from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
import yaml

from ..ingesta.alcampo_client import AlcampoClient, AlcampoClientConfig
from ..ingesta.exceptions import AlcampoBlockedError
from ..normalizacion.detalle import parsear_detalle
from .db import get_connection, init_db
from .repositorio import ProductoRepository

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--limit",
    default=None,
    type=int,
    help="Enriquece solo N productos (para muestras/pruebas). Sin limite: todos los pendientes.",
)
@click.option(
    "--incluir-no-aptos",
    is_flag=True,
    help="Tambien enriquece los productos no aptos para receta (por defecto solo aptos).",
)
@click.option("-v", "--verbose", is_flag=True)
def main(
    config_path: Path,
    db_path: Path | None,
    limit: int | None,
    incluir_no_aptos: bool,
    verbose: bool,
) -> None:
    """Rellena nutricion/ingredientes/origen de los productos ya cargados (endpoint bop)."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = _load_config(config_path)
    ingesta_cfg = cfg.get("ingesta", {}) or {}
    almac_cfg = cfg.get("almacenamiento", {}) or {}
    db_path = db_path or Path(almac_cfg.get("db_path", "data/menu.db"))

    client_config = AlcampoClientConfig(
        cache_dir=Path(ingesta_cfg.get("cache_dir", ".cache/alcampo")),
        min_request_interval_seconds=float(ingesta_cfg.get("min_request_interval_seconds", 1.5)),
        max_request_interval_jitter_seconds=float(
            ingesta_cfg.get("max_request_interval_jitter_seconds", 0.5)
        ),
        product_page_ttl_seconds=int(ingesta_cfg.get("product_page_ttl_hours", 6)) * 3600,
    )

    conn = get_connection(db_path)
    init_db(conn)
    repo = ProductoRepository(conn)

    ids = repo.ids_sin_enriquecer(solo_aptos=not incluir_no_aptos, limite=limit)
    click.echo(f"Productos a enriquecer: {len(ids)}")

    fecha = datetime.now(UTC).isoformat(timespec="seconds")
    con_nutricion = 0
    errores = 0

    with AlcampoClient(client_config) as client:
        for i, rid in enumerate(ids, start=1):
            try:
                detalle = parsear_detalle(client.get_product_detail(rid))
            except AlcampoBlockedError:
                errores += 1
                continue
            except Exception as e:  # noqa: BLE001 - un producto no debe tumbar la pasada
                logger.warning("Fallo al enriquecer %s: %s", rid, e)
                errores += 1
                continue
            repo.actualizar_detalle(rid, detalle, fecha)
            if detalle.tiene_nutricion():
                con_nutricion += 1
            if verbose and i % 25 == 0:
                logger.info("  %d/%d procesados", i, len(ids))

    click.echo(
        f"Enriquecidos {len(ids) - errores} de {len(ids)} "
        f"({con_nutricion} con datos nutricionales, {errores} errores/sin datos)."
    )


if __name__ == "__main__":
    main()
