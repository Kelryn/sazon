"""Copias de seguridad de los datos del usuario (#80): BD, config.usuario.yaml y
planes. Deterministas, locales, sin red. Se guardan junto a la BD en una carpeta
`backups/`, con nombre por fecha, y se limitan a las N mas recientes.
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_BACKUPS_DEFECTO = 10


@dataclass
class Backup:
    ruta: Path
    fecha: str  # ISO, extraida del nombre del fichero
    tamano_kb: float


def _carpeta_backups(db_path: Path) -> Path:
    carpeta = db_path.parent / "backups"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def crear_backup(db_path: Path, config_usuario_path: Path | None = None,
                  max_backups: int = MAX_BACKUPS_DEFECTO) -> Path | None:
    """Crea un .zip con la BD y config.usuario.yaml (si existe). Devuelve la ruta
    del backup creado, o None si no habia BD que respaldar. Purga los mas antiguos
    por encima de `max_backups`."""
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    carpeta = _carpeta_backups(db_path)
    # Microsegundos en el nombre: dos backups creados muy seguidos (p.ej. el de
    # seguridad justo antes de restaurar) no deben colisionar y sobrescribirse.
    marca = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    # A prueba de colisiones: en Windows el reloj tiene granularidad gruesa y dos
    # backups muy seguidos (el de seguridad justo antes de restaurar) pueden caer
    # en la misma marca de microsegundos. Si el nombre ya existe, se añade un
    # sufijo -N para no sobrescribir el anterior.
    destino = carpeta / f"sazon-backup-{marca}.zip"
    contador = 2
    while destino.exists():
        destino = carpeta / f"sazon-backup-{marca}-{contador}.zip"
        contador += 1
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(db_path, arcname="menu.db")
        if config_usuario_path and Path(config_usuario_path).exists():
            z.write(config_usuario_path, arcname="config.usuario.yaml")
    _purgar_antiguos(carpeta, max_backups)
    return destino


def _purgar_antiguos(carpeta: Path, max_backups: int) -> None:
    backups = sorted(carpeta.glob("sazon-backup-*.zip"), key=lambda p: p.name, reverse=True)
    for viejo in backups[max_backups:]:
        try:
            viejo.unlink()
        except OSError:
            pass


def listar_backups(db_path: Path) -> list[Backup]:
    carpeta = _carpeta_backups(db_path)
    out = []
    for p in sorted(carpeta.glob("sazon-backup-*.zip"), reverse=True):
        marca = p.stem.replace("sazon-backup-", "")
        try:
            fecha = datetime.strptime(marca, "%Y%m%d-%H%M%S-%f").isoformat(timespec="seconds")
        except ValueError:
            fecha = marca
        out.append(Backup(ruta=p, fecha=fecha, tamano_kb=round(p.stat().st_size / 1024, 1)))
    return out


def restaurar_backup(backup_zip: Path, db_path: Path, config_usuario_path: Path | None = None) -> None:
    """Restaura BD (y config.usuario.yaml si estaba en el zip) desde un backup.
    Hace una copia de seguridad del estado ACTUAL antes de sobrescribir (por si acaso)."""
    db_path = Path(db_path)
    crear_backup(db_path, config_usuario_path)  # red de seguridad antes de restaurar
    with zipfile.ZipFile(backup_zip, "r") as z:
        with z.open("menu.db") as origen, open(db_path, "wb") as dest:
            shutil.copyfileobj(origen, dest)
        if config_usuario_path and "config.usuario.yaml" in z.namelist():
            with z.open("config.usuario.yaml") as origen, open(config_usuario_path, "wb") as dest:
                shutil.copyfileobj(origen, dest)
