"""Tests del clasificador de rol de plato (principal/postre/desayuno/guarnicion)."""

from __future__ import annotations

import pytest

from menu_app.optimizacion.rol_plato import (
    DESAYUNO,
    GUARNICION,
    POSTRE,
    PRINCIPAL,
    rol_receta,
)


@pytest.mark.parametrize(
    "titulo",
    [
        "Bizcocho de yogur",
        "Tarta de manzana",
        "Tarta de queso",
        "Pastel de chocolate",
        "Mermelada de naranja",
        "Arroz con leche",
        "Flan de huevo",
        "Galletas de avena",
    ],
)
def test_postres(titulo):
    assert rol_receta(titulo) == POSTRE


@pytest.mark.parametrize(
    "titulo",
    [
        "Panqueques de plátano",
        "Tostada de aguacate",
        "Gofres caseros",
    ],
)
def test_desayunos(titulo):
    assert rol_receta(titulo) == DESAYUNO


@pytest.mark.parametrize(
    "titulo",
    [
        "Lentejas estofadas con chorizo",
        "Arroz caldoso con pollo",
        "Crema de calabaza",
        "Ensalada de tomate",
        "Tortilla de patata",
        # Guarda de salado: horneados salados son principal, no postre.
        "Pastel de carne",
        "Quiche de puerros",
        "Tarta de puerros y beicon",
    ],
)
def test_principales(titulo):
    assert rol_receta(titulo) == PRINCIPAL


@pytest.mark.parametrize(
    "titulo",
    [
        "Harina de avena casera",
        "Masa para empanadas caseras",
        "Salsa de tomate casera",
        "Caldo de pollo",
        "Vinagreta de mostaza",
    ],
)
def test_guarniciones_y_bases(titulo):
    assert rol_receta(titulo) == GUARNICION


def test_licuado_es_bebida_desayuno():
    assert rol_receta("Licuado de amaranto y papaya") == DESAYUNO


def test_prefijo_receta_de_no_rompe_las_reglas_por_inicio():
    # Las fuentes prefijan "Receta de ..."; la regla de guarnicion (por inicio)
    # debe seguir funcionando pese al prefijo.
    assert rol_receta("Receta de Harina de avena casera") == GUARNICION
    assert rol_receta("Receta de Pollo en salsa") == PRINCIPAL


def test_categoria_desempata_cuando_titulo_no_dice_nada():
    # Titulo neutro; manda la categoria del scraper.
    assert rol_receta("Delicia de la abuela", "Postre") == POSTRE
    assert rol_receta("Especial del chef", "Desayuno") == DESAYUNO
    assert rol_receta("Plato de la casa", "Plato principal") == PRINCIPAL
