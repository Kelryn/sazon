"""CLI `menu-app-carrito`: envia la compra del plan al carrito de Alcampo.

Prototipo (ver ROADMAP.md D). Por defecto DRY-RUN (no toca el carrito). Para
anadir de verdad hay que pasar --confirmar, que es el visto bueno EXPLICITO del
usuario. La sesion se inicia a mano en la ventana del navegador; la app nunca
guarda la contrasena.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from ..almacenamiento.db import get_connection, init_db
from ..configuracion import cargar_config
from ..optimizacion.compra import lista_compra
from .alcampo import anadir_al_carrito, playwright_disponible

_AYUDA_PLAYWRIGHT = (
    "Falta el navegador automatizado (extra opcional 'playwright'). Instalalo con:\n"
    "    uv sync --extra playwright\n"
    "    uv run playwright install chromium"
)


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--plan", "plan_id", default=None, help="ID del plan (por defecto, el activo).")
@click.option(
    "--confirmar",
    is_flag=True,
    help="ANADE de verdad al carrito. Sin este flag va en dry-run (solo comprueba).",
)
@click.option("--headless", is_flag=True, help="Sin ventana (no recomendado para el login).")
@click.option("--limite", default=None, type=int, help="Prueba solo los primeros N productos.")
@click.option(
    "--paralelo",
    default=0,
    type=int,
    help="Nº de productos anadiendose a la vez (0 = todos a la vez, por defecto).",
)
@click.option(
    "--diagnostico",
    is_flag=True,
    help="Vuelca los botones del primer producto (para afinar los selectores de 'Anadir').",
)
@click.option(
    "--mantener-abierto",
    "mantener_abierto",
    default=0,
    type=int,
    help="Deja la ventana abierta N segundos al terminar (para revisar el carrito).",
)
@click.option(
    "--esperar-enter",
    is_flag=True,
    help="Esperar a que pulses ENTER tras el login en vez de autodetectarlo (respaldo).",
)
@click.option(
    "--sincronizar",
    is_flag=True,
    help="Si un producto ya esta en la cesta, ajusta a la cantidad EXACTA en vez de sumar.",
)
@click.option(
    "--vaciar-antes",
    "vaciar_antes",
    is_flag=True,
    help="Vacia la cesta entera antes de empezar a anadir.",
)
@click.option(
    "--reporte",
    "reporte_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Guarda un JSON con el resultado y los endpoints del carrito capturados.",
)
def main(
    config_path: Path,
    db_path: Path | None,
    plan_id: str | None,
    confirmar: bool,
    headless: bool,
    limite: int | None,
    paralelo: int,
    diagnostico: bool,
    mantener_abierto: int,
    esperar_enter: bool,
    sincronizar: bool,
    vaciar_antes: bool,
    reporte_path: Path | None,
) -> None:
    """Anade la compra del plan al carrito de compraonline.alcampo.es (prototipo)."""
    if not playwright_disponible():
        raise click.ClickException(_AYUDA_PLAYWRIGHT)

    cfg = cargar_config(config_path)
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(db_path)
    init_db(conn)
    compra = lista_compra(conn, plan_id, despensa=cfg.get("despensa"))
    conn.close()

    if not compra.lineas:
        raise click.ClickException("El plan no tiene lista de la compra (genera antes un menu).")

    click.echo(
        f"Plan {compra.plan_id or '(activo)'}: {len(compra.lineas)} productos, "
        f"total estimado {compra.total:.2f} €."
    )
    if confirmar:
        click.secho(
            "MODO REAL: se anadiran productos a TU carrito de Alcampo. La sesion la inicias "
            "tu en la ventana; la app no guarda tu contrasena.",
            fg="yellow",
        )
    else:
        click.echo("DRY-RUN: solo compruebo que cada ficha tiene boton de anadir (no toco el carrito).")

    res = anadir_al_carrito(
        compra.lineas, dry_run=not confirmar, headless=headless,
        limite=limite, diagnostico=diagnostico,
        mantener_abierto_ms=max(0, mantener_abierto) * 1000,
        esperar_enter=esperar_enter,
        paralelo=paralelo,
        sincronizar=sincronizar,
        vaciar_antes=vaciar_antes,
    )

    click.echo("")
    agotados = [l for l in res.lineas if l.detalle == "agotado"]
    fallidos = [l for l in res.lineas if not l.ok and l.detalle != "agotado"]
    click.echo(
        f"Sesion iniciada: {'si' if res.logueado else 'no'} | "
        f"lineas OK: {res.n_ok}/{len(res.lineas)} | "
        f"agotados: {len(agotados)} | fallidos: {len(fallidos)} | "
        f"endpoints de carrito capturados: {len(res.endpoints_carrito)}"
        + (f" | total cesta: {res.total_cesta}" if res.total_cesta else "")
    )
    if agotados:
        click.echo("Agotados (no disponibles en Alcampo): " + ", ".join(l.nombre for l in agotados))
    if fallidos:
        click.echo("Fallidos: " + "; ".join(f"{l.nombre} ({l.detalle})" for l in fallidos))
    if res.endpoints_carrito:
        ej = res.endpoints_carrito[0]
        click.echo(f"  Ejemplo de endpoint del carrito (Via 1 futura): {ej['metodo']} {ej['url']}")
    if res.botones_diagnostico:
        click.echo("\nBotones visibles del primer producto (para afinar selectores):")
        for b in res.botones_diagnostico:
            etiqueta = b.get("text") or b.get("aria") or "(sin texto)"
            click.echo(
                f"  - <{b['tag']}> '{etiqueta}'"
                + (f" aria='{b['aria']}'" if b.get("aria") else "")
                + (f" data-testid='{b['testid']}'" if b.get("testid") else "")
            )

    if reporte_path is not None:
        datos = {
            "dry_run": res.dry_run,
            "logueado": res.logueado,
            "lineas": [vars(l) for l in res.lineas],
            "endpoints_carrito": res.endpoints_carrito,
        }
        reporte_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        click.echo(f"Reporte guardado en {reporte_path}")


if __name__ == "__main__":
    main()
