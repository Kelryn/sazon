"""Tests del modulo de actualizaciones (Fase 11), sin tocar la red real."""

from __future__ import annotations

import httpx
import pytest

from menu_app import actualizaciones
from menu_app.actualizaciones import es_mas_nueva, hay_actualizacion


@pytest.mark.parametrize(
    "remota,local,esperado",
    [
        ("v0.2.0", "0.1.0", True),
        ("0.1.1", "0.1.0", True),
        ("v1.0.0", "0.9.9", True),
        ("v0.1.0", "0.1.0", False),
        ("v0.1.0", "0.2.0", False),
        ("v0.2.0-beta", "0.1.0", True),
    ],
)
def test_es_mas_nueva(remota, local, esperado):
    assert es_mas_nueva(remota, local) is esperado


def test_sin_repo_devuelve_none():
    assert hay_actualizacion(None) is None
    assert hay_actualizacion("") is None
    assert hay_actualizacion("sin-barra") is None


def _fake_get(payload, status=200):
    def _get(url, **kw):
        return httpx.Response(status, json=payload, request=httpx.Request("GET", url))
    return _get


def test_detecta_version_nueva(monkeypatch):
    payload = {
        "tag_name": "v0.5.0",
        "html_url": "https://github.com/u/sazon-releases/releases/tag/v0.5.0",
        "body": "Novedades",
        "assets": [
            {"name": "Sazon.exe", "browser_download_url": "https://x/Sazon.exe"},
            {"name": "Sazon-Setup.exe", "browser_download_url": "https://x/Sazon-Setup.exe"},
        ],
    }
    monkeypatch.setattr(httpx, "get", _fake_get(payload))
    info = hay_actualizacion("u/sazon-releases", version_actual="0.1.0")
    assert info is not None
    assert info.version == "0.5.0"
    assert info.url_descarga.endswith("Sazon-Setup.exe")  # prefiere el instalador


def test_al_dia_devuelve_none(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({"tag_name": "v0.1.0", "assets": []}))
    assert hay_actualizacion("u/repo", version_actual="0.1.0") is None


def test_error_red_no_rompe(monkeypatch):
    def _boom(url, **kw):
        raise httpx.ConnectError("sin red")
    monkeypatch.setattr(httpx, "get", _boom)
    assert hay_actualizacion("u/repo") is None
