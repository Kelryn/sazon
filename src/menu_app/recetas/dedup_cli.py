"""CLI `menu-app-dedup-recetas`: reporta grupos de recetas casi-duplicadas (#45).

Solo informa; no borra nada (el usuario decide con menu-app-receta si elimina alguna).
"""

from __future__ import annotations

from pathlib import Path

import click

from ..almacenamiento.db import get_connection, init_db
from ..configuracion import cargar_config
from .dedup import encontrar_duplicados


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
def main(config_path: Path, db_path: Path | None) -> None:
    """Lista grupos de recetas que probablemente son el mismo plato (>=60% ingredientes en comun)."""
    cfg = cargar_config(config_path)
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(db_path)
    init_db(conn)
    grupos = encontrar_duplicados(conn)
    conn.close()

    if not grupos:
        click.echo("No se encontraron recetas duplicadas evidentes.")
        return
    click.echo(f"{len(grupos)} grupos de posibles duplicados:\n")
    for g in grupos:
        click.echo(f"[{g.familia}]")
        for rid, titulo, fuente in g.recetas:
            click.echo(f"  {rid}  {titulo[:60]:<60} ({fuente})")
        click.echo("")


if __name__ == "__main__":
    main()
