"""Tests de validación de datos del catálogo (#120)."""

from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.almacenamiento.validacion_datos import validar_datos


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _base(conn, rid, **extra):
    cols = {
        "retailer_product_id": rid, "nombre": f"Producto {rid}", "categoria": "Frescos",
        "disponible": 1, "en_oferta": 0, "url_producto": f"https://x/{rid}",
        "apto_receta": 1, "fecha_extraccion": "2026-01-01", "fecha_actualizacion": "2026-01-01",
    }
    cols.update(extra)
    campos = ", ".join(cols)
    marcadores = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO productos ({campos}) VALUES ({marcadores})", list(cols.values()))


def test_sin_problemas_no_reporta_nada(conn):
    _base(conn, "P1", precio_eur=2.0, energia_kcal_100g=100)
    conn.commit()
    assert validar_datos(conn) == []


def test_precio_negativo(conn):
    _base(conn, "P1", precio_eur=-1.0)
    conn.commit()
    problemas = validar_datos(conn)
    assert len(problemas) == 1
    assert "precio negativo" in problemas[0]["problema"]


def test_oferta_mas_cara_que_el_precio_normal(conn):
    _base(conn, "P1", precio_eur=2.0, en_oferta=1, precio_oferta=3.0)
    conn.commit()
    problemas = validar_datos(conn)
    assert any("oferta" in p["problema"] for p in problemas)


def test_energia_imposible(conn):
    _base(conn, "P1", energia_kcal_100g=950)
    conn.commit()
    problemas = validar_datos(conn)
    assert any("energía imposible" in p["problema"] for p in problemas)


def test_macros_suman_mas_de_100g(conn):
    _base(conn, "P1", proteinas_100g=50, hidratos_100g=40, grasas_100g=30)
    conn.commit()
    problemas = validar_datos(conn)
    assert any("macros suman" in p["problema"] for p in problemas)


def test_fibra_mayor_que_hidratos(conn):
    _base(conn, "P1", fibra_100g=10.0, hidratos_100g=2.0)
    conn.commit()
    problemas = validar_datos(conn)
    assert any("fibra" in p["problema"] for p in problemas)


def test_nutriente_negativo(conn):
    _base(conn, "P1", grasas_100g=-5.0)
    conn.commit()
    problemas = validar_datos(conn)
    assert any("nutriente negativo" in p["problema"] for p in problemas)
