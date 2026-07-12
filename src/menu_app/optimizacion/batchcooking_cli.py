from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from .batchcooking import clasificar_recetas


def _db_path(config_path: Path, db_path: Path | None) -> Path:
    if db_path:
        return db_path
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    return Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
def main(config_path: Path, db_path: Path | None) -> None:
    """Clasifica las recetas en aptas / no aptas para batchcooking (columna es_batchcooking)."""
    conn = get_connection(_db_path(config_path, db_path))
    init_db(conn)
    r = clasificar_recetas(conn)
    conn.close()

    total = r["total"] or 1
    pct_bc = 100 * r["batchcooking"] / total
    pct_esp = 100 * r["batchcooking_espanolas"] / (r["batchcooking"] or 1)
    click.echo(f"Recetas: {r['total']}")
    click.echo(f"  batchcooking:    {r['batchcooking']:4d} ({pct_bc:.0f}%)")
    click.echo(f"  no batchcooking: {r['no_batchcooking']:4d} ({100 - pct_bc:.0f}%)")
    click.echo(
        f"  de las batchcooking, españolas: {r['batchcooking_espanolas']} ({pct_esp:.0f}%)"
    )
    if pct_bc < 45:
        click.echo("[!] Menos del ~50% son batchcooking: conviene ampliar guisos/legumbres/arroces.")
    if pct_esp < 50:
        click.echo("[!] Menos del 50% de las batchcooking son españolas.")


if __name__ == "__main__":
    main()
