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
import sys
import threading
import time
import traceback
from pathlib import Path

import uvicorn

# Import ABSOLUTO (no relativo): PyInstaller ejecuta este fichero como script
# principal ("__main__"), sin paquete padre, y un "from .lanzador import ..."
# revienta con "attempted relative import with no known parent package". Con
# pathex=["src"] en el .spec, "menu_app" es importable de forma absoluta.
from menu_app.lanzador import _dir_bundle, _dir_datos, _puerto_libre, _sembrar

_LOG = "sazon.log"


def _redirigir_salida(datos: Path) -> None:
    """En modo --noconsole (ventana), sys.stdout/stderr son None; uvicorn y cualquier
    print fallarian y tumbarian el hilo del servidor en silencio. Redirigimos a un log
    dentro de la carpeta de datos (sirve tambien para diagnosticar)."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        f = open(datos / _LOG, "a", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
    except Exception:  # noqa: BLE001
        import io

        sys.stdout = sys.stderr = io.StringIO()


def _arrancar_servidor(config_path, puerto: int, datos: Path) -> None:
    """Arranca uvicorn en ESTE hilo (secundario). Sin manejadores de señales (solo
    valen en el hilo principal). Cualquier error se registra en el log."""
    try:
        from menu_app.web.app import crear_app

        app = crear_app(config_path)
        config = uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        server.run()
    except Exception:  # noqa: BLE001 - se muestra en la ventana y se registra
        try:
            (datos / _LOG).open("a", encoding="utf-8").write(
                "\n=== ERROR arrancando el servidor ===\n" + traceback.format_exc()
            )
        except Exception:  # noqa: BLE001
            pass


def _esperar_servidor(puerto: int, timeout: float = 30.0) -> bool:
    """Espera a que el servidor acepte conexiones antes de abrir la ventana."""
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def iniciar_servidor_en_hilo(config_path, puerto: int, datos: Path | None = None) -> bool:
    """Lanza el servidor en un hilo y espera a que responda. Devuelve True si arranco."""
    threading.Thread(
        target=_arrancar_servidor, args=(config_path, puerto, datos or Path.cwd()), daemon=True
    ).start()
    return _esperar_servidor(puerto)


def _html_error(datos: Path) -> str:
    """Pagina de error (si el servidor no arranco) con la cola del log."""
    try:
        log = (datos / _LOG).read_text(encoding="utf-8")[-4000:]
    except Exception:  # noqa: BLE001
        log = "(sin detalles disponibles)"
    return (
        "<html><body style='font-family:sans-serif;padding:24px;background:#fbf8f2'>"
        "<h2>No se pudo iniciar Sazón</h2>"
        "<p>El servidor interno no arrancó. Detalles (también en "
        f"<code>{datos / _LOG}</code>):</p>"
        f"<pre style='background:#111;color:#9f9;padding:12px;border-radius:8px;"
        f"white-space:pre-wrap;font-size:12px'>{log}</pre></body></html>"
    )


def main() -> None:
    bundle = _dir_bundle()
    datos = _dir_datos()
    _redirigir_salida(datos)  # antes de nada: evita el crash por stdout/stderr None
    _sembrar(bundle, datos)
    os.chdir(datos)

    puerto = _puerto_libre()
    config_path = datos / "config.yaml"
    arranco = iniciar_servidor_en_hilo(config_path, puerto, datos)

    import webview  # import diferido (dependencia de escritorio)

    from menu_app.web.marca import ESLOGAN, NOMBRE  # absoluto (ver nota de import arriba)

    if arranco:
        webview.create_window(
            f"{NOMBRE} — {ESLOGAN}",
            f"http://127.0.0.1:{puerto}/",
            width=1240,
            height=880,
            min_size=(900, 600),
        )
    else:
        webview.create_window(f"{NOMBRE}", html=_html_error(datos), width=1000, height=700)
    # Bloquea hasta que se cierra la ventana; al volver, el proceso termina (el hilo
    # del servidor es daemon y muere con el).
    webview.start()


if __name__ == "__main__":
    main()
