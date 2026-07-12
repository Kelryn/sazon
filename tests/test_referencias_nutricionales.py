"""Tests de las bandas nutricionales semanales (base de las restricciones MILP)."""

from __future__ import annotations

import pytest

from menu_app.optimizacion.referencias_nutricionales import (
    BandaNutriente,
    PerfilNutricional,
    bandas_semanales,
    perfil_desde_config,
)

PERFIL = PerfilNutricional(peso_kg=70, kcal_dia=2200)  # 15.400 kcal/semana


def test_energia_con_tolerancia_del_10_pct():
    b = bandas_semanales(PERFIL)["energia_kcal"]
    assert b.minimo == pytest.approx(13860)
    assert b.maximo == pytest.approx(16940)


def test_proteina_suelo_efsa_no_recortable():
    """El caso que motiva todo: 0,83 g/kg/dia x 70 kg x 7 dias = 406,7 g/semana."""
    b = bandas_semanales(PERFIL)["proteinas_g"]
    assert b.minimo == pytest.approx(406.7)
    assert b.maximo == pytest.approx(980.0)  # techo 2,0 g/kg/dia


def test_grasas_20_a_35_pct_energia():
    b = bandas_semanales(PERFIL)["grasas_g"]
    assert b.minimo == pytest.approx(15400 * 0.20 / 9)
    assert b.maximo == pytest.approx(15400 * 0.35 / 9)


def test_saturadas_solo_techo():
    b = bandas_semanales(PERFIL)["grasas_sat_g"]
    assert b.minimo is None
    assert b.maximo == pytest.approx(15400 * 0.10 / 9)


def test_hidratos_45_a_60_pct_energia():
    b = bandas_semanales(PERFIL)["hidratos_g"]
    assert b.minimo == pytest.approx(1732.5)
    assert b.maximo == pytest.approx(2310.0)


def test_fibra_suelo_y_sal_techo():
    bandas = bandas_semanales(PERFIL)
    assert bandas["fibra_g"].minimo == pytest.approx(175)  # 25 g/dia
    assert bandas["fibra_g"].maximo is None
    assert bandas["sal_g"].maximo == pytest.approx(35)  # 5 g/dia OMS
    assert bandas["sal_g"].minimo is None


def test_banda_cumple():
    b = BandaNutriente(minimo=100, maximo=200)
    assert b.cumple(150)
    assert not b.cumple(99)
    assert not b.cumple(201)
    assert BandaNutriente(None, 50).cumple(0)
    assert BandaNutriente(50, None).cumple(1e9)


def test_perfil_desde_config_con_overrides():
    cfg = {"nutricion": {"peso_kg": 85, "kcal_dia": 2600, "fibra_min_g_dia": 30}}
    p = perfil_desde_config(cfg)
    assert p.peso_kg == 85
    assert p.kcal_dia == 2600
    assert p.fibra_min_g_dia == 30
    assert p.proteina_min_g_kg_dia == 0.83  # el resto conserva los valores por defecto
    # y las bandas escalan con el perfil:
    assert bandas_semanales(p)["proteinas_g"].minimo == pytest.approx(0.83 * 85 * 7)


def test_perfil_desde_config_vacio_usa_defaults():
    p = perfil_desde_config({})
    assert p.peso_kg == 70
    assert p.kcal_dia == 2200
