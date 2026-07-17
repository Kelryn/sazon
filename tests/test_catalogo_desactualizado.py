"""Tests de dias_desde_ultima_actualizacion (#116, catálogo programado)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from menu_app.almacenamiento.actualizar import dias_desde_ultima_actualizacion
from menu_app.almacenamiento.db import get_connection, init_db


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _producto(conn, rid, fecha):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion) "
        "VALUES (?, 'X', 'Frescos', 1, 0, ?, 1, ?, ?)",
        (rid, f"https://x/{rid}", fecha, fecha),
    )


def test_catalogo_vacio_devuelve_none(conn):
    assert dias_desde_ultima_actualizacion(conn) is None


def test_actualizado_hoy_devuelve_cero(conn):
    hoy = datetime.now(UTC).isoformat(timespec="seconds")
    _producto(conn, "P1", hoy)
    conn.commit()
    assert dias_desde_ultima_actualizacion(conn) == 0


def test_actualizado_hace_diez_dias(conn):
    hace_10 = (datetime.now(UTC) - timedelta(days=10)).isoformat(timespec="seconds")
    _producto(conn, "P1", hace_10)
    conn.commit()
    assert dias_desde_ultima_actualizacion(conn) == 10


def test_usa_el_producto_mas_reciente(conn):
    hace_10 = (datetime.now(UTC) - timedelta(days=10)).isoformat(timespec="seconds")
    hoy = datetime.now(UTC).isoformat(timespec="seconds")
    _producto(conn, "P1", hace_10)
    _producto(conn, "P2", hoy)
    conn.commit()
    assert dias_desde_ultima_actualizacion(conn) == 0
