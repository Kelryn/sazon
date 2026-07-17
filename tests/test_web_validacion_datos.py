"""Tests de la página /catalogo/validar (#120)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.web.app import crear_app


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


def test_sin_problemas(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion, "
        "precio_eur) VALUES ('P1','Sal','Frescos',1,0,'http://x',1,'2026-01-01','2026-01-01',1.0)"
    )
    conn.commit()
    conn.close()

    r = c.get("/catalogo/validar")
    assert r.status_code == 200
    assert "No se ha encontrado ningún dato anómalo" in r.text


def test_con_problemas(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion, "
        "precio_eur) VALUES ('P1','Producto raro','Frescos',1,0,'http://x',1,'2026-01-01',"
        "'2026-01-01',-3.0)"
    )
    conn.commit()
    conn.close()

    r = c.get("/catalogo/validar")
    assert r.status_code == 200
    assert "Producto raro" in r.text
    assert "precio negativo" in r.text
