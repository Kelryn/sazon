"""Tests de comensales_equivalentes (#108, modo familiar / raciones infantiles)."""

from __future__ import annotations

from menu_app.optimizacion.servicio import comensales_equivalentes


def test_sin_ninos_devuelve_el_total_tal_cual():
    assert comensales_equivalentes({"num_comensales": 4}) == 4.0


def test_ninos_reducen_los_comensales_equivalentes():
    cfg = {"num_comensales": 4, "ninos": 2, "factor_racion_infantil": 0.5}
    # 2 adultos + 2 ninos*0.5 = 3.0
    assert comensales_equivalentes(cfg) == 3.0


def test_factor_por_defecto_es_0_6():
    cfg = {"num_comensales": 2, "ninos": 1}
    # 1 adulto + 1*0.6 = 1.6
    assert comensales_equivalentes(cfg) == 1.6


def test_ninos_no_puede_superar_el_total():
    cfg = {"num_comensales": 2, "ninos": 10, "factor_racion_infantil": 0.5}
    # se recorta a 2 ninos (todo el hogar): 0 adultos + 2*0.5 = 1.0
    assert comensales_equivalentes(cfg) == 1.0


def test_nunca_baja_de_1():
    cfg = {"num_comensales": 1, "ninos": 1, "factor_racion_infantil": 0.1}
    assert comensales_equivalentes(cfg) == 1.0
