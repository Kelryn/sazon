"""Tests del runner de migraciones de esquema (Lote 9, #84)."""

from __future__ import annotations

from pathlib import Path

from menu_app.almacenamiento import db as db_mod
from menu_app.almacenamiento.db import get_connection, init_db


def test_bd_nueva_queda_en_la_ultima_version(tmp_path: Path):
    conn = get_connection(tmp_path / "test.db")
    init_db(conn)
    assert db_mod._version_guardada(conn) == db_mod.SCHEMA_VERSION


def test_migracion_pendiente_se_ejecuta_una_sola_vez(tmp_path: Path, monkeypatch):
    conn = get_connection(tmp_path / "test.db")
    init_db(conn)  # BD "antigua", ya en SCHEMA_VERSION

    llamadas = []
    monkeypatch.setitem(db_mod._MIGRACIONES, db_mod.SCHEMA_VERSION + 1, llamadas.append)
    monkeypatch.setattr(db_mod, "SCHEMA_VERSION", db_mod.SCHEMA_VERSION + 1)

    init_db(conn)  # ahora hay una migracion pendiente: debe ejecutarse
    assert len(llamadas) == 1

    init_db(conn)  # ya esta al dia: no debe repetirse
    assert len(llamadas) == 1
    assert db_mod._version_guardada(conn) == db_mod.SCHEMA_VERSION


def test_migraciones_se_aplican_en_orden(tmp_path: Path, monkeypatch):
    conn = get_connection(tmp_path / "test.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO meta (clave, valor) VALUES ('schema_version', '0')")
    conn.commit()

    orden = []
    monkeypatch.setattr(
        db_mod,
        "_MIGRACIONES",
        {2: lambda c: orden.append(2), 1: lambda c: orden.append(1)},
    )

    db_mod._aplicar_migraciones(conn)
    assert orden == [1, 2]
