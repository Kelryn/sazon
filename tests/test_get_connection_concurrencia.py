"""Regresión: get_connection()/_activar_wal reintenta si journal_mode=WAL choca
con otra conexión activando WAL a la vez sobre un fichero recién creado (Lote 10,
descubierto al añadir la tarea de fondo #116: dos init_db() concurrentes podían
fallar con "database is locked" sin llegar a reintentar, porque ese PRAGMA en
concreto no siempre respeta busy_timeout al cambiar de modo)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from menu_app.almacenamiento import db as db_mod
from menu_app.almacenamiento.db import get_connection


class _ConexionBloqueoTemporal:
    """Envoltorio: falla las primeras `fallos` veces que se intenta
    'PRAGMA journal_mode = WAL', luego deja pasar la llamada real."""

    def __init__(self, conn, fallos=2, error="database is locked"):
        self._conn = conn
        self._fallos = fallos
        self._error = error
        self.intentos = 0

    def execute(self, sql, *args, **kwargs):
        if sql.strip() == "PRAGMA journal_mode = WAL":
            self.intentos += 1
            if self.intentos <= self._fallos:
                raise sqlite3.OperationalError(self._error)
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, nombre):
        return getattr(self._conn, nombre)


def test_activar_wal_reintenta_si_esta_bloqueado(tmp_path: Path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "test.db")
    envoltorio = _ConexionBloqueoTemporal(conn, fallos=2)
    monkeypatch.setattr(db_mod.time, "sleep", lambda _s: None)  # no esperar de verdad

    db_mod._activar_wal(envoltorio)
    assert envoltorio.intentos == 3  # fallo, fallo, exito


def test_activar_wal_propaga_otros_errores(tmp_path: Path):
    conn = sqlite3.connect(tmp_path / "test.db")
    envoltorio = _ConexionBloqueoTemporal(conn, fallos=99, error="disk I/O error")
    try:
        db_mod._activar_wal(envoltorio)
        raise AssertionError("deberia haber propagado el error")
    except sqlite3.OperationalError as e:
        assert "disk I/O error" in str(e)


def test_get_connection_sigue_funcionando_normalmente(tmp_path: Path):
    conn = get_connection(tmp_path / "test.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    conn.close()
