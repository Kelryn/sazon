"""Tests del historial de planes y "repetir semana pasada" (#109)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.optimizacion.planes import cargar_plan
from menu_app.web.app import crear_app


def _receta_simple(conn, receta_id, titulo):
    conn.execute(
        "INSERT INTO recetas (id, url, fuente, titulo, raciones, rol, fecha_ingesta) "
        "VALUES (?, ?, 'es', ?, 2, 'principal', '2026-01-01')",
        (receta_id, f"manual://{receta_id}", titulo),
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


def test_historial_vacio(client):
    c, _ = client
    r = c.get("/historial")
    assert r.status_code == 200
    assert "Todavía no hay planes generados" in r.text


def test_historial_muestra_planes_generados(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta_simple(conn, "r1", "Sopa")
    conn.commit()
    conn.close()

    c.post("/generar", data={}, follow_redirects=True)
    r = c.get("/historial")
    assert r.status_code == 200
    assert "Ver semanas" in r.text


def test_repetir_semana_anade_una_semana_nueva(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta_simple(conn, "r1", "Sopa")
    conn.commit()
    conn.close()

    c.post("/generar", data={}, follow_redirects=True)
    r_hist = c.get("/historial")
    # Extrae el plan_id del enlace "Ver semanas".
    import re
    m = re.search(r'/historial/([^"]+)"', r_hist.text)
    assert m
    plan_id = m.group(1)

    conn = get_connection(db)
    _pid, semanas_antes = cargar_plan(conn)
    conn.close()
    n_antes = max(semanas_antes) if semanas_antes else 0

    r = c.post(
        "/repetir-semana",
        data={"origen_plan_id": plan_id, "origen_semana": 1},
        follow_redirects=False,
    )
    assert r.status_code == 303

    conn = get_connection(db)
    _pid2, semanas_despues = cargar_plan(conn)
    conn.close()
    assert max(semanas_despues) == n_antes + 1


def test_exportar_e_importar_plan(client):
    c, db = client
    conn = get_connection(db)
    init_db(conn)
    _receta_simple(conn, "r1", "Sopa")
    conn.commit()
    conn.close()

    c.post("/generar", data={}, follow_redirects=True)
    r_hist = c.get("/historial")
    import re
    m = re.search(r'/historial/([^"]+)"', r_hist.text)
    plan_id = m.group(1)

    r_export = c.get(f"/historial/{plan_id}/exportar.json")
    assert r_export.status_code == 200
    assert r_export.headers["content-type"].startswith("application/json")

    r_import = c.post(
        "/historial/importar",
        files={"fichero": ("plan.json", r_export.content, "application/json")},
        follow_redirects=False,
    )
    assert r_import.status_code == 303
    assert "plan-importado" in r_import.headers["location"]

    r_hist2 = c.get("/historial")
    assert r_hist2.text.count('href="/historial/plan') == 2  # el original + el importado


def test_importar_fichero_invalido_avisa(client):
    c, _ = client
    r = c.post(
        "/historial/importar",
        files={"fichero": ("plan.json", b"no es json", "application/json")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "historial" in r.headers["location"]
