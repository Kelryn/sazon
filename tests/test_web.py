"""Tests de la interfaz web (FastAPI) con BD temporal, sin tocar la real."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from menu_app.web.app import crear_app


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "menu.db"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"almacenamiento:\n  db_path: {db.as_posix()}\n"
        "num_comensales: 2\ncomidas_por_dia: [comida, cena]\n",
        encoding="utf-8",
    )
    return TestClient(crear_app(cfg))


def test_home_responde_aunque_no_haya_plan(client):
    # BD vacia -> sin plan generado, pero la pagina se renderiza con el boton.
    r = client.get("/")
    assert r.status_code == 200
    assert "Sazón" in r.text
    assert "no hay ningún plan" in r.text
    assert "Generar plan nuevo" in r.text


def test_generar_plan_sin_recetas_reporta_infactible(client):
    # POST /generar con BD vacia -> plan guardado pero semana infactible.
    r = client.post("/generar", data={}, follow_redirects=True)
    assert r.status_code == 200
    assert "Sin menú factible" in r.text


def test_compra_sin_plan(client):
    r = client.get("/compra")
    assert r.status_code == 200
    assert "No hay plan generado" in r.text


def test_config_muestra_actualizaciones(client):
    r = client.get("/config")
    assert r.status_code == 200
    assert "Actualizaciones de la aplicación" in r.text
    assert "Versión instalada" in r.text


def test_actualizaciones_solo_boton(client, monkeypatch):
    # La seccion de actualizaciones tiene SOLO el boton (sin campo de repo).
    r = client.get("/config")
    assert r.status_code == 200
    assert "Buscar actualización" in r.text
    assert 'action="/actualizaciones/comprobar"' in r.text
    assert 'name="repo"' not in r.text  # ya no hay campo que rellenar
    # Al pulsar, si estamos al dia, avisa; si hay version, instala. Simulamos "al dia".
    from menu_app import actualizaciones
    monkeypatch.setattr("menu_app.web.app.hay_actualizacion", lambda *a, **k: None)
    r2 = client.post("/actualizaciones/comprobar", follow_redirects=True)
    assert r2.status_code == 200
    assert "última versión" in r2.text


def test_catalogo_page(client):
    r = client.get("/catalogo")
    assert r.status_code == 200
    assert "Descargar / actualizar catálogo" in r.text
    assert "Categorías a descargar" in r.text  # checkboxes de categorias
    assert "Ver y corregir el catálogo" in r.text  # visor
    # Regresion: el boton de actualizar NO puede apuntar a /catalogo/actualizar
    # (chocaria con /catalogo/{producto_id} -> "Producto no encontrado").
    assert 'action="/catalogo-actualizar"' in r.text
    assert 'action="/catalogo/actualizar"' not in r.text


def test_editar_producto(client, tmp_path):
    from menu_app.almacenamiento.db import get_connection, init_db

    db = get_connection(tmp_path / "menu.db")
    init_db(db)
    db.execute(
        "INSERT INTO productos (retailer_product_id, nombre, categoria, disponible, en_oferta, "
        "url_producto, apto_receta, fecha_extraccion, fecha_actualizacion, precio_eur) "
        "VALUES ('P1','Yuca al peso','Frescos',1,0,'http://x',1,'2026-01-01','2026-01-01',2.0)"
    )
    db.commit()
    db.close()
    r = client.get("/catalogo/P1")
    assert r.status_code == 200 and "Yuca al peso" in r.text
    r2 = client.post(
        "/catalogo/P1",
        data={"precio_eur": "3.5", "apto_receta": "1", "fibra_100g": "1.8"},
        follow_redirects=True,
    )
    assert r2.status_code == 200 and "actualizado" in r2.text


def test_pagina_recetas_y_editor(client):
    r = client.get("/recetas")
    assert r.status_code == 200
    assert "Nueva receta" in r.text

    # El editor de nueva receta trae el desplegable de catalogo y las filas.
    r_nueva = client.get("/recetas/nueva")
    assert r_nueva.status_code == 200
    assert "catalogo_ing" in r_nueva.text and "ing_nombre" in r_nueva.text

    # Alta con ingredientes estructurados.
    r2 = client.post(
        "/recetas/guardar",
        data={
            "titulo": "Lentejas de prueba",
            "raciones": "4",
            "ing_nombre": ["Lentejas", "Cebolla"],
            "ing_cantidad": ["300", "1"],
            "ing_unidad": ["g", "ud"],
            "plato_unico": "1",
        },
        follow_redirects=True,
    )
    assert r2.status_code == 200
    assert "Lentejas de prueba" in r2.text  # redirige al editor de la receta guardada
    assert "Nutrientes de una ración" in r2.text  # barras de nutrientes


def test_alta_invalida_muestra_error(client):
    r = client.post(
        "/recetas/guardar",
        data={"titulo": "Sin ingredientes", "raciones": "2", "ing_nombre": [""]},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Error" in r.text


def test_pagina_config_y_guardado(client, tmp_path):
    r = client.get("/config")
    assert r.status_code == 200
    assert "Configuración del menú" in r.text

    r2 = client.post(
        "/config",
        data={
            "num_comensales": "3", "kcal_por_comensal": "2200",
            "repeticiones_comida_semana": "2", "peso_palatabilidad": "5",
            "peso_cena_ligera_simple": "3", "peso_favorita": "4",
            "dias_bc": ["lun", "mar", "mie"],
        },
        follow_redirects=True,
    )
    assert r2.status_code == 200
    assert "guardada" in r2.text
    # El overlay se escribio y la pagina refleja los cambios.
    assert (tmp_path / "config.usuario.yaml").exists()
    r3 = client.get("/config")
    assert 'name="num_comensales" type="number" step="1" min="1" value="3"' in r3.text
    # Los pesos ahora son barras (input range) en %.
    assert 'type="range" name="sabor_pct"' in r3.text
