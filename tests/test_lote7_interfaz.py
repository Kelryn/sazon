"""Tests del Lote 7 (interfaz): tema, buscador, dashboard, impresion, onboarding."""

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


def test_toggle_de_tema_presente_en_toda_pagina(client):
    r = client.get("/")
    assert "alternarTema" in r.text
    assert 'data-theme="dark"' in r.text  # override CSS presente


def test_buscador_global(client):
    r = client.get("/buscar")
    assert r.status_code == 200
    r2 = client.get("/buscar?q=algo")
    assert r2.status_code == 200


def test_dashboard_sin_planes(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Aún no hay planes" in r.text


def test_onboarding_con_bd_vacia(client):
    r = client.get("/")
    assert "Primeros pasos" in r.text


def test_estilo_de_impresion_presente(client):
    r = client.get("/")
    assert "@media print" in r.text


def test_skip_link_accesibilidad(client):
    r = client.get("/")
    assert "skip-link" in r.text
    assert 'id="contenido"' in r.text
