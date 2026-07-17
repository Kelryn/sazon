"""Tests de sustitucion de agotados (#53) y ofertas (#57/#59) en la lista de la compra."""

from __future__ import annotations

import json

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.optimizacion.compra import lista_compra


def _producto(conn, rid, nombre, categoria, subcategoria, precio=1.0, base_g=500,
              disponible=1, en_oferta=0, precio_oferta=None, apto=1):
    conn.execute(
        """INSERT INTO productos (retailer_product_id, nombre, categoria, subcategoria,
            precio_eur, precio_por_unidad, unidad_medida, cantidad_base_g_ml, disponible,
            en_oferta, precio_oferta, url_producto, apto_receta, fecha_extraccion,
            fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?, 'kg', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rid, nombre, categoria, subcategoria, precio, precio, base_g, disponible,
         en_oferta, precio_oferta, f"https://x/{rid}", apto, "2026-01-01", "2026-01-01"),
    )


def _receta_simple(conn, receta_id, titulo, ingrediente_norm, texto):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta) "
        "VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01')",
        (receta_id, f"manual://{receta_id}", titulo),
    )
    conn.execute(
        "INSERT INTO receta_ingredientes (receta_id, orden, texto_original, cantidad, "
        "unidad, nombre_normalizado, cantidad_metrica) VALUES (?, 1, ?, 500, 'g', ?, 500)",
        (receta_id, texto, ingrediente_norm),
    )


def _guardar_plan_directo(conn, plan_id, receta_id, raciones, num_comensales=1):
    """Inserta un plan minimo directamente (evita depender de que el MILP encuentre
    viable un corpus de una sola receta; lista_compra solo necesita raciones+comensales)."""
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
def conn(tmp_path):
    c = get_connection(tmp_path / "t.db")
    init_db(c)
    return c


def test_sustituye_por_producto_de_la_misma_subcategoria(conn):
    _producto(conn, "P1", "Cebolla dulce 1 kg", "Frescos", "Verduras", disponible=0)
    _producto(conn, "P2", "Cebolla malla 2 kg", "Frescos", "Verduras", disponible=1)
    _producto(conn, "P3", "Cebolla granulada 60 g", "Alimentación", "Especias", disponible=1)
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES ('cebolla', 'cebolla', 'P1', '2026-01-01')"
    )
    _receta_simple(conn, "r1", "Receta de sopa", "cebolla", "500 g de cebolla")
    conn.commit()
    _guardar_plan_directo(conn, "p1", "r1", raciones=1.0)

    compra = lista_compra(conn, "p1")
    linea = next((ln for ln in compra.lineas if ln.nombre_original == "Cebolla dulce 1 kg"), None)
    assert linea is not None, "debe sustituir el producto agotado"
    assert linea.producto_id == "P2"  # la de la MISMA subcategoria, no la de especias
    assert linea.sustituido is True


def test_sin_alternativa_en_categoria_reporta_agotado(conn):
    _producto(conn, "P1", "Cebolla dulce 1 kg", "Frescos", "Verduras", disponible=0)
    _producto(conn, "P3", "Cebolla granulada 60 g", "Alimentación", "Especias", disponible=1)
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES ('cebolla', 'cebolla', 'P1', '2026-01-01')"
    )
    _receta_simple(conn, "r1", "Receta de sopa", "cebolla", "500 g de cebolla")
    conn.commit()
    _guardar_plan_directo(conn, "p1", "r1", raciones=1.0)

    compra = lista_compra(conn, "p1")
    assert "Cebolla dulce 1 kg" in compra.agotados_sin_sustituto
    assert not any(ln.nombre == "Cebolla granulada 60 g" for ln in compra.lineas)


def test_oferta_reduce_precio_y_suma_ahorro(conn):
    _producto(conn, "P1", "Tomate frito 500 g", "Alimentación", "Salsas",
              precio=1.50, en_oferta=1, precio_oferta=1.00)
    conn.execute(
        "INSERT INTO mapeo_ingr_producto (ingrediente_norm, clave_matching, "
        "retailer_product_id, fecha) VALUES ('tomate', 'tomate', 'P1', '2026-01-01')"
    )
    _receta_simple(conn, "r1", "Receta de pasta", "tomate", "500 g de tomate")
    conn.commit()
    _guardar_plan_directo(conn, "p1", "r1", raciones=1.0)

    compra = lista_compra(conn, "p1")
    linea = compra.lineas[0]
    assert linea.en_oferta is True
    assert linea.precio_unidad == 1.00
    assert linea.ahorro == pytest.approx(0.50, abs=0.01)
    assert compra.ahorro_total == pytest.approx(0.50, abs=0.01)
