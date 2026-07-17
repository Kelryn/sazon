"""Tests de la página web del asistente de sustituciones (#100)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from menu_app.web.app import crear_app


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "menu.db"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"almacenamiento:\n  db_path: {db.as_posix()}\nnum_comensales: 2\n",
        encoding="utf-8",
    )
    return TestClient(crear_app(cfg))


def test_pagina_sin_busqueda_muestra_formulario(client):
    r = client.get("/sustituciones")
    assert r.status_code == 200
    assert 'action="/sustituciones"' in r.text


def test_busqueda_con_resultado(client):
    r = client.get("/sustituciones", params={"q": "nata"})
    assert r.status_code == 200
    assert "leche evaporada" in r.text


def test_busqueda_sin_resultado(client):
    r = client.get("/sustituciones", params={"q": "unicornio de mar"})
    assert r.status_code == 200
    assert "No tengo sustituciones" in r.text
