from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from .reporte_sin_match import generar_reporte


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--salida", default="ingredientes_sin_match.md", type=click.Path(path_type=Path))
def main(config_path: Path, db_path: Path | None, salida: Path) -> None:
    """Genera un .md con los ingredientes que no han casado con productos de Alcampo."""
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(db_path)
    init_db(conn)
    md = generar_reporte(conn)
    conn.close()
    salida.write_text(md, encoding="utf-8")
    click.echo(f"Informe escrito en {salida}")


if __name__ == "__main__":
    main()
