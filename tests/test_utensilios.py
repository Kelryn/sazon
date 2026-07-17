"""Tests de deteccion de utensilios (#47)."""

from __future__ import annotations

from menu_app.recetas.utensilios import detectar_utensilios


def test_detecta_horno():
    assert "horno" in detectar_utensilios("Pollo al horno", "Hornear 40 minutos a 200º")


def test_detecta_batidora():
    assert "batidora" in detectar_utensilios("Batido", "Triturar con la batidora")


def test_sin_utensilios_detectados():
    assert detectar_utensilios("Ensalada de tomate", "Cortar y aliñar") == set()


def test_varios_utensilios():
    u = detectar_utensilios("Sopa", "Cocer en la olla exprés y triturar con la batidora")
    assert {"olla exprés", "batidora"} <= u
