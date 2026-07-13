"""Actualizaciones de la APP via GitHub Releases (Fase 11).

Consulta la API publica de releases del repo de binarios (fijo, no se pide al
usuario), compara la ultima version publicada con la instalada (`version.__version__`)
y, si hay una mas nueva, permite DESCARGARLA E INSTALARLA (lanza el instalador).

El repositorio es fijo (`REPO`): el usuario no configura nada, solo pulsa "Buscar
actualizaciones".
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from .version import __version__

# Repositorio PUBLICO de releases (FIJO; no se pide al usuario).
REPO = "Kelryn/sazon"

_USER_AGENT = "Sazon-Updater/1.0"
_NUM = re.compile(r"\d+")


def _parse_version(texto: str) -> tuple[int, ...]:
    """'v1.2.3' / '1.2.3-beta' -> (1, 2, 3). Ignora sufijos no numericos."""
    nums = _NUM.findall((texto or "").split("+")[0])
    return tuple(int(n) for n in nums[:3]) or (0,)


def es_mas_nueva(remota: str, local: str) -> bool:
    return _parse_version(remota) > _parse_version(local)


@dataclass
class InfoActualizacion:
    version: str          # p.ej. "0.4.0"
    url_descarga: str     # instalador .exe (o la pagina de la release)
    url_pagina: str       # pagina de la release en GitHub
    notas: str            # cuerpo/changelog de la release
    es_instalador: bool = False  # url_descarga apunta a un .exe instalable


def hay_actualizacion(
    version_actual: str = __version__, timeout: float = 6.0
) -> InfoActualizacion | None:
    """Devuelve la actualizacion disponible o None (si no hay, o falla la red).

    Consulta SIEMPRE el repo fijo `REPO`; no recibe parametros de configuracion.
    """
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    try:
        resp = httpx.get(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    tag = data.get("tag_name") or ""
    if not es_mas_nueva(tag, version_actual):
        return None

    pagina = data.get("html_url", f"https://github.com/{REPO}/releases/latest")
    descarga, es_instalador = pagina, False
    setup, cualquier_exe = None, None
    for asset in data.get("assets", []) or []:
        nombre = (asset.get("name") or "").lower()
        if nombre.endswith(".exe"):
            u = asset.get("browser_download_url")
            cualquier_exe = cualquier_exe or u
            if "setup" in nombre or "install" in nombre:
                setup = u
    if setup:
        descarga, es_instalador = setup, True
    elif cualquier_exe:
        descarga, es_instalador = cualquier_exe, True
    return InfoActualizacion(
        version=tag.lstrip("v"),
        url_descarga=descarga,
        url_pagina=pagina,
        notas=(data.get("body") or "").strip(),
        es_instalador=es_instalador,
    )


def _es_ejecutable_congelado() -> bool:
    """True si corremos como .exe empaquetado (PyInstaller), no desde codigo fuente."""
    return bool(getattr(sys, "frozen", False))


def descargar_instalador(info: InfoActualizacion, timeout: float = 300.0) -> Path:
    """Descarga el instalador a una carpeta temporal y devuelve su ruta."""
    destino = Path(tempfile.gettempdir()) / f"Sazon-Setup-{info.version}.exe"
    with httpx.stream(
        "GET",
        info.url_descarga,
        headers={"User-Agent": _USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    ) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return destino


def instalar(info: InfoActualizacion) -> tuple[bool, str]:
    """Descarga y LANZA el instalador (solo en el .exe). Devuelve (ok, mensaje).

    En modo codigo fuente no auto-instala (no hay .exe que reemplazar): informa y
    enlaza a la release.
    """
    if not info.es_instalador:
        return False, (
            f"La version {info.version} no trae instalador. Descargala en {info.url_pagina}"
        )
    if not _es_ejecutable_congelado():
        return False, (
            "Estas ejecutando Sazon desde el codigo fuente; la instalacion automatica "
            f"solo aplica al ejecutable. Novedades de la version {info.version}: {info.url_pagina}"
        )
    try:
        ruta = descargar_instalador(info)
    except Exception as e:  # noqa: BLE001
        return False, f"No se pudo descargar la actualizacion: {e}"
    try:
        os.startfile(str(ruta))  # type: ignore[attr-defined]  # lanza el instalador (Windows)
    except Exception as e:  # noqa: BLE001
        return False, f"Descargada en {ruta}, pero no pude abrir el instalador: {e}"
    return True, (
        f"Descargada la version {info.version}. Se ha abierto el instalador: sigue los "
        "pasos (la app se cerrara para actualizarse)."
    )
