from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
import yaml

from .alcampo_client import AlcampoClient, AlcampoClientConfig
from .categories import FOOD_CATEGORY_ROOTS
from .csv_export import write_catalog_csv
from .models import Product, product_from_decorated

logger = logging.getLogger(__name__)


def _load_ingesta_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        full_config = yaml.safe_load(f) or {}
    return full_config.get("ingesta", {}) or {}


@click.command()
@click.option(
    "--config",
    "config_path",
    default="config.yaml",
    type=click.Path(path_type=Path),
    help="Ruta al config.yaml del proyecto (seccion 'ingesta').",
)
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Ruta del CSV de salida (por defecto, la de config.yaml).",
)
@click.option(
    "--limit-categories",
    default=None,
    type=int,
    help="Solo procesa las N primeras categorias hoja (util para pruebas rapidas).",
)
@click.option(
    "--limit-products",
    default=None,
    type=int,
    help="Para en cuanto se acumulen N productos en total (util para revisar una muestra del CSV).",
)
@click.option(
    "--limit-products-per-category",
    default=None,
    type=int,
    help=(
        "En cada categoria hoja, solo toma los N primeros productos nuevos antes de pasar a la "
        "siguiente (util para ver una muestra representativa de todas las categorias sin extraer "
        "el catalogo entero)."
    ),
)
@click.option("-v", "--verbose", is_flag=True, help="Log detallado por categoria.")
def main(
    config_path: Path,
    output_path: Path | None,
    limit_categories: int | None,
    limit_products: int | None,
    limit_products_per_category: int | None,
    verbose: bool,
) -> None:
    """Extrae el catalogo de alimentacion de Alcampo a un CSV."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ingesta_cfg = _load_ingesta_config(config_path)
    output_path = output_path or Path(ingesta_cfg.get("output_csv", "data/catalogo_alcampo.csv"))
    root_ids = set(ingesta_cfg.get("category_roots") or FOOD_CATEGORY_ROOTS.keys())

    client_config = AlcampoClientConfig(
        cache_dir=Path(ingesta_cfg.get("cache_dir", ".cache/alcampo")),
        min_request_interval_seconds=float(ingesta_cfg.get("min_request_interval_seconds", 1.5)),
        max_request_interval_jitter_seconds=float(
            ingesta_cfg.get("max_request_interval_jitter_seconds", 0.5)
        ),
        category_tree_ttl_seconds=int(ingesta_cfg.get("category_tree_ttl_hours", 24)) * 3600,
        product_page_ttl_seconds=int(ingesta_cfg.get("product_page_ttl_hours", 6)) * 3600,
    )

    fecha_extraccion = datetime.now(UTC).date().isoformat()
    products: list[Product] = []
    seen_ids: set[str] = set()

    with AlcampoClient(client_config) as client:
        leaves = list(client.iter_leaf_categories(root_ids))
        if limit_categories:
            leaves = leaves[:limit_categories]
        logger.info("Categorias hoja a procesar: %d", len(leaves))

        for i, leaf in enumerate(leaves, start=1):
            retailer_category_id = leaf["retailerCategoryId"]
            path_str = " > ".join(leaf["path"])
            logger.info(
                "[%d/%d] %s (%s, %d productos segun el arbol)",
                i,
                len(leaves),
                path_str,
                retailer_category_id,
                leaf.get("productCount", 0),
            )
            count_before = len(products)
            for raw_product in client.iter_category_products(retailer_category_id):
                rpid = raw_product.get("retailerProductId")
                if rpid and rpid in seen_ids:
                    continue
                if rpid:
                    seen_ids.add(rpid)
                products.append(product_from_decorated(raw_product, leaf["path"], fecha_extraccion))
                if limit_products_per_category and len(products) - count_before >= limit_products_per_category:
                    break
                if limit_products and len(products) >= limit_products:
                    break
            logger.info("  -> %d productos nuevos", len(products) - count_before)
            if limit_products and len(products) >= limit_products:
                logger.info("Limite de %d productos alcanzado, se para aqui.", limit_products)
                break

    total = write_catalog_csv(products, output_path)
    click.echo(f"CSV escrito en {output_path} con {total} productos.")


if __name__ == "__main__":
    main()
