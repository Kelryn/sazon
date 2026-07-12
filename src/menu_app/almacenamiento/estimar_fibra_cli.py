from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..normalizacion.fibra_estimada import estimar_fibra
from .db import get_connection, init_db


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--rehacer", is_flag=True, help="Rehace tambien las estimaciones de fibra ya puestas.")
@click.option("-v", "--verbose", is_flag=True)
def main(config_path: Path, db_path: Path | None, rehacer: bool, verbose: bool) -> None:
    """Rellena la FIBRA estimada (USDA/BEDCA) en productos que traen el resto de
    nutrientes pero no la fibra (Alcampo apenas la declara)."""
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    init_db(conn)

    # Con --rehacer, primero se retira la fibra estimada previa (para reestimar con
    # la tabla actual y limpiar falsos positivos); nunca toca la fibra real de 'bop'.
    if rehacer:
        conn.execute(
            "UPDATE productos SET fibra_100g = NULL, fibra_estimada = NULL WHERE fibra_estimada = 1"
        )
        conn.commit()

    # Productos aptos con nutricion pero SIN fibra.
    pendientes = conn.execute(
        "SELECT retailer_product_id, nombre FROM productos "
        "WHERE apto_receta = 1 AND energia_kcal_100g IS NOT NULL AND fibra_100g IS NULL"
    ).fetchall()

    estimados = 0
    for p in pendientes:
        fibra = estimar_fibra(p["nombre"])
        if fibra is None:
            continue
        conn.execute(
            "UPDATE productos SET fibra_100g = ?, fibra_estimada = 1 WHERE retailer_product_id = ?",
            (fibra, p["retailer_product_id"]),
        )
        estimados += 1
        if verbose:
            click.echo(f"  {p['nombre'][:55]:55s} -> fibra {fibra:.1f} g/100g")
    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) FROM productos WHERE apto_receta = 1 AND energia_kcal_100g IS NOT NULL"
    ).fetchone()[0]
    con_fibra = conn.execute(
        "SELECT COUNT(*) FROM productos WHERE apto_receta = 1 AND energia_kcal_100g IS NOT NULL "
        "AND fibra_100g IS NOT NULL"
    ).fetchone()[0]
    click.echo(
        f"Productos sin fibra revisados: {len(pendientes)} | fibra estimada añadida: {estimados}."
    )
    click.echo(f"Cobertura de fibra (aptos con nutricion): {con_fibra}/{total} ({100 * con_fibra / total:.0f}%).")
    conn.close()


if __name__ == "__main__":
    main()
