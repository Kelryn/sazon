"""Test del aviso de subida de precio en la página /compra (#118)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.web.app import crear_app


def _producto(conn, rid, nombre, precio):
    conn.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, subcategoria, "
        "precio_eur, precio_por_unidad, unidad_medida, cantidad_base_g_ml, disponible, "
        "en_oferta, url_producto, apto_receta, fecha_extraccion, fecha_actualizacion) "
        "VALUES (?, ?, 'Frescos', 'Verduras', ?, ?, 'kg', 500, 1, 0, ?, 1, '2026-01-01', '2026-01-01')",
        (rid, nombre, precio, precio, f"https://x/{rid}"),
    )


def _receta_simple(conn, receta_id, titulo, ingrediente_norm):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta) "
        "VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01')",
        (receta_id, f"manual://{receta_id}", titulo),
    )
    conn.execute(
        "INSERT INTO receta_ingredientes (receta_id, orden, texto_original, cantidad, "
        "unidad, nombre_normalizado, cantidad_metrica) VALUES (?, 1, ?, 500, 'g', ?, 500)",
        (receta_id, ingrediente_norm, ingrediente_norm),
    )
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES (?, ?, 'P1', '2026-01-01')",
        (ingrediente_norm, ingrediente_norm),
    )


def _guardar_plan_directo(conn, plan_id, receta_id, raciones=1.0, num_comensales=1):
    """Inserta un plan minimo directamente (evita depender de que el MILP
    encuentre viable un corpus de una sola receta)."""
    datos = {
        "factible": True, "raciones": {receta_id: raciones}, "num_comensales": num_comensales,
        "seleccion_comida": {receta_id: 1}, "seleccion_cena": {}, "dias": 1,
    }
    conn.execute(
        "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, 1, '2026-01-01', ?)",
        (plan_id, json.dumps(datos)),
    )
    conn.commit()


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "menu.db"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"almacenamiento:\n  db_path: {db.as_posix()}\nnum_comensales: 1\n"
        "backups_automaticos: false\n",
        encoding="utf-8",
    )
    return TestClient(crear_app(cfg)), db


def test_compra_muestra_aviso_de_subida_de_precio(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _producto(conn, "P1", "Cebolla dulce", 3.00)
    _receta_simple(conn, "r1", "Sopa de cebolla", "cebolla")
    conn.execute(
        "INSERT INTO precios_historico (retailer_product_id, fecha, precio_eur) VALUES "
        "('P1', '2026-01-01', 2.00), ('P1', '2026-02-01', 3.00)"
    )
    _guardar_plan_directo(conn, "p1", "r1")
    conn.close()

    r = c.get("/compra")
    assert r.status_code == 200
    # Rediseño Lote 11: la subida se muestra por fila, en su columna (↑ +N% rojo).
    assert 'class="lc-sube"' in r.text
    assert "↑ +50%" in r.text  # 2.00 → 3.00
    assert "Cebolla dulce" in r.text
