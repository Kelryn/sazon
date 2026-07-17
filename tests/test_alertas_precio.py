"""Tests de avisos de subida de precio (#118)."""

from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.alertas_precio import subidas_de_precio
from menu_app.almacenamiento.db import get_connection, init_db


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _producto(conn, rid, nombre):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion) "
        "VALUES (?, ?, 'Frescos', 1, 0, ?, 1, '2026-01-01', '2026-01-01')",
        (rid, nombre, f"https://x/{rid}"),
    )


def _historico(conn, rid, fecha, precio):
    conn.execute(
        "INSERT INTO precios_historico (retailer_product_id, fecha, precio_eur) VALUES (?, ?, ?)",
        (rid, fecha, precio),
    )


def test_sube_por_encima_del_umbral_se_reporta(conn):
    _producto(conn, "P1", "Aceite de oliva")
    _historico(conn, "P1", "2026-01-01", 3.00)
    _historico(conn, "P1", "2026-02-01", 3.50)  # +16.7%
    conn.commit()

    avisos = subidas_de_precio(conn, umbral_pct=8.0)
    assert len(avisos) == 1
    assert avisos[0]["retailer_product_id"] == "P1"
    assert avisos[0]["subida_pct"] == pytest.approx(16.7, abs=0.1)


def test_subida_pequena_no_se_reporta(conn):
    _producto(conn, "P1", "Leche")
    _historico(conn, "P1", "2026-01-01", 1.00)
    _historico(conn, "P1", "2026-02-01", 1.02)  # +2%
    conn.commit()

    assert subidas_de_precio(conn, umbral_pct=8.0) == []


def test_bajada_de_precio_no_se_reporta(conn):
    _producto(conn, "P1", "Tomate")
    _historico(conn, "P1", "2026-01-01", 2.00)
    _historico(conn, "P1", "2026-02-01", 1.50)
    conn.commit()

    assert subidas_de_precio(conn, umbral_pct=8.0) == []


def test_un_solo_punto_de_historico_no_se_reporta(conn):
    _producto(conn, "P1", "Sal")
    _historico(conn, "P1", "2026-01-01", 1.00)
    conn.commit()

    assert subidas_de_precio(conn, umbral_pct=8.0) == []


def test_filtra_por_rids(conn):
    _producto(conn, "P1", "Aceite")
    _producto(conn, "P2", "Vinagre")
    _historico(conn, "P1", "2026-01-01", 2.00)
    _historico(conn, "P1", "2026-02-01", 3.00)
    _historico(conn, "P2", "2026-01-01", 1.00)
    _historico(conn, "P2", "2026-02-01", 2.00)
    conn.commit()

    avisos = subidas_de_precio(conn, rids=["P1"], umbral_pct=8.0)
    assert [a["retailer_product_id"] for a in avisos] == ["P1"]


def test_rids_vacio_no_devuelve_nada(conn):
    _producto(conn, "P1", "Aceite")
    _historico(conn, "P1", "2026-01-01", 1.00)
    _historico(conn, "P1", "2026-02-01", 2.00)
    conn.commit()

    assert subidas_de_precio(conn, rids=[], umbral_pct=8.0) == []


def test_ordena_por_mayor_subida_primero(conn):
    _producto(conn, "P1", "Poco")
    _producto(conn, "P2", "Mucho")
    _historico(conn, "P1", "2026-01-01", 1.00)
    _historico(conn, "P1", "2026-02-01", 1.10)  # +10%
    _historico(conn, "P2", "2026-01-01", 1.00)
    _historico(conn, "P2", "2026-02-01", 1.50)  # +50%
    conn.commit()

    avisos = subidas_de_precio(conn, umbral_pct=8.0)
    assert [a["retailer_product_id"] for a in avisos] == ["P2", "P1"]
