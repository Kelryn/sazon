"""Punto de entrada del EJECUTABLE (.exe) — Fase 8.

Cuando la app va empaquetada con PyInstaller, el codigo corre desde una carpeta
temporal de solo lectura (sys._MEIPASS). Este lanzador:

1. Resuelve una carpeta de DATOS escribible (junto al .exe o en %LOCALAPPDATA%).
2. Siembra ahi el config.yaml y el catalogo (data/menu.db) desde el bundle la
   primera vez, si no existen.
3. Fija esa carpeta como directorio de trabajo (para que las rutas relativas de
   la app —data/, .cache/, config.usuario.yaml— funcionen y sean escribibles).
4. Elige un puerto libre, arranca el servidor y abre el navegador.

En desarrollo (no congelado) se comporta como el servidor normal sobre el CWD.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn


def _congelado() -> bool:
    return getattr(sys, "frozen", False)


def _dir_bundle() -> Path:
    """Carpeta con los recursos empaquetados (o la raiz del repo en desarrollo)."""
    if _congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def _dir_datos() -> Path:
    """Carpeta escribible para config.usuario.yaml, data/ y .cache/."""
    if not _congelado():
        return Path.cwd()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    destino = Path(base) / "Sazon"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _sembrar(bundle: Path, datos: Path) -> None:
    """Copia config.yaml y el catalogo del bundle a la carpeta de datos (1ª vez)."""
    cfg = datos / "config.yaml"
    if not cfg.exists() and (bundle / "config.yaml").exists():
        shutil.copy2(bundle / "config.yaml", cfg)
    db_dest = datos / "data" / "menu.db"
    db_src = bundle / "data" / "menu.db"
    if not db_dest.exists() and db_src.exists():
        db_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_src, db_dest)


def _puerto_libre(preferido: int = 8137) -> int:
    for puerto in (preferido, 8138, 8139, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", puerto))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferido


def main() -> None:
    bundle = _dir_bundle()
    datos = _dir_datos()
    _sembrar(bundle, datos)
    os.chdir(datos)

    # Import diferido: tras fijar el CWD y con el bundle en el path.
    from menu_app.web.app import crear_app

    puerto = _puerto_libre()
    url = f"http://127.0.0.1:{puerto}/"
    app = crear_app(datos / "config.yaml")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Sazon — tu menu semanal en {url}  (cierra esta ventana para salir)")
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")


if __name__ == "__main__":
    main()
