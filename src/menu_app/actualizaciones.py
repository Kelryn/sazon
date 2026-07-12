"""Comprobacion de actualizaciones de la APP via GitHub Releases (Fase 11).

Consulta la API publica de releases del repo de binarios (no necesita token si el
repo es publico), compara la ultima version publicada con la instalada
(`version.__version__`) y, si hay una mas nueva, devuelve sus datos para avisar
al usuario con un enlace de descarga.

Por seguridad NO descarga ni ejecuta nada: solo informa y enlaza a la Release.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from .version import __version__

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
    version: str          # p.ej. "0.2.0"
    url_descarga: str     # instalador .exe (o la pagina de la release)
    url_pagina: str       # pagina de la release en GitHub
    notas: str            # cuerpo/changelog de la release


def hay_actualizacion(
    repo: str | None, version_actual: str = __version__, timeout: float = 6.0
) -> InfoActualizacion | None:
    """Devuelve la actualizacion disponible o None (si no hay, o falla la red).

    `repo` es "usuario/repositorio" (el repo publico de binarios). Sin repo, None.
    """
    if not repo or "/" not in repo:
        return None
    url = f"https://api.github.com/repos/{repo.strip()}/releases/latest"
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

    # Prefiere el instalador (.exe) entre los assets; si no, la pagina de la release.
    pagina = data.get("html_url", f"https://github.com/{repo}/releases/latest")
    descarga = pagina
    for asset in data.get("assets", []) or []:
        nombre = (asset.get("name") or "").lower()
        if nombre.endswith(".exe"):
            descarga = asset.get("browser_download_url", pagina)
            if "setup" in nombre or "install" in nombre:
                break  # el instalador es la mejor opcion
    return InfoActualizacion(
        version=tag.lstrip("v"),
        url_descarga=descarga,
        url_pagina=pagina,
        notas=(data.get("body") or "").strip(),
    )
