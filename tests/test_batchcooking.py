"""Tests del clasificador de batchcooking y del filtro del solver."""

from __future__ import annotations

import pytest

from menu_app.optimizacion.batchcooking import es_batchcooking
from menu_app.optimizacion.nutrientes import BandaNutriente
from menu_app.optimizacion.solver import RecetaOpt, optimizar


@pytest.mark.parametrize(
    "titulo",
    [
        "Lentejas estofadas con chorizo",
        "Guiso de garbanzos con espinacas",
        "Arroz al horno",
        "Crema de calabaza",
        "Lasaña de carne",
        "Pollo asado con patatas",
        "Curry de pollo",
        "Albóndigas en salsa",
        "Fabada asturiana",
        "Tortilla de patata",
        "Ensalada de tomate y mozzarella",
        "Ensalada de lentejas",
        "Ensaladilla rusa",
    ],
)
def test_aptas_para_batchcooking(titulo):
    assert es_batchcooking(titulo) is True


@pytest.mark.parametrize(
    "titulo",
    [
        "Merluza a la plancha",
        "Calamares fritos",
        "Tartar de atún",
        "Bocadillo de calamares",
        "Huevos fritos con patatas",
        "Tosta de aguacate",
    ],
)
def test_no_aptas_para_batchcooking(titulo):
    assert es_batchcooking(titulo) is False


def test_negativa_gana_a_positiva():
    # "arroz" es positiva pero "frito" lo desaconseja para tupper.
    assert es_batchcooking("Arroz frito tres delicias") is False


def test_sin_senal_no_es_batchcooking():
    assert es_batchcooking("Yogur con fruta") is False
    assert es_batchcooking("") is False
    assert es_batchcooking(None) is False


def _r(id, bc, coste=1.0):
    return RecetaOpt(
        id=id, titulo=id, coste_racion=coste,
        nutricion_racion={"energia_kcal": 500, "proteinas": 20.0},
        es_batchcooking=bc,
    )


def test_solver_solo_batchcooking_filtra_el_catalogo():
    bc = _r("guiso", True, coste=1.5)
    no_bc = _r("ensalada", False, coste=0.2)  # mas barata, pero no batchcooking
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda")]
    menu = optimizar(
        [bc, no_bc], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, solo_batchcooking=True,
    )
    assert menu.factible
    assert "ensalada" not in menu.seleccion  # excluida pese a ser mas barata
    assert menu.seleccion.get("guiso", 0) == 10


def test_solver_sin_batchcooking_no_hay_recetas():
    no_bc = _r("ensalada", False)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda")]
    menu = optimizar(
        [no_bc], bandas, n_comidas=10, num_comensales=1, solo_batchcooking=True,
    )
    assert not menu.factible
