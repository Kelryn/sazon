"""Tests de la integración web de re-match de descatalogados (#117)."""

from __future__ import annotations

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.web.app import crear_app


def _producto(conn, rid, nombre, fecha):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion) "
        "VALUES (?, ?, 'Frescos', 1, 0, ?, 1, ?, ?)",
        (rid, nombre, f"https://x/{rid}", fecha, fecha),
    )


def _mapeo(conn, ingrediente_norm, clave_matching, rid):
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES (?, ?, ?, '2026-01-01')",
        (ingrediente_norm, clave_matching, rid),
    )


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "menu.db"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"almacenamiento:\n  db_path: {db.as_posix()}\nnum_comensales: 2\n"
        "backups_automaticos: false\n",
        encoding="utf-8",
    )
    return TestClient(crear_app(cfg)), db


def test_matching_page_muestra_aviso_de_descatalogados(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _producto(conn, "P1", "Cebolla vieja", "2026-01-01")
    _producto(conn, "P2", "Zanahoria", "2026-02-01")
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()
    conn.close()

    r = c.get("/matching")
    assert r.status_code == 200
    assert "Posibles descatalogados" in r.text


def test_boton_rematch_reemplaza_el_producto(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _producto(conn, "P1", "Cebolla dulce 1 kg", "2026-01-01")
    _producto(conn, "P2", "Cebolla dulce 2 kg", "2026-02-01")
    _mapeo(conn, "cebolla", "cebolla", "P1")
    conn.commit()
    conn.close()

    r = c.post("/matching/rematch-descatalogados", follow_redirects=False)
    assert r.status_code == 303
    assert "re-emparejados 1" in unquote(r.headers["location"])

    conn = get_connection(db)
    fila = conn.execute(
        "SELECT retailer_product_id FROM mapeo_ingr_producto WHERE ingrediente_norm='cebolla'"
    ).fetchone()
    conn.close()
    assert fila["retailer_product_id"] == "P2"
