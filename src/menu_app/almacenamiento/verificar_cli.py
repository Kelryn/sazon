"""Prueba de verificacion: muestra que la clasificacion y el enriquecimiento
nutricional funcionan sobre alimentos reales ya extraidos.

Pensado para ejecutarlo tras cargar/enriquecer la BD y comprobar de un vistazo
que (1) los productos se estan calificando bien como aptos/no aptos para
receta y (2) los datos nutricionales obtenidos son correctos y coherentes.
"""

from __future__ import annotations

from pathlib import Path

import click
import yaml

from .db import get_connection
from .repositorio import ProductoRepository


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--n", "n", default=6, type=int, help="Ejemplos a mostrar por bloque.")
def main(config_path: Path, db_path: Path | None, n: int) -> None:
    """Muestra ejemplos reales de clasificacion y nutricion para verificar el sistema."""
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    repo = ProductoRepository(conn)

    por_apto = repo.contar_por_apto()
    con_nutri = repo.contar_enriquecidos_con_nutricion()
    con_off = repo.contar_con_off()
    click.echo(
        f"Total: {repo.contar()} | aptos receta: {por_apto.get(True, 0)} | "
        f"no aptos: {por_apto.get(False, 0)} | con nutricion (bop): {con_nutri} | "
        f"con match OFF: {con_off}\n"
    )

    click.echo("== Clasificacion: APTOS para receta ==")
    for r in conn.execute(
        "SELECT nombre, subcategoria FROM productos WHERE apto_receta=1 ORDER BY RANDOM() LIMIT ?", (n,)
    ):
        click.echo(f"  [OK] {r['nombre'][:48]:48s} [{r['subcategoria']}]")

    click.echo("\n== Clasificacion: NO aptos (bebidas/alcohol/golosinas/suplementos) ==")
    for r in conn.execute(
        "SELECT nombre, categoria, subcategoria FROM productos WHERE apto_receta=0 "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ):
        click.echo(f"  [--] {r['nombre'][:40]:40s} [{r['categoria']} > {r['subcategoria']}]")

    click.echo("\n== Nutricion (por 100 g/ml) de productos reales enriquecidos ==")
    filas = conn.execute(
        "SELECT nombre, energia_kcal_100g, grasas_100g, azucares_100g, proteinas_100g, sal_100g, "
        "base_nutricional, origen FROM productos WHERE energia_kcal_100g IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    click.echo(f"  {'producto':40s} {'kcal':>5s} {'gras':>5s} {'azuc':>5s} {'prot':>5s} {'sal':>5s} origen")
    for r in filas:
        click.echo(
            f"  {r['nombre'][:40]:40s} {r['energia_kcal_100g']!s:>5s} {r['grasas_100g']!s:>5s} "
            f"{r['azucares_100g']!s:>5s} {r['proteinas_100g']!s:>5s} {r['sal_100g']!s:>5s} {r['origen']}"
        )

    click.echo("\n== Cruce Open Food Facts (EAN / Nutri-Score / NOVA / alergenos) ==")
    filas = conn.execute(
        "SELECT nombre, ean, nutri_score, nova, alergenos, off_match_score "
        "FROM productos WHERE off_match_score IS NOT NULL ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    if not filas:
        click.echo("  (aun sin cruce OFF; ejecuta menu-app-cruzar-off)")
    for r in filas:
        click.echo(
            f"  {r['nombre'][:38]:38s} ean={r['ean']} nutri={r['nutri_score']} "
            f"nova={r['nova']} score={r['off_match_score']} alerg={r['alergenos']}"
        )

    conn.close()


if __name__ == "__main__":
    main()
