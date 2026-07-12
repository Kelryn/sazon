"""Tests de deteccion de ingredientes opcionales (exclusion de recetas)."""

from __future__ import annotations

import pytest

from menu_app.optimizacion.economia_recetas import _es_opcional


@pytest.mark.parametrize(
    "texto",
    [
        "Perejil para decorar",
        "Guindilla (opcional)",
        "Sal al gusto",
        "amaretto o licor de naranja (opcional)",
        "Queso rallado para servir",
        "Aceite para engrasar el molde",
    ],
)
def test_opcionales(texto):
    assert _es_opcional(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "300 g de lentejas",
        "1 cebolla",
        "200 ml de vino blanco",
        "2 pechugas de pollo",
    ],
)
def test_no_opcionales(texto):
    assert _es_opcional(texto) is False
