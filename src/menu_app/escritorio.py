"""Programa de ESCRITORIO de Sazon: ventana nativa, sin terminal ni navegador.

En vez de abrir la interfaz en el navegador (que quedaba como "una terminal que abre
una web"), Sazon es un PROGRAMA con su propia ventana: arranca el servidor FastAPI en
un hilo interno y muestra la UI en una ventana nativa (pywebview -> WebView2/Edge, ya
integrado en Windows 10/11). El navegador externo SOLO se usa para el carrito de
Alcampo (Playwright).

Reutiliza la siembra de datos y el puerto libre del lanzador. Punto de entrada del
.exe (ver menu-app.spec).
"""

from __future__ import annotations

import os
import socket
import threading
import time

import uvicorn

from .lanzador import _dir_bundle, _dir_datos, _puerto_libre, _sembrar


def _arrancar_servidor(config_path, puerto: int) -> None:
    """Arranca uvicorn en ESTE hilo (secundario). Sin manejadores de señales, que
    solo funcionan en el hilo principal."""
    from menu_app.web.app import crear_app

    app = crear_app(config_path)
    config = uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    server.run()


def _esperar_servidor(puerto: int, timeout: float = 20.0) -> bool:
    """Espera a que el servidor acepte conexiones antes de abrir la ventana."""
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def iniciar_servidor_en_hilo(config_path, puerto: int) -> threading.Thread:
    hilo = threading.Thread(
        target=_arrancar_servidor, args=(config_path, puerto), daemon=True
    )
    hilo.start()
    _esperar_servidor(puerto)
    return hilo


def main() -> None:
    bundle = _dir_bundle()
    datos = _dir_datos()
    _sembrar(bundle, datos)
    os.chdir(datos)

    puerto = _puerto_libre()
    config_path = datos / "config.yaml"
    iniciar_servidor_en_hilo(config_path, puerto)

    import webview  # import diferido (dependencia de escritorio)

    from .marca import ESLOGAN, NOMBRE

    webview.create_window(
        f"{NOMBRE} — {ESLOGAN}",
        f"http://127.0.0.1:{puerto}/",
        width=1240,
        height=880,
        min_size=(900, 600),
    )
    # Bloquea hasta que se cierra la ventana; al volver, el proceso termina (el hilo
    # del servidor es daemon y muere con el).
    webview.start()


if __name__ == "__main__":
    main()
