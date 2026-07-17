"""Tests de puntua_despensa (#97): fraccion de ingredientes de la receta que ya
tienes en casa, usada como bonus en el solver (ver test_solver.py para el
efecto en la seleccion de recetas)."""

from __future__ import annotations

from menu_app.optimizacion.despensa import puntua_despensa


def test_sin_despensa_puntua_cero():
    assert puntua_despensa({"tomate", "cebolla"}, frozenset()) == 0.0


def test_sin_ingredientes_puntua_cero():
    assert puntua_despensa(set(), frozenset({"sal"})) == 0.0


def test_todos_los_ingredientes_en_despensa():
    assert puntua_despensa({"sal", "aceite de oliva"}, frozenset({"sal", "aceite de oliva"})) == 1.0


def test_mitad_de_ingredientes_en_despensa():
    assert puntua_despensa({"sal", "pollo"}, frozenset({"sal"})) == 0.5


def test_coincide_por_subcadena():
    # "aceite de oliva virgen extra" contiene "aceite de oliva" de la despensa.
    assert puntua_despensa({"aceite de oliva virgen extra"}, frozenset({"aceite de oliva"})) == 1.0
