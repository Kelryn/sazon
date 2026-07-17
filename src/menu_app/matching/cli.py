from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from ..ia.claves import obtener_clave
from ..ia.desambiguador import crear_desambiguador
from .matcher import UMBRAL_LEXICO, IndiceProductos, Match, MatcherLexico
from .normalizar import clave_ingrediente
from .repositorio import MatchingRepository

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--umbral", default=UMBRAL_LEXICO, type=float, help="Umbral de similitud lexica (0-100).")
@click.option(
    "--con-llm",
    is_flag=True,
    help="Desambigua con Claude entre los candidatos lexicos (necesita clave de API).",
)
@click.option(
    "--k-candidatos", default=8, type=int, help="Nº de candidatos lexicos que ve el LLM."
)
@click.option("-v", "--verbose", is_flag=True)
def main(
    config_path: Path,
    db_path: Path | None,
    umbral: float,
    con_llm: bool,
    k_candidatos: int,
    verbose: bool,
) -> None:
    """Empareja los ingredientes de receta con productos de Alcampo (Fase 4).

    Por defecto usa solo el matcher lexico. Con --con-llm, para cada ingrediente
    Claude elige el producto correcto entre los candidatos lexicos (rompe el
    techo de precision del texto).
    """
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = _load_config(config_path)
    almac_cfg = cfg.get("almacenamiento", {}) or {}
    ia_cfg = cfg.get("ia", {}) or {}
    db_path = db_path or Path(almac_cfg.get("db_path", "data/menu.db"))
    # Umbral fuzzy configurable (#21): si no se pasa --umbral, usa el de config.yaml.
    if umbral == UMBRAL_LEXICO and "matching_umbral_fuzzy" in cfg:
        umbral = float(cfg["matching_umbral_fuzzy"])

    proveedor = ia_cfg.get("proveedor", "gemini")
    intervalo_llm = float(ia_cfg.get("min_request_interval_seconds", 4.0))
    desambiguador = None
    if con_llm:
        clave = obtener_clave(proveedor)
        if not clave:
            raise click.ClickException(
                f"No hay clave de API para '{proveedor}'. Ejecuta primero "
                "'menu-app-config-clave' para guardarla."
            )
        desambiguador = crear_desambiguador(
            proveedor, api_key=clave, modelo=ia_cfg.get("modelo_desambiguador")
        )

    conn = get_connection(db_path)
    init_db(conn)
    repo = MatchingRepository(conn)

    indice = IndiceProductos.construir(repo.productos_aptos())
    ingredientes = repo.ingredientes_distintos()
    click.echo(
        f"Productos aptos en indice: {len(indice)} | ingredientes distintos: {len(ingredientes)} | "
        f"desambiguacion: {'LLM (' + desambiguador.modelo + ')' if desambiguador else 'solo lexico'}"
    )

    matcher = MatcherLexico(indice, umbral=umbral)
    sinonimos = repo.sinonimos()  # sinonimos del usuario (#22/#14)
    if sinonimos:
        click.echo(f"Sinonimos del usuario aplicados: {len(sinonimos)}")
    fecha = datetime.now(UTC).isoformat(timespec="seconds")
    con_match = 0

    def _aplicar_sinonimos(clave: str) -> str:
        return " ".join(sinonimos.get(t, t) for t in clave.split())

    for i, ing in enumerate(ingredientes, start=1):
        clave = _aplicar_sinonimos(clave_ingrediente(ing))
        if desambiguador is not None:
            match = _emparejar_con_llm(matcher, desambiguador, clave, k_candidatos)
            time.sleep(intervalo_llm)  # respeta el limite de la capa gratuita
        else:
            match = matcher.emparejar(clave)

        repo.upsert_mapeo(ing, clave, match, metodo_sin_match="sin_match", fecha=fecha)
        if match:
            con_match += 1
        if verbose:
            destino = match.producto_nombre[:45] if match else "SIN MATCH"
            logger.info("  [%d/%d] '%s' -> %s", i, len(ingredientes), clave, destino)

    total = len(ingredientes)
    pct = 100 * con_match / total if total else 0
    click.echo(
        f"Emparejados {con_match}/{total} ({pct:.0f}%). "
        f"Sin correspondencia: {total - con_match} ({100 - pct:.0f}%)."
    )


def _emparejar_con_llm(
    matcher: MatcherLexico, desambiguador, clave: str, k: int
) -> Match | None:
    """Genera candidatos lexicos y deja que el LLM elija el correcto."""
    candidatos = matcher.candidatos(clave, k=k)
    if not candidatos:
        return None
    try:
        idx = desambiguador.elegir(clave, [c.producto_nombre for c in candidatos])
    except Exception as e:  # noqa: BLE001 - un ingrediente no debe tumbar la pasada
        logger.warning("Fallo LLM en %r: %s; se cae al lexico", clave, e)
        return matcher.emparejar(clave)
    if idx is None:
        return None
    elegido = candidatos[idx]
    return Match(
        retailer_product_id=elegido.retailer_product_id,
        producto_nombre=elegido.producto_nombre,
        score=elegido.score,
        metodo="llm",
    )


if __name__ == "__main__":
    main()
