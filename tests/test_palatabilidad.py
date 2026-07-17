"""Tests de palatabilidad_bayesiana, incluida la mezcla con valoración personal (Lote 12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.optimizacion.palatabilidad import palatabilidad_bayesiana
from menu_app.recetas.valoraciones import guardar_valoracion


@pytest.fixture
def conn(tmp_path: Path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def _receta(conn, rid, titulo, rating=None, rating_count=None):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta, "
        "rating, rating_count) VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01', ?, ?)",
        (rid, f"manual://{rid}", titulo, rating, rating_count),
    )


def test_sin_valoracion_personal_se_comporta_como_antes(conn):
    _receta(conn, "r1", "Sopa", rating=4.0, rating_count=50)
    conn.commit()
    p = palatabilidad_bayesiana(conn)
    assert p["r1"] == pytest.approx(0.8, abs=0.02)


def test_valoracion_personal_mala_baja_la_palatabilidad(conn):
    _receta(conn, "r1", "Sopa", rating=4.5, rating_count=200)  # muy bien valorada en el sitio
    conn.commit()
    sin_personal = palatabilidad_bayesiana(conn)["r1"]

    guardar_valoracion(conn, "r1", {"sabor": 1, "se_repetiria": 1})  # pero a ti no te gustó
    con_personal = palatabilidad_bayesiana(conn)["r1"]

    assert con_personal < sin_personal


def test_valoracion_personal_buena_en_receta_sin_rating_del_sitio(conn):
    _receta(conn, "r1", "Receta manual sin rating")  # rating=None
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 5, "se_repetiria": 5})
    p = palatabilidad_bayesiana(conn)
    # Con rating=None, bayes usa la media global (neutral); la valoracion
    # personal (5/5=1.0) tira de eso hacia arriba.
    assert p["r1"] > 0.5


def test_receta_sin_ninguna_valoracion_no_se_ve_afectada(conn):
    _receta(conn, "r1", "Con rating", rating=3.0, rating_count=10)
    _receta(conn, "r2", "Sin valorar", rating=3.0, rating_count=10)
    conn.commit()
    guardar_valoracion(conn, "r1", {"sabor": 5})
    p = palatabilidad_bayesiana(conn)
    assert p["r1"] != p["r2"]  # r1 cambio, r2 no
