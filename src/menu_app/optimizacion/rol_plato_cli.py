from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from .rol_plato import clasificar_roles


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
    """Clasifica el ROL de cada receta: principal / postre / desayuno / guarnicion."""
    conn = get_connection(_db_path(config_path, db_path))
    init_db(conn)
    c = clasificar_roles(conn)
    conn.close()
    total = sum(c.values()) or 1
    click.echo(f"Recetas: {total}")
    for rol in ("principal", "postre", "desayuno", "guarnicion"):
        n = c.get(rol, 0)
        click.echo(f"  {rol:12s} {n:5d} ({100*n/total:.0f}%)")


if __name__ == "__main__":
    main()
