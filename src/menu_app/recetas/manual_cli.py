from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..almacenamiento.db import get_connection, init_db
from .manual import añadir_receta_manual, listar_favoritas, marcar_favorita


def _db(config_path: Path, db_path: Path | None):
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    ruta = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(ruta)
    init_db(conn)
    return conn


@click.group()
def main() -> None:
    """Gestiona recetas MANUALES y FAVORITAS (Fase 6)."""


@main.command("anadir")
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--titulo", required=True, help="Nombre de la receta.")
@click.option("--raciones", required=True, type=int, help="Nº de raciones.")
@click.option(
    "--ingrediente", "ingredientes", multiple=True, required=True,
    help="Linea de ingrediente ('200 g de lentejas'). Repetir por cada uno.",
)
@click.option("--favorita", is_flag=True, help="Marcar como favorita (se prioriza en el menu).")
@click.option("--tiempo", type=int, default=None, help="Tiempo total en minutos (opcional).")
def anadir(config_path, db_path, titulo, raciones, ingredientes, favorita, tiempo):
    """Da de alta una receta manual (nombre + ingredientes con cantidades)."""
    conn = _db(config_path, db_path)
    try:
        rid = añadir_receta_manual(
            conn, titulo=titulo, raciones=raciones, ingredientes=list(ingredientes),
            es_favorita=favorita, tiempo_total_min=tiempo,
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Receta '{titulo}' guardada (id {rid}){' [FAVORITA]' if favorita else ''}.")
    click.echo(
        "Recuerda ejecutar 'menu-app-emparejar' para casar sus ingredientes con productos "
        "antes de generar el menu."
    )
    conn.close()


@main.command("favorita")
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.argument("receta_id")
@click.option("--quitar", is_flag=True, help="Desmarcar en vez de marcar.")
def favorita(config_path, db_path, receta_id, quitar):
    """Marca (o desmarca con --quitar) una receta como favorita por su id."""
    conn = _db(config_path, db_path)
    ok = marcar_favorita(conn, receta_id, favorita=not quitar)
    conn.close()
    if not ok:
        raise click.ClickException(f"No existe la receta con id {receta_id}.")
    click.echo(f"Receta {receta_id} {'desmarcada' if quitar else 'marcada'} como favorita.")


@main.command("listar")
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
def listar(config_path, db_path):
    """Lista las recetas favoritas."""
    conn = _db(config_path, db_path)
    favs = listar_favoritas(conn)
    conn.close()
    if not favs:
        click.echo("No hay recetas favoritas.")
        return
    click.echo(f"Favoritas ({len(favs)}):")
    for rid, titulo, fuente in favs:
        click.echo(f"  {rid}  {titulo[:50]:50s}  [{fuente}]")


if __name__ == "__main__":
    main()
