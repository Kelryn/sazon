"""Diagnostico de errores LOCAL, opt-in (#81).

IMPORTANTE — honestidad sobre el alcance: Sazon es una app 100% local, sin backend
propio. Esto NO envia nada por red a ningun sitio (no hay servidor que lo reciba).
Es un registro de errores en un fichero LOCAL (%LOCALAPPDATA%\\Sazon\\errores.log),
desactivado por defecto, que el usuario activa si quiere guardar un historial de
fallos para diagnosticarlos el mismo o compartirlos manualmente si pide ayuda.
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _ruta_log() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    carpeta = Path(base) / "Sazon"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / "errores.log"


def registrar_error(origen: str, exc: BaseException, activo: bool) -> None:
    """Anota un error en el log LOCAL si la telemetria esta activada. `activo` lo
    decide el llamador (lee la config); por defecto en toda la app es False."""
    if not activo:
        return
    try:
        with _ruta_log().open("a", encoding="utf-8") as f:
            f.write(
                f"\n=== {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                f"[{origen}] ===\n"
            )
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except OSError:
        pass  # el diagnostico nunca debe romper la app


def leer_ultimos_errores(n: int = 20) -> str:
    """Ultimas lineas del log local, para mostrarlas en Configuracion."""
    ruta = _ruta_log()
    if not ruta.exists():
        return ""
    lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lineas[-n * 8 :])  # cada error ocupa varias lineas


def limpiar_log() -> None:
    ruta = _ruta_log()
    if ruta.exists():
        ruta.unlink()
