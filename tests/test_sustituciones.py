"""Tests del asistente de sustituciones de cocina (#100)."""

from __future__ import annotations

from menu_app.recetas.sustituciones import buscar_sustitutos


def test_encuentra_sustitutos_directos():
    clave, alternativas = buscar_sustitutos("nata")
    assert clave == "nata"
    assert len(alternativas) >= 2


def test_encuentra_por_alias():
    clave, alternativas = buscar_sustitutos("crema de leche")
    assert clave == "nata"
    assert alternativas


def test_encuentra_por_coincidencia_parcial():
    clave, _ = buscar_sustitutos("nata para cocinar")
    assert clave == "nata"


def test_ingrediente_desconocido_devuelve_none():
    assert buscar_sustitutos("unicornio de mar") is None


def test_vacio_devuelve_none():
    assert buscar_sustitutos("") is None
    assert buscar_sustitutos("   ") is None


def test_ignora_acentos_y_mayusculas():
    clave, _ = buscar_sustitutos("HARINA")
    assert clave == "harina"
