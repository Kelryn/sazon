from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from ..almacenamiento.repositorio import ProductoRepository
from .matcher import mejor_match, texto_busqueda
from .off_client import OFFClient

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--limit", default=None, type=int, help="Cruza solo N productos (muestra/pruebas).")
@click.option("--incluir-no-aptos", is_flag=True)
@click.option("-v", "--verbose", is_flag=True)
def main(
    config_path: Path,
    db_path: Path | None,
    limit: int | None,
    incluir_no_aptos: bool,
    verbose: bool,
) -> None:
    """Cruza los productos con Open Food Facts (por nombre+marca) -> EAN, Nutri-Score, NOVA, alergenos."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = _load_config(config_path)
    almac_cfg = cfg.get("almacenamiento", {}) or {}
    off_cfg = cfg.get("off", {}) or {}
    db_path = db_path or Path(almac_cfg.get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    init_db(conn)
    repo = ProductoRepository(conn)

    pendientes = repo.productos_sin_off(solo_aptos=not incluir_no_aptos, limite=limit)
    click.echo(f"Productos a cruzar con OFF: {len(pendientes)}")

    fecha = datetime.now(UTC).isoformat(timespec="seconds")
    con_match = 0
    with OFFClient(
        cache_dir=off_cfg.get("cache_dir", ".cache/off"),
        min_request_interval_seconds=float(off_cfg.get("min_request_interval_seconds", 3.0)),
    ) as off:
        for i, (rid, nombre, marca) in enumerate(pendientes, start=1):
            try:
                candidatos = off.buscar(texto_busqueda(nombre, marca))
                datos = mejor_match(nombre, marca, candidatos)
            except Exception as e:  # noqa: BLE001 - un producto no debe tumbar la pasada
                logger.warning("Fallo OFF en %s (%s): %s", rid, nombre[:40], e)
                continue
            repo.actualizar_off(rid, datos, fecha)
            if datos:
                con_match += 1
            if verbose and i % 20 == 0:
                logger.info("  %d/%d (%d con match)", i, len(pendientes), con_match)

    click.echo(
        f"Cruce OFF terminado: {con_match} de {len(pendientes)} con match fiable "
        f"(>= umbral de similitud)."
    )


if __name__ == "__main__":
    main()
