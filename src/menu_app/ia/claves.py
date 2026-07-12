"""Gestion de claves de API (keyring) para el proveedor de LLM configurado.

Soporta varios proveedores (Gemini de Google, Claude de Anthropic). La clave
NUNCA se hardcodea ni se guarda en ficheros del proyecto: se guarda en el almacen
de credenciales del sistema (Windows Credential Manager) y se lee de ahi, o de la
variable de entorno correspondiente. Se pide al usuario en el primer arranque
(config_clave_cli.py).
"""

from __future__ import annotations

import os

import keyring

SERVICE = "menu-app"

# Config por proveedor: variables de entorno aceptadas, usuario en keyring,
# prefijos conocidos y longitud minima. `estricto=False` acepta cualquier clave
# suficientemente larga aunque no case el prefijo (Google cambia formatos:
# hay claves que empiezan por 'AIza' y otras por 'AQ'); la valida la propia API.
PROVEEDORES: dict[str, dict] = {
    "gemini": {
        "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "usuario": "gemini_api_key",
        "prefijos": ("AIza", "AQ"),
        "min_len": 20,
        "estricto": False,
    },
    "anthropic": {
        "env": ["ANTHROPIC_API_KEY"],
        "usuario": "anthropic_api_key",
        "prefijos": ("sk-ant-",),
        "min_len": 30,
        "estricto": True,
    },
}


def _cfg(proveedor: str) -> dict:
    if proveedor not in PROVEEDORES:
        raise ValueError(f"Proveedor de LLM desconocido: {proveedor!r}")
    return PROVEEDORES[proveedor]


def guardar_clave(proveedor: str, clave: str) -> None:
    keyring.set_password(SERVICE, _cfg(proveedor)["usuario"], clave)


def obtener_clave(proveedor: str) -> str | None:
    """Clave desde variable de entorno (si existe) o keyring, o None."""
    cfg = _cfg(proveedor)
    for var in cfg["env"]:
        if os.environ.get(var):
            return os.environ[var]
    return keyring.get_password(SERVICE, cfg["usuario"])


def borrar_clave(proveedor: str) -> None:
    try:
        keyring.delete_password(SERVICE, _cfg(proveedor)["usuario"])
    except keyring.errors.PasswordDeleteError:
        pass


def hay_clave(proveedor: str) -> bool:
    return bool(obtener_clave(proveedor))


def formato_valido(proveedor: str, clave: str) -> bool:
    """Comprobacion ligera para detectar un pegado fallido (p.ej. 1 caracter),
    no una validacion real de la clave (eso lo hace la API)."""
    cfg = _cfg(proveedor)
    if len(clave) < cfg["min_len"] or not clave.isprintable():
        return False
    if clave.startswith(cfg["prefijos"]):
        return True
    return not cfg["estricto"]  # gemini: acepta claves largas con otro prefijo
