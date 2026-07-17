"""Actualizaciones de la APP via GitHub Releases (Fase 11).

Consulta la API publica de releases del repo de binarios (fijo, no se pide al
usuario), compara la ultima version publicada con la instalada (`version.__version__`)
y, si hay una mas nueva, permite DESCARGARLA E INSTALARLA (lanza el instalador).

El repositorio es fijo (`REPO`): el usuario no configura nada, solo pulsa "Buscar
actualizaciones". Ademas:
- #75 auto-descarga en 2º plano: `pre_descargar()` se puede llamar en un hilo al
  detectar una version nueva, para que "Instalar" sea instantaneo despues.
- #76 changelog: `InfoActualizacion.notas` (cuerpo de la release) se muestra en la app.
- #77 canal beta: `canal="beta"` incluye pre-releases (la ultima, sea o no beta).
- #82 hash del instalador: si la release publica `SHA256SUMS.txt`, se verifica el
  hash del fichero descargado antes de lanzarlo (protege de una descarga corrupta
  o manipulada).
"""

from __future__ import annotations

import hashlib
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
    notas: str            # cuerpo/changelog de la release (#76)
    es_instalador: bool = False  # url_descarga apunta a un .exe instalable
    es_beta: bool = False        # la release es un pre-release de GitHub (#77)
    nombre_asset: str = ""       # nombre del asset descargable (para el hash, #82)
    url_checksums: str = ""      # URL de SHA256SUMS.txt si la release lo publica (#82)


def _release_desde_json(data: dict) -> InfoActualizacion:
    pagina = data.get("html_url", f"https://github.com/{REPO}/releases/latest")
    descarga, es_instalador, nombre_asset = pagina, False, ""
    setup, setup_nombre = None, ""
    cualquier_exe, cualquier_nombre = None, ""
    url_checksums = ""
    for asset in data.get("assets", []) or []:
        nombre = (asset.get("name") or "")
        low = nombre.lower()
        if low in ("sha256sums.txt", "checksums.txt", "sha256sums"):
            url_checksums = asset.get("browser_download_url", "")
        elif low.endswith(".exe"):
            u = asset.get("browser_download_url")
            if cualquier_exe is None:
                cualquier_exe, cualquier_nombre = u, nombre
            if "setup" in low or "install" in low:
                setup, setup_nombre = u, nombre
    if setup:
        descarga, es_instalador, nombre_asset = setup, True, setup_nombre
    elif cualquier_exe:
        descarga, es_instalador, nombre_asset = cualquier_exe, True, cualquier_nombre
    tag = data.get("tag_name") or ""
    return InfoActualizacion(
        version=tag.lstrip("v"),
        url_descarga=descarga,
        url_pagina=pagina,
        notas=(data.get("body") or "").strip(),
        es_instalador=es_instalador,
        es_beta=bool(data.get("prerelease")),
        nombre_asset=nombre_asset,
        url_checksums=url_checksums,
    )


def hay_actualizacion(
    version_actual: str = __version__, timeout: float = 6.0, canal: str = "estable",
) -> InfoActualizacion | None:
    """Devuelve la actualizacion disponible o None (si no hay, o falla la red).

    Consulta SIEMPRE el repo fijo `REPO`; no recibe parametros de configuracion.
    `canal="beta"` (#77) mira la release MAS RECIENTE (incluidas pre-releases);
    `canal="estable"` (por defecto) solo la ultima release estable.
    """
    if canal == "beta":
        url = f"https://api.github.com/repos/{REPO}/releases"
    else:
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
    if canal == "beta":
        lista = data if isinstance(data, list) else []
        if not lista:
            return None
        data = lista[0]  # la API ya las devuelve ordenadas por fecha, mas reciente primero
    info = _release_desde_json(data)
    if not es_mas_nueva(info.version, version_actual):
        return None
    return info


def _es_ejecutable_congelado() -> bool:
    """True si corremos como .exe empaquetado (PyInstaller), no desde codigo fuente."""
    return bool(getattr(sys, "frozen", False))


def _ruta_descarga(info: InfoActualizacion) -> Path:
    return Path(tempfile.gettempdir()) / f"Sazon-Setup-{info.version}.exe"


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _hash_esperado(info: InfoActualizacion, timeout: float = 15.0) -> str | None:
    """Descarga SHA256SUMS.txt (si la release lo publica) y busca la linea del
    asset instalado. Formato esperado: '<hash>  <nombre_fichero>' por linea (#82)."""
    if not info.url_checksums or not info.nombre_asset:
        return None
    try:
        resp = httpx.get(info.url_checksums, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    for linea in resp.text.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[-1].lstrip("*") == info.nombre_asset:
            return partes[0].lower()
    return None


def pre_descargar(info: InfoActualizacion, timeout: float = 300.0) -> Path:
    """Descarga el instalador (para hacerlo en 2º plano, #75) y devuelve su ruta.
    Reutilizable: si ya existe (mismo nombre/version), no vuelve a descargar."""
    destino = _ruta_descarga(info)
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    with httpx.stream(
        "GET", info.url_descarga, headers={"User-Agent": _USER_AGENT},
        timeout=timeout, follow_redirects=True,
    ) as r:
        r.raise_for_status()
        tmp = destino.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
        tmp.replace(destino)
    return destino


def instalar(info: InfoActualizacion, ruta_predescargada: Path | None = None) -> tuple[bool, str]:
    """Verifica el hash (si se publica) y LANZA el instalador (solo en el .exe).

    Si `ruta_predescargada` viene dada (de una descarga en 2º plano, #75), no
    vuelve a descargar. Devuelve (ok, mensaje).
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
        ruta = ruta_predescargada or pre_descargar(info)
    except Exception as e:  # noqa: BLE001
        return False, f"No se pudo descargar la actualizacion: {e}"

    esperado = _hash_esperado(info)
    if esperado:
        real = _sha256(ruta)
        if real.lower() != esperado.lower():
            try:
                ruta.unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
            return False, (
                "La descarga NO coincide con el hash publicado (posible descarga corrupta "
                "o manipulada). Por seguridad, NO se ha instalado. Vuelve a intentarlo."
            )

    try:
        os.startfile(str(ruta))  # type: ignore[attr-defined]  # lanza el instalador (Windows)
    except Exception as e:  # noqa: BLE001
        return False, f"Descargada en {ruta}, pero no pude abrir el instalador: {e}"
    verificado = " (hash verificado)" if esperado else ""
    return True, (
        f"Descargada la version {info.version}{verificado}. Se ha abierto el instalador: "
        "sigue los pasos (la app se cerrara para actualizarse)."
    )
