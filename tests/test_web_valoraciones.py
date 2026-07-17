"""Tests de la interfaz web de valoración de recetas (Lote 12)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.web.app import crear_app


def _receta(conn, receta_id, titulo):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta) "
        "VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01')",
        (receta_id, f"manual://{receta_id}", titulo),
    )


def _plan_directo(conn, plan_id, recetas_comida):
    titulos = {
        r["id"]: r["titulo"]
        for r in conn.execute(
            f"SELECT id, titulo FROM recetas WHERE id IN "
            f"({', '.join('?' for _ in recetas_comida)})",
            recetas_comida,
        ).fetchall()
    }
    datos = {
        "factible": True, "coste_total": 10.0,
        "seleccion_comida": dict.fromkeys(recetas_comida, 1), "seleccion_cena": {},
        "recetas_info": {rid: {"titulo": titulos.get(rid, rid)} for rid in recetas_comida},
        "num_comensales": 2, "dias": 7,
    }
    conn.execute(
        "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, 1, '2026-01-01', ?)",
        (plan_id, json.dumps(datos)),
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


def test_pagina_sin_pendientes(client):
    c, _ = client
    r = c.get("/valoraciones")
    assert r.status_code == 200
    assert "Nada pendiente" in r.text


def test_pagina_muestra_pendiente_de_un_plan(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta(conn, "r1", "Sopa de puerro")
    _plan_directo(conn, "p1", ["r1"])
    conn.commit()
    conn.close()

    r = c.get("/valoraciones")
    assert r.status_code == 200
    assert "Sopa de puerro" in r.text


def test_receta_no_encontrada(client):
    c, _ = client
    r = c.get("/valoraciones/no-existe")
    assert r.status_code == 200
    assert "no encontrada" in r.text


def test_formulario_de_valoracion_tiene_los_baremos(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta(conn, "r1", "Sopa de puerro")
    conn.commit()
    conn.close()

    r = c.get("/valoraciones/r1")
    assert r.status_code == 200
    assert 'name="baremo__sabor"' in r.text
    assert 'name="baremo__frescura"' in r.text


def test_guardar_valoracion_completa_y_desaparece_de_la_cola(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta(conn, "r1", "Sopa de puerro")
    _plan_directo(conn, "p1", ["r1"])
    conn.commit()
    conn.close()

    r = c.post(
        "/valoraciones/r1",
        data={
            "baremo__sabor": "5", "baremo__frescura": "4",
            "ingredientes": "puerro\npatata", "metodo": "al vapor",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    r2 = c.get("/valoraciones")
    assert "Nada pendiente" in r2.text
    assert "Sopa de puerro" in r2.text  # ahora aparece en "ya valoradas"


def test_receta_afines_aparece_en_el_detalle(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta(conn, "r1", "Sopa de puerro")
    _receta(conn, "r2", "Crema de puerro")
    for rid in ("r1", "r2"):
        conn.execute(
            "INSERT INTO receta_ingredientes (receta_id, orden, texto_original, "
            "nombre_normalizado) VALUES (?, 1, 'puerro', 'puerro')",
            (rid,),
        )
    conn.commit()
    conn.close()

    r = c.get("/receta/r1")
    assert r.status_code == 200
    assert "Recetas afines" in r.text
    assert "Crema de puerro" in r.text
