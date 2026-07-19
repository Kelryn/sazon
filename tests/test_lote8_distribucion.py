"""Tests del Lote 8 (distribucion y robustez): backups, canal, telemetria, hash."""

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
        "num_comensales: 2\ncomidas_por_dia: [comida, cena]\n"
        "backups_automaticos: false\n",  # evita el hilo de backup en el arranque del test
        encoding="utf-8",
    )
    return TestClient(crear_app(cfg))


def test_config_muestra_canal_y_backups_y_telemetria(client):
    r = client.get("/config")
    assert 'name="canal"' in r.text
    assert "Copias de seguridad" in r.text
    assert "Diagnóstico de errores" in r.text


def test_crear_y_ver_backup_en_config(client, tmp_path):
    # Sin BD todavia (backups_automaticos=false y no se ha usado la app): crear
    # backup debe informar sin romper, ya que get_connection() la crea al vuelo
    # con _conn() -> init_db al pedir /config.
    rp = client.post("/config/backups/crear", follow_redirects=True)
    assert rp.status_code == 200


def test_activar_y_desactivar_telemetria(client):
    r1 = client.post("/config/telemetria", data={"activo": "1"}, follow_redirects=True)
    assert r1.status_code == 200
    r2 = client.get("/config")
    assert "Guardar un registro local de errores" in r2.text
    r3 = client.post("/config/telemetria", data={}, follow_redirects=True)
    assert r3.status_code == 200


def test_limpiar_registro_no_rompe_sin_log(client):
    r = client.post("/config/telemetria/limpiar", follow_redirects=True)
    assert r.status_code == 200


def test_cambiar_canal_actualiza_config(client):
    r = client.post("/config/canal", data={"canal": "beta"}, follow_redirects=True)
    assert r.status_code == 200
    r2 = client.get("/config")
    # El canal es ahora un segmentado (.seg): el botón activo lleva class="on".
    assert 'value="beta" class="on"' in r2.text
