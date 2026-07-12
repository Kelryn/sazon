from __future__ import annotations

from pathlib import Path

import click

from ..almacenamiento.db import get_connection, init_db
from ..configuracion import cargar_config
from .nutrientes import resumen_legible
from .servicio import ResultadoMenu, generar_menu
from .solver import MenuOptimizado, RecetaOpt


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--batchcooking",
    is_flag=True,
    help="Elige solo recetas aptas para batchcooking (cocinar en tanda).",
)
@click.option(
    "--incluir-todo",
    is_flag=True,
    help="No filtra por rol: incluye postres, desayunos y guarniciones como comidas.",
)
def main(config_path: Path, db_path: Path | None, batchcooking: bool, incluir_todo: bool) -> None:
    """Genera el menu semanal optimo (coste minimo con nutrientes en banda) — Fase 5."""
    cfg = cargar_config(config_path)
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))

    conn = get_connection(db_path)
    init_db(conn)
    res = generar_menu(conn, cfg, batchcooking=batchcooking, incluir_todo=incluir_todo)
    n_comidas = res.dias * len(cfg.get("comidas_por_dia", ["comida", "cena"]) or ["comida", "cena"])
    click.echo(
        f"Comensales: {res.num_comensales} | dias: {res.dias} (comida + cena = {n_comidas} comidas) | "
        f"ingesta cubierta por el menu: {res.fraccion_ingesta * 100:.0f}% del dia | "
        f"recetas utilizables: {res.n_utilizables} (descartadas {res.descartadas_cobertura} por baja "
        f"cobertura, {res.descartadas_rol} por no ser plato principal)"
    )
    click.echo("Objetivos nutricionales de la semana (comida+cena):")
    click.echo(resumen_legible(res.bandas))
    _mostrar(res.menu, res.recetas, res.bandas)
    conn.close()


def _mostrar(menu: MenuOptimizado, recetas: dict[str, RecetaOpt], bandas: list) -> None:
    if not menu.factible:
        click.echo(f"\n[!] No hay menu factible: {menu.motivo}.")
        click.echo(
            "   Con el corpus de recetas actual no se pueden cumplir las bandas "
            "(tipicamente falta proteina). Solucion: ampliar el corpus de recetas "
            "y mejorar la cobertura del matching."
        )
        return
    por_id = recetas
    click.echo(f"\n=== MENU (coste total semana: {menu.coste_total:.2f} €) ===")

    def _listar(titulo, seleccion):
        click.echo(f"\n-- {titulo} --")
        for rid, n in sorted((seleccion or {}).items(), key=lambda x: -x[1]):
            r = por_id[rid]
            fav = " ★FAV" if r.es_favorita else ""
            click.echo(
                f"  {n}x  {r.titulo[:44]:44s}{fav:5s}  ({r.coste_racion:.2f} €/rac, "
                f"palat {r.palatabilidad:.2f}, cena {r.aptitud_cena:.2f})"
            )

    if menu.seleccion_comida is not None:
        _listar("COMIDAS (mediodia)", menu.seleccion_comida)
        _listar("CENAS (ligeras y sencillas, nunca batchcooking)", menu.seleccion_cena)
    else:
        _listar("COMIDAS", menu.seleccion)
    click.echo("\nNutrientes del menu vs objetivo:")
    deficit = menu.deficit_blando or {}
    for b in bandas:
        val = menu.nutricion_total.get(b.nutriente, 0.0)
        lo = f"{b.minimo:.0f}" if b.minimo is not None else "—"
        hi = f"{b.maximo:.0f}" if b.maximo is not None else "—"
        marca = f"  [!] {deficit[b.nutriente]:.0f} por debajo del suelo" if b.nutriente in deficit else ""
        click.echo(f"  {b.nutriente:14s} {val:>8.0f} {b.unidad}  (objetivo {lo}..{hi}){marca}")
    if deficit:
        click.echo(
            "\n[!] Deficit en suelos blandos (fibra): el dato de fibra apenas viene en las "
            "etiquetas de Alcampo, no es que el menu no lleve fibra. Mejorable ampliando la "
            "cobertura del dato (estimacion de fibra para productos sin etiqueta)."
        )


if __name__ == "__main__":
    main()
