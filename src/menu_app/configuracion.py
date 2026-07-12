"""Carga de configuracion con overlay de usuario.

`config.yaml` es el fichero base, comentado y versionable. La UI web guarda los
cambios del usuario en `config.usuario.yaml` (mismo directorio), que se FUSIONA
por encima del base al cargar. Asi la pantalla de configuracion no machaca los
comentarios del YAML base y se puede "resetear" borrando el overlay.
"""

from __future__ import annotations

from pathlib import Path

import yaml

NOMBRE_OVERLAY = "config.usuario.yaml"

# Dias de la semana, en orden, tal como se usan en config y UI.
DIAS_SEMANA = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    with ruta.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _fusionar(base: dict, encima: dict) -> dict:
    """Fusion profunda de dicts: `encima` gana; los sub-dicts se combinan.
    Un valor None en `encima` ELIMINA esa clave (para retirar ajustes antiguos)."""
    out = dict(base)
    for k, v in encima.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _fusionar(out[k], v)
        else:
            out[k] = v
    return out


def ruta_overlay(config_path: str | Path) -> Path:
    return Path(config_path).parent / NOMBRE_OVERLAY


def cargar_config(config_path: str | Path) -> dict:
    """Config efectiva: config.yaml + (encima) config.usuario.yaml."""
    config_path = Path(config_path)
    return _fusionar(_leer_yaml(config_path), _leer_yaml(ruta_overlay(config_path)))


def guardar_overlay(config_path: str | Path, cambios: dict) -> None:
    """Fusiona `cambios` en el overlay del usuario y lo escribe a disco."""
    ruta = ruta_overlay(config_path)
    actual = _leer_yaml(ruta)
    nuevo = _fusionar(actual, cambios)
    with ruta.open("w", encoding="utf-8") as f:
        f.write("# Ajustes del usuario (editados desde la interfaz web).\n")
        f.write("# Se aplican POR ENCIMA de config.yaml; borra este fichero para resetear.\n")
        yaml.safe_dump(nuevo, f, allow_unicode=True, sort_keys=False)


def dias_batchcooking(cfg: dict) -> list[str]:
    """Dias marcados como batchcooking (laborales con cocinado en tanda)."""
    bc = cfg.get("batchcooking", {}) or {}
    dias = bc.get("dias", []) or []
    return [d for d in DIAS_SEMANA if d in dias]
