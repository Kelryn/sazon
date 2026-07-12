from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from .descubrimiento import (
    BUSQUEDAS_MEDITERRANEAS,
    CATEGORIAS_PRINCIPALES,
    SEMILLAS_SALADAS,
    dataset_arranque_completo,
    urls_desde_busquedas,
    urls_desde_categorias,
    urls_desde_pagina,
    urls_desde_sitemap,
    urls_por_crawl,
)
from .repositorio import RecetaRepository
from .scraper import RecetaScraper

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _id_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--from-sitemap", "sitemap_url", default=None, help="Descubre recetas de un sitemap.")
@click.option(
    "--from-pagina",
    "pagina_url",
    default=None,
    help="Descubre recetas extrayendo enlaces de una pagina de listado (home/categoria).",
)
@click.option(
    "--crawl",
    "crawl_n",
    default=None,
    type=int,
    help="Rastrea N recetas siguiendo 'relacionadas' desde semillas saladas (amplia el corpus).",
)
@click.option(
    "--mediterranea",
    is_flag=True,
    help="Cosecha recetas de PLATOS PRINCIPALES de cocina española/mediterranea e italiana "
    "(categorias + buscador griego/italiano) e ingiere. Amplia el corpus con ingredientes "
    "que estan en Alcampo.",
)
@click.option(
    "--paginas-categoria", default=2, type=int, help="Nº de paginas por categoria a cosechar."
)
@click.option(
    "--urls-file",
    "urls_file",
    default=None,
    type=click.Path(path_type=Path),
    help="Fichero con una URL de receta por linea.",
)
@click.option("--limit", default=None, type=int, help="Ingesta como mucho N recetas.")
@click.option("--reingerir", is_flag=True, help="Reprocesa aunque la receta ya este en la BD.")
@click.option("-v", "--verbose", is_flag=True)
def main(
    config_path: Path,
    db_path: Path | None,
    sitemap_url: str | None,
    pagina_url: str | None,
    crawl_n: int | None,
    mediterranea: bool,
    paginas_categoria: int,
    urls_file: Path | None,
    limit: int | None,
    reingerir: bool,
    verbose: bool,
) -> None:
    """Ingesta recetas de webs ES a SQLite (Fase 3)."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = _load_config(config_path)
    almac_cfg = cfg.get("almacenamiento", {}) or {}
    recetas_cfg = cfg.get("recetas", {}) or {}
    db_path = db_path or Path(almac_cfg.get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    init_db(conn)
    repo = RecetaRepository(conn)
    fecha = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with RecetaScraper(
        cache_dir=recetas_cfg.get("cache_dir", ".cache/recetas"),
        min_request_interval_seconds=float(recetas_cfg.get("min_request_interval_seconds", 2.0)),
    ) as scraper:
        if mediterranea:
            click.echo("Descubriendo recetas mediterraneas (categorias + buscador)...")
            urls = urls_desde_categorias(CATEGORIAS_PRINCIPALES, paginas=paginas_categoria)
            urls += urls_desde_busquedas(BUSQUEDAS_MEDITERRANEAS)
            urls = list(dict.fromkeys(urls))
            if limit:
                urls = urls[:limit]
            click.echo(f"URLs de receta descubiertas: {len(urls)}")
            ok = _ingerir_lista(scraper, repo, urls, fecha, reingerir, verbose)
        elif crawl_n:
            # Crawl + ingesta en una sola pasada: cada pagina se descarga UNA vez
            # (se ingiere y de la misma descarga se sacan las recetas relacionadas).
            ok = _crawl_ingesta(scraper, repo, SEMILLAS_SALADAS, crawl_n, fecha, reingerir, verbose)
        else:
            if urls_file:
                urls = [l.strip() for l in urls_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            elif sitemap_url:
                urls = urls_desde_sitemap(sitemap_url)
            elif pagina_url:
                urls = urls_desde_pagina(pagina_url)
            else:
                urls = dataset_arranque_completo()
            if limit:
                urls = urls[:limit]
            click.echo(f"URLs de receta a procesar: {len(urls)}")
            ok = _ingerir_lista(scraper, repo, urls, fecha, reingerir, verbose)

    click.echo(
        f"Recetas ingeridas (nuevas): {ok} | "
        f"total en BD: {repo.contar_recetas()} ({repo.contar_ingredientes()} ingredientes)."
    )


def _ingerir_lista(scraper, repo, urls, fecha, reingerir, verbose) -> int:
    ok = 0
    for i, url in enumerate(urls, start=1):
        if not reingerir and repo.url_ya_ingerida(_id_url(url)):
            continue
        try:
            receta = scraper.scrape(url)
        except Exception as e:  # noqa: BLE001
            logger.warning("Fallo al procesar %s: %s", url, e)
            continue
        if receta is None:
            continue
        repo.upsert_receta(receta, fecha)
        ok += 1
        if verbose:
            logger.info("  [%d/%d] %s (%d ingr)", i, len(urls), receta.titulo[:50], len(receta.ingredientes))
    return ok


def _crawl_ingesta(scraper, repo, semillas, limite, fecha, reingerir, verbose) -> int:
    """BFS: descarga cada pagina una vez, ingiere la receta y encola las relacionadas."""
    from collections import deque

    vistas: set[str] = set()
    frontera: deque[str] = deque(dict.fromkeys(semillas))
    ok = 0
    while frontera and ok < limite:
        url = frontera.popleft()
        if url in vistas:
            continue
        vistas.add(url)
        if not reingerir and repo.url_ya_ingerida(_id_url(url)):
            # Aun asi necesitamos sus enlaces para seguir el crawl.
            try:
                _, enlaces = scraper.scrape_con_enlaces(url)
            except Exception:  # noqa: BLE001
                continue
            for e in enlaces:
                if e not in vistas:
                    frontera.append(e)
            continue
        try:
            receta, enlaces = scraper.scrape_con_enlaces(url)
        except Exception as e:  # noqa: BLE001
            logger.warning("Fallo en %s: %s", url, e)
            continue
        for enlace in enlaces:
            if enlace not in vistas:
                frontera.append(enlace)
        if receta is None:
            continue
        repo.upsert_receta(receta, fecha)
        ok += 1
        if verbose and ok % 25 == 0:
            logger.info("  %d/%d recetas ingeridas (frontera: %d)", ok, limite, len(frontera))
    return ok


if __name__ == "__main__":
    main()
