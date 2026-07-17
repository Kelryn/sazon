"""Cache de IndiceProductos por firma del catalogo apto (Lote 9, #90)."""

from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.matching import matcher as matcher_mod
from menu_app.matching.matcher import indice_productos_aptos_cacheado
from menu_app.matching.repositorio import MatchingRepository


def _insertar(conn, rid, nombre, fecha="2026-01-01"):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion) "
        "VALUES (?, ?, 'Frescos', 1, 0, ?, 1, ?, ?)",
        (rid, nombre, f"https://x/{rid}", fecha, fecha),
    )


@pytest.fixture(autouse=True)
def _limpiar_cache():
    matcher_mod._CACHE_INDICE["firma"] = None
    matcher_mod._CACHE_INDICE["indice"] = None
    yield
    matcher_mod._CACHE_INDICE["firma"] = None
    matcher_mod._CACHE_INDICE["indice"] = None


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    return c


def test_devuelve_el_mismo_indice_si_el_catalogo_no_cambia(conn):
    _insertar(conn, "P1", "Cebolla")
    conn.commit()
    repo = MatchingRepository(conn)

    i1 = indice_productos_aptos_cacheado(conn, repo.productos_aptos())
    i2 = indice_productos_aptos_cacheado(conn, repo.productos_aptos())
    assert i1 is i2  # mismo objeto: no se ha reconstruido


def test_reconstruye_si_cambia_el_catalogo(conn):
    _insertar(conn, "P1", "Cebolla")
    conn.commit()
    repo = MatchingRepository(conn)
    i1 = indice_productos_aptos_cacheado(conn, repo.productos_aptos())

    _insertar(conn, "P2", "Ajo", fecha="2026-02-01")
    conn.commit()
    i2 = indice_productos_aptos_cacheado(conn, repo.productos_aptos())

    assert i1 is not i2
    assert len(i2) == 2
