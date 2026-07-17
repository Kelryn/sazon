from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
import yaml

from ..ingesta.alcampo_client import AlcampoClient, AlcampoClientConfig
from ..ingesta.categories import FOOD_CATEGORY_ROOTS
from ..ingesta.models import product_from_decorated
from ..normalizacion.clasificacion import (
    DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS,
    DEFAULT_KEYWORDS_EXCLUIDAS,
    ConfigClasificacion,
)
from ..normalizacion.limpieza import normalizar_producto
from .db import get_connection, init_db
from .reporte import resumen_por_categoria
from .repositorio import ProductoRepository

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _config_clasificacion(cfg: dict) -> ConfigClasificacion:
    norm = cfg.get("normalizacion", {}) or {}
    raices = norm.get("categorias_raiz_excluidas")
    keywords = norm.get("subcategorias_excluidas_keywords")
    alcohol = norm.get("subcat_alcohol_cocina")
    kwargs = dict(
        categorias_raiz_excluidas=tuple(raices) if raices else DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS,
        keywords_excluidas=tuple(keywords) if keywords else DEFAULT_KEYWORDS_EXCLUIDAS,
    )
    if alcohol:
        kwargs["subcat_alcohol_cocina"] = tuple(alcohol)
    return ConfigClasificacion(**kwargs)


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option(
    "--db",
    "db_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Ruta del fichero SQLite (por defecto, la de config.yaml).",
)
@click.option(
    "--limit-products-per-category",
    default=None,
    type=int,
    help="Toma solo N productos por categoria hoja (para pruebas rapidas).",
)
@click.option("-v", "--verbose", is_flag=True, help="Log detallado por categoria.")
def main(
    config_path: Path,
    db_path: Path | None,
    limit_products_per_category: int | None,
    verbose: bool,
) -> None:
    """Extrae el catalogo, lo normaliza y lo carga en SQLite (Fase 2)."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = _load_config(config_path)
    ingesta_cfg = cfg.get("ingesta", {}) or {}
    almac_cfg = cfg.get("almacenamiento", {}) or {}

    db_path = db_path or Path(almac_cfg.get("db_path", "data/menu.db"))
    root_ids = set(ingesta_cfg.get("category_roots") or FOOD_CATEGORY_ROOTS.keys())
    config_clas = _config_clasificacion(cfg)

    client_config = AlcampoClientConfig(
        cache_dir=Path(ingesta_cfg.get("cache_dir", ".cache/alcampo")),
        min_request_interval_seconds=float(ingesta_cfg.get("min_request_interval_seconds", 1.5)),
        max_request_interval_jitter_seconds=float(
            ingesta_cfg.get("max_request_interval_jitter_seconds", 0.5)
        ),
        category_tree_ttl_seconds=int(ingesta_cfg.get("category_tree_ttl_hours", 24)) * 3600,
        product_page_ttl_seconds=int(ingesta_cfg.get("product_page_ttl_hours", 6)) * 3600,
    )

    ahora = datetime.now(UTC)
    fecha_extraccion = ahora.date().isoformat()
    fecha_actualizacion = ahora.isoformat(timespec="seconds")

    conn = get_connection(db_path)
    init_db(conn)
    repo = ProductoRepository(conn)

    seen_ids: set[str] = set()
    normalizados = []

    with AlcampoClient(client_config) as client:
        leaves = list(client.iter_leaf_categories(root_ids))
        logger.info("Categorias hoja a procesar: %d", len(leaves))

        for i, leaf in enumerate(leaves, start=1):
            retailer_category_id = leaf["retailerCategoryId"]
            logger.info("[%d/%d] %s (%s)", i, len(leaves), " > ".join(leaf["path"]), retailer_category_id)
            tomados = 0
            for raw in client.iter_category_products(retailer_category_id):
                rpid = raw.get("retailerProductId")
                if rpid and rpid in seen_ids:
                    continue
                if rpid:
                    seen_ids.add(rpid)
                producto = product_from_decorated(raw, leaf["path"], fecha_extraccion)
                normalizados.append(normalizar_producto(producto, config_clas))
                tomados += 1
                if limit_products_per_category and tomados >= limit_products_per_category:
                    break

    resumen = repo.upsert_muchos(normalizados, fecha_actualizacion)

    click.echo(
        f"BD actualizada en {db_path}: {resumen['procesados']} procesados "
        f"({resumen['nuevos']} nuevos, {resumen['cambios_precio']} cambios de precio)."
    )
    por_apto = repo.contar_por_apto()
    click.echo(
        f"Aptos para receta: {por_apto.get(True, 0)} | "
        f"No aptos (bebidas, alcohol, suplementos...): {por_apto.get(False, 0)}"
    )

    df = resumen_por_categoria(conn)
    if not df.empty:
        click.echo("\nResumen por categoria:")
        click.echo(
            df[["categoria", "productos", "aptos_receta", "pct_aptos", "en_oferta", "precio_medio"]]
            .to_string(index=False)
        )

    conn.close()


if __name__ == "__main__":
    main()
