from __future__ import annotations

import threading
import webbrowser

import click
import uvicorn

from .app import crear_app


@click.command()
@click.option("--config", "config_path", default="config.yaml")
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=int)
@click.option("--abrir/--no-abrir", default=True, help="Abrir el navegador al arrancar.")
def main(config_path: str, host: str, port: int, abrir: bool) -> None:
    """Arranca la interfaz web local del generador de menu (Fase 6)."""
    app = crear_app(config_path)
    url = f"http://{host}:{port}/"
    if abrir:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    click.echo(f"Interfaz web en {url}  (Ctrl+C para parar)")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
