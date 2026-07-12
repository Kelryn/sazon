"""Tests de la estimacion de fibra para productos sin ese dato."""

from __future__ import annotations

import pytest

from menu_app.normalizacion.fibra_estimada import estimar_fibra


def test_legumbre_seca_vs_cocida():
    seca = estimar_fibra("Lentejas pardinas paquete 1 kg")
    cocida = estimar_fibra("Lentejas cocidas bote 400 g")
    assert seca is not None and cocida is not None
    assert seca > cocida  # la cocida tiene menos fibra por 100 g (agua)


def test_bebidas_vegetales_no_reciben_fibra_del_solido():
    # "Bebida de avena/almendra" es casi agua: no lleva la fibra del solido.
    assert estimar_fibra("ALPRO Bebida de avena 1 l") is None
    assert estimar_fibra("Bebida de almendras sin azucar 1 l") is None
    assert estimar_fibra("Batido de avena y chocolate") is None


@pytest.mark.parametrize(
    "nombre,mini",
    [
        ("Almendra cruda 200 g", 10.0),
        ("Copos de avena integral 500 g", 8.0),
        ("Arroz integral 1 kg", 3.0),
        ("Garbanzos secos 500 g", 10.0),
        ("Pan integral de trigo 400 g", 6.0),
        ("Semillas de chia 250 g", 25.0),
    ],
)
def test_alimentos_ricos_en_fibra(nombre, mini):
    fib = estimar_fibra(nombre)
    assert fib is not None and fib >= mini


def test_sin_match_devuelve_none():
    assert estimar_fibra("Refresco de cola 2 l") is None
    assert estimar_fibra("Detergente liquido") is None
    assert estimar_fibra("") is None
