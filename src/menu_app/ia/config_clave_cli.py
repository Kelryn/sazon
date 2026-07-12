from __future__ import annotations

from pathlib import Path

import click
import yaml

from .claves import borrar_clave, formato_valido, guardar_clave, hay_clave


def _proveedor_config(config_path: Path) -> str:
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("ia", {}) or {}).get("proveedor", "gemini")
    return "gemini"


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option(
    "--proveedor",
    default=None,
    help="gemini | anthropic. Por defecto, el de config.yaml (ia.proveedor).",
)
@click.option("--borrar", is_flag=True, help="Elimina la clave guardada del proveedor.")
def main(config_path: Path, proveedor: str | None, borrar: bool) -> None:
    """Guarda tu clave de API (Gemini o Anthropic) en el almacen de credenciales del sistema.

    La clave se pide de forma oculta y se guarda con keyring (Windows Credential
    Manager); NO se muestra por pantalla ni se guarda en ningun fichero.
    """
    proveedor = proveedor or _proveedor_config(config_path)

    if borrar:
        borrar_clave(proveedor)
        click.echo(f"Clave de '{proveedor}' eliminada.")
        return

    donde = {
        "gemini": "Google AI Studio (aistudio.google.com/app/apikey)",
        "anthropic": "console.anthropic.com (empieza por 'sk-ant-')",
    }.get(proveedor, "")
    click.echo(f"Proveedor: {proveedor}. Consigue la clave en {donde}.")

    if hay_clave(proveedor) and not click.confirm("Ya hay una clave guardada. ¿Reemplazarla?"):
        return

    clave = click.prompt("Pega tu clave de API", hide_input=True).strip()
    if not clave:
        click.echo("No se guardo nada (clave vacia).")
        return
    if not formato_valido(proveedor, clave):
        click.echo(
            "Eso no parece una clave valida para este proveedor.\n"
            "Probablemente el pegado no funciono: en PowerShell usa CLIC DERECHO o "
            "Ctrl+Shift+V (Ctrl+V NO pega en una entrada oculta). No se guardo nada."
        )
        return
    guardar_clave(proveedor, clave)
    click.echo("Clave guardada de forma segura. Ya puedes usar --con-llm.")


if __name__ == "__main__":
    main()
