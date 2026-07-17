"""Tests de presupuesto_max_efectivo (#113): presupuesto por comensal escalado
por el nº de comensales, con prioridad sobre el presupuesto semanal plano."""

from __future__ import annotations

from menu_app.optimizacion.servicio import presupuesto_max_efectivo


def test_sin_presupuesto_configurado_no_hay_tope():
    assert presupuesto_max_efectivo({}, num_comensales=4) is None


def test_presupuesto_semanal_plano():
    cfg = {"presupuesto_max_semana": 60.0}
    assert presupuesto_max_efectivo(cfg, num_comensales=4) == 60.0


def test_presupuesto_por_comensal_escala_con_el_hogar():
    cfg = {"presupuesto_max_por_comensal_semana": 15.0}
    assert presupuesto_max_efectivo(cfg, num_comensales=4) == 60.0
    assert presupuesto_max_efectivo(cfg, num_comensales=2) == 30.0


def test_presupuesto_por_comensal_manda_sobre_el_semanal_plano():
    cfg = {"presupuesto_max_semana": 999.0, "presupuesto_max_por_comensal_semana": 15.0}
    assert presupuesto_max_efectivo(cfg, num_comensales=2) == 30.0


def test_num_comensales_cero_no_anula_el_presupuesto():
    cfg = {"presupuesto_max_por_comensal_semana": 15.0}
    assert presupuesto_max_efectivo(cfg, num_comensales=0) == 15.0
