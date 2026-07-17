"""Tests de detección de descatalogados y re-match automático (#117)."""

from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.matching.descatalogados import productos_descatalogados, rematch_descatalogados


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _producto(conn, rid, nombre, fecha, apto=1, subcategoria=None):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, subcategoria, "
        "disponible, en_oferta, url_producto, apto_receta, fecha_extraccion, "
        "fecha_actualizacion) VALUES (?, ?, 'Frescos', ?, 1, 0, ?, ?, ?, ?)",
        (rid, nombre, subcategoria, f"https://x/{rid}", apto, fecha, fecha),
    )


def _mapeo(conn, ingrediente_norm, clave_matching, rid, fecha="2026-01-01"):
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES (?, ?, ?, ?)",
        (ingrediente_norm, clave_matching, rid, fecha),
    )


def test_sin_mapeos_no_hay_descatalogados(conn):
    _producto(conn, "P1", "Cebolla", "2026-02-01")
    conn.commit()
    assert productos_descatalogados(conn) == []


def test_producto_no_actualizado_en_la_ultima_pasada_se_detecta(conn):
    _producto(conn, "P1", "Cebolla vieja", "2026-01-01")  # no se toco en la ultima pasada
    _producto(conn, "P2", "Zanahoria", "2026-02-01")  # esta si es de la ultima pasada
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()

    descatalogados = productos_descatalogados(conn)
    assert len(descatalogados) == 1
    assert descatalogados[0]["rid_actual"] == "P1"


def test_producto_vigente_no_se_reporta(conn):
    _producto(conn, "P1", "Cebolla", "2026-02-01")
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()
    assert productos_descatalogados(conn) == []


def test_rematch_encuentra_sustituto_vigente(conn):
    _producto(conn, "P1", "Cebolla dulce 1 kg", "2026-01-01")  # descatalogada
    _producto(conn, "P2", "Cebolla dulce 2 kg", "2026-02-01")  # vigente, mismo texto
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()

    resumen = rematch_descatalogados(conn)
    assert resumen == {"revisados": 1, "reemparejados": 1}

    fila = conn.execute(
        "SELECT retailer_product_id FROM mapeo_ingr_producto WHERE ingrediente_norm='cebolla'"
    ).fetchone()
    assert fila["retailer_product_id"] == "P2"


def test_rematch_sin_sustituto_no_cambia_nada(conn):
    _producto(conn, "P1", "Cebolla dulce 1 kg", "2026-01-01")
    _producto(conn, "P2", "Zanahoria 1 kg", "2026-02-01")  # nada que ver
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()

    resumen = rematch_descatalogados(conn)
    assert resumen == {"revisados": 1, "reemparejados": 0}
    fila = conn.execute(
        "SELECT retailer_product_id FROM mapeo_ingr_producto WHERE ingrediente_norm='cebolla'"
    ).fetchone()
    assert fila["retailer_product_id"] == "P1"  # sin cambios


def test_rematch_sin_descatalogados_no_hace_nada(conn):
    _producto(conn, "P1", "Cebolla", "2026-02-01")
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()
    assert rematch_descatalogados(conn) == {"revisados": 0, "reemparejados": 0}
