from __future__ import annotations

from pathlib import Path

import click
import yaml

from ..normalizacion.nutricion_estimada import estimar
from .db import get_connection, init_db

_COLS = ["energia_kcal", "grasas", "grasas_sat", "hidratos", "azucares", "proteinas", "sal", "fibra"]

# Subcategorias que NO se estiman: especias/sazonadores (van en trazas y dan
# falsos positivos tipo "chile con limon"->limon), e infusiones/cafe/te (aporte
# nutricional irrelevante y ambiguo).
_SUBCAT_EXCLUIDAS = ("especia", "sazonador", "infusion", "cafe", "te e ")


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--rehacer", is_flag=True, help="Rehace tambien las estimaciones ya puestas.")
@click.option("-v", "--verbose", is_flag=True)
def main(config_path: Path, db_path: Path | None, rehacer: bool, verbose: bool) -> None:
    """Rellena nutricion ESTIMADA (USDA/BEDCA) para frescos aptos sin datos reales."""
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    init_db(conn)

    filtro_excluidas = " AND " + " AND ".join(
        f"lower(subcategoria) NOT LIKE '%{k}%'" for k in _SUBCAT_EXCLUIDAS
    )

    # Limpia estimaciones previas en subcategorias que ahora excluimos (idempotente).
    cols_null = ", ".join(f"{c}_100g = NULL" for c in _COLS)
    limpiadas = conn.execute(
        f"UPDATE productos SET {cols_null}, fuente_nutricion = NULL "
        f"WHERE fuente_nutricion = 'estimada' AND NOT (1{filtro_excluidas})"
    ).rowcount
    conn.commit()
    if limpiadas:
        click.echo(f"Estimaciones retiradas de subcategorias excluidas (especias/infusiones): {limpiadas}")

    # Productos aptos sin nutricion real; si no --rehacer, tampoco los ya estimados.
    sql = (
        "SELECT retailer_product_id, nombre FROM productos "
        "WHERE apto_receta = 1 AND energia_kcal_100g IS NULL" + filtro_excluidas
    )
    if not rehacer:
        sql += " AND fuente_nutricion IS NULL"
    pendientes = conn.execute(sql).fetchall()

    set_clause = ", ".join(f"{c}_100g = :{c}" for c in _COLS)
    estimados = 0
    por_alimento: dict[str, int] = {}
    for p in pendientes:
        res = estimar(p["nombre"])
        if res is None:
            continue
        macros, alimento = res
        params = {c: macros[c] for c in _COLS}
        params["rid"] = p["retailer_product_id"]
        conn.execute(
            f"UPDATE productos SET {set_clause}, base_nutricional='100g', "
            f"fuente_nutricion='estimada' WHERE retailer_product_id = :rid",
            params,
        )
        estimados += 1
        por_alimento[alimento] = por_alimento.get(alimento, 0) + 1
        if verbose:
            click.echo(f"  {p['nombre'][:50]:50s} -> {alimento} ({macros['energia_kcal']:.0f} kcal)")
    conn.commit()

    click.echo(
        f"Frescos sin nutricion: {len(pendientes)} | estimados: {estimados} "
        f"({len(pendientes) - estimados} sin correspondencia en la tabla)."
    )
    if por_alimento:
        top = sorted(por_alimento.items(), key=lambda x: -x[1])[:10]
        click.echo("Top alimentos estimados: " + ", ".join(f"{a}({n})" for a, n in top))
    conn.close()


if __name__ == "__main__":
    main()
