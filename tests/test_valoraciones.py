"""Tests del sistema de valoración personal de recetas (Lote 12)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.recetas.valoraciones import (
    BAREMOS,
    detalle_de,
    guardar_valoracion,
    listar_recetas_valoradas,
    recetas_afines,
    recetas_para_valorar,
    valoraciones_de,
)


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _receta(conn, receta_id, titulo):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta) "
        "VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01')",
        (receta_id, f"manual://{receta_id}", titulo),
    )


def _ingrediente(conn, receta_id, nombre_normalizado, orden=1):
    conn.execute(
        "INSERT INTO receta_ingredientes (receta_id, orden, texto_original, "
        "nombre_normalizado) VALUES (?, ?, ?, ?)",
        (receta_id, orden, nombre_normalizado, nombre_normalizado),
    )


def _plan(conn, plan_id, semana, recetas_comida, creado="2026-01-01T00:00:00+00:00"):
    datos = {
        "factible": True, "coste_total": 10.0,
        "seleccion_comida": dict.fromkeys(recetas_comida, 1),
        "seleccion_cena": {},
        "recetas_info": {rid: {"titulo": rid} for rid in recetas_comida},
        "num_comensales": 2, "dias": 7,
    }
    conn.execute(
        "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, ?, ?, ?)",
        (plan_id, semana, creado, json.dumps(datos)),
    )


def test_baremos_tiene_los_pedidos_por_el_usuario():
    claves = {k for k, _ in BAREMOS}
    assert {"sabor", "frescura", "recepcion_estomacal"} <= claves


def test_sin_plan_no_hay_nada_que_valorar(conn):
    assert recetas_para_valorar(conn) == []


def test_receta_de_esta_semana_aparece_en_la_cola(conn):
    _receta(conn, "r1", "Sopa")
    _plan(conn, "p1", 1, ["r1"])
    conn.commit()
    pendientes = recetas_para_valorar(conn)
    assert [p["receta_id"] for p in pendientes] == ["r1"]


def test_receta_ya_valorada_no_vuelve_a_pedirse(conn):
    _receta(conn, "r1", "Sopa")
    _plan(conn, "p1", 1, ["r1"])
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 5})
    assert recetas_para_valorar(conn) == []


def test_receta_de_plan_anterior_tambien_cuenta(conn):
    _receta(conn, "r1", "Sopa")
    _receta(conn, "r2", "Guiso")
    _plan(conn, "p_anterior", 1, ["r1"], creado="2026-01-01T00:00:00+00:00")
    _plan(conn, "p_actual", 1, ["r2"], creado="2026-01-08T00:00:00+00:00")
    conn.commit()
    ids = {p["receta_id"] for p in recetas_para_valorar(conn)}
    assert ids == {"r1", "r2"}


def test_guardar_y_leer_valoracion(conn):
    _receta(conn, "r1", "Sopa")
    conn.commit()
    guardar_valoracion(
        conn, "r1", {"sabor": 5, "frescura": 3},
        ingredientes_destacados=["puerro"], metodo_destacado=["al vapor"],
    )
    assert valoraciones_de(conn, "r1") == {"sabor": 5, "frescura": 3}
    assert detalle_de(conn, "r1") == {"ingrediente": ["puerro"], "metodo": ["al vapor"]}


def test_revalorar_pisa_lo_anterior_sin_acumular(conn):
    _receta(conn, "r1", "Sopa")
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 2}, ingredientes_destacados=["cebolla"])
    guardar_valoracion(conn, "r1", {"sabor": 5}, ingredientes_destacados=["puerro"])
    assert valoraciones_de(conn, "r1") == {"sabor": 5}
    assert detalle_de(conn, "r1")["ingrediente"] == ["puerro"]


def test_ignora_baremo_desconocido_y_estrellas_invalidas(conn):
    _receta(conn, "r1", "Sopa")
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 5, "baremo_inventado": 3, "frescura": 9})
    assert valoraciones_de(conn, "r1") == {"sabor": 5}


def test_recetas_afines_por_ingredientes_compartidos(conn):
    _receta(conn, "r1", "Sopa de puerro")
    _receta(conn, "r2", "Crema de puerro y patata")  # comparte puerro y patata
    _receta(conn, "r3", "Tarta de manzana")  # nada que ver
    for rid, ings in {
        "r1": ["puerro", "patata", "caldo"],
        "r2": ["puerro", "patata", "nata"],
        "r3": ["manzana", "harina", "azucar"],
    }.items():
        for i, ing in enumerate(ings):
            _ingrediente(conn, rid, ing, i)
    conn.commit()

    afines = recetas_afines(conn, "r1")
    ids = [a["receta_id"] for a in afines]
    assert ids[0] == "r2"
    assert "r3" not in ids


def test_recetas_afines_sin_ingredientes_devuelve_vacio(conn):
    _receta(conn, "r1", "Sin ingredientes registrados")
    conn.commit()
    assert recetas_afines(conn, "r1") == []


def test_recetas_afines_prioriza_las_bien_valoradas(conn):
    _receta(conn, "r1", "Base")
    _receta(conn, "r2", "Afin sin valorar")
    _receta(conn, "r3", "Afin bien valorada")
    for rid in ("r1", "r2", "r3"):
        _ingrediente(conn, rid, "puerro", 0)
        _ingrediente(conn, rid, "patata", 1)
    conn.commit()
    guardar_valoracion(conn, "r3", {"sabor": 5, "se_repetiria": 5})

    afines = recetas_afines(conn, "r1")
    assert afines[0]["receta_id"] == "r3"  # empatan en similitud, gana la bien valorada


def test_listar_valoradas_con_busqueda(conn):
    _receta(conn, "r1", "Sopa de puerro")
    _receta(conn, "r2", "Guiso de lentejas")
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 4, "frescura": 3})
    guardar_valoracion(conn, "r2", {"sabor": 5})

    todas = listar_recetas_valoradas(conn)
    assert {r["id"] for r in todas} == {"r1", "r2"}
    solo_sopa = listar_recetas_valoradas(conn, q="sopa")
    assert [r["id"] for r in solo_sopa] == ["r1"]
