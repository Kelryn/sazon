"""Tests del alta de recetas manuales, favoritas y peso por pieza."""

from __future__ import annotations

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.optimizacion.economia_recetas import _gramos_por_piezas
from menu_app.recetas.manual import (
    añadir_receta_manual,
    listar_favoritas,
    marcar_favorita,
)


@pytest.fixture
def conn(tmp_path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def test_anadir_receta_manual_clasifica_y_marca_favorita(conn):
    rid = añadir_receta_manual(
        conn,
        titulo="Lentejas de la abuela",
        raciones=4,
        ingredientes=["300 g de lentejas", "1 cebolla", "2 zanahorias"],
        es_favorita=True,
    )
    fila = conn.execute(
        "SELECT fuente, raciones, rol, es_batchcooking, es_favorita FROM recetas WHERE id = ?",
        (rid,),
    ).fetchone()
    assert fila["fuente"] == "manual"
    assert fila["raciones"] == 4
    assert fila["rol"] == "principal"
    assert fila["es_batchcooking"] == 1  # "lentejas" es batchcooking
    assert fila["es_favorita"] == 1
    # Los ingredientes se guardaron parseados.
    n = conn.execute(
        "SELECT COUNT(*) FROM receta_ingredientes WHERE receta_id = ?", (rid,)
    ).fetchone()[0]
    assert n == 3


def test_validaciones(conn):
    with pytest.raises(ValueError):
        añadir_receta_manual(conn, titulo="", raciones=2, ingredientes=["x"])
    with pytest.raises(ValueError):
        añadir_receta_manual(conn, titulo="X", raciones=0, ingredientes=["x"])
    with pytest.raises(ValueError):
        añadir_receta_manual(conn, titulo="X", raciones=2, ingredientes=[])


def test_marcar_y_listar_favoritas(conn):
    rid = añadir_receta_manual(conn, titulo="Sopa", raciones=2, ingredientes=["1 cebolla"])
    assert [f[0] for f in listar_favoritas(conn)] == []  # no favorita al crear
    assert marcar_favorita(conn, rid) is True
    assert [f[0] for f in listar_favoritas(conn)] == [rid]
    assert marcar_favorita(conn, rid, favorita=False) is True
    assert listar_favoritas(conn) == []
    assert marcar_favorita(conn, "inexistente") is False


def test_reañadir_misma_receta_no_duplica(conn):
    r1 = añadir_receta_manual(conn, titulo="Guiso", raciones=2, ingredientes=["1 cebolla"])
    r2 = añadir_receta_manual(conn, titulo="Guiso", raciones=3, ingredientes=["2 cebollas"])
    assert r1 == r2  # mismo id estable por titulo
    fila = conn.execute("SELECT raciones FROM recetas WHERE id = ?", (r1,)).fetchone()
    assert fila["raciones"] == 3  # se actualizo


@pytest.mark.parametrize(
    "nombre,unidad,cantidad,esperado",
    [
        ("cebolla", None, 1, 150),
        ("zanahorias", None, 2, 160),
        ("ajo", "dientes", 3, 15),
        ("huevo", "unidad", 2, 120),
        ("cosa rara", None, 1, None),  # sin peso conocido
    ],
)
def test_gramos_por_piezas(nombre, unidad, cantidad, esperado):
    assert _gramos_por_piezas(nombre, unidad, cantidad) == esperado
