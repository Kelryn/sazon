"""Tests del plan multi-semana con persistencia y regla de repeticion."""

from __future__ import annotations

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.optimizacion.planes import cargar_plan, generar_plan, regenerar_semana
from menu_app.optimizacion.servicio import _max_repeticiones_semana, semanas_exclusion


@pytest.fixture
def conn(tmp_path):
    c = get_connection(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


def test_max_repeticiones_desde_dias_repeticion():
    assert _max_repeticiones_semana({"dias_repeticion": 7}) == 1
    assert _max_repeticiones_semana({"dias_repeticion": 14}) == 1
    assert _max_repeticiones_semana({"dias_repeticion": 3}) == 2
    assert _max_repeticiones_semana({"dias_repeticion": 1}) == 7


def test_semanas_exclusion():
    assert semanas_exclusion({"dias_repeticion": 7}) == 0   # puede repetir a la semana sig.
    assert semanas_exclusion({"dias_repeticion": 14}) == 1  # veta la semana anterior
    assert semanas_exclusion({"dias_repeticion": 21}) == 2


def _cfg(tmp_path, **extra):
    cfg = {
        "almacenamiento": {"db_path": str(tmp_path / "test.db")},
        "num_comensales": 1,
        "semanas_plan": 2,
        "dias_repeticion": 7,
        "fraccion_recetas_espanolas_min": 0,
    }
    cfg.update(extra)
    return cfg


def test_generar_plan_persiste_semanas(conn, tmp_path):
    # Sin recetas: el plan se guarda igualmente (semana 1 infactible) y se puede cargar.
    plan_id, resultados = generar_plan(conn, _cfg(tmp_path), n_semanas=2)
    assert plan_id.startswith("plan-")
    pid, semanas = cargar_plan(conn)
    assert pid == plan_id
    assert 1 in semanas
    assert semanas[1]["factible"] is False


def test_regenerar_semana_reescribe(conn, tmp_path):
    cfg = _cfg(tmp_path)
    plan_id, _ = generar_plan(conn, cfg, n_semanas=1)
    res = regenerar_semana(conn, cfg, plan_id, 1, excluir="cualquiera")
    _pid, semanas = cargar_plan(conn, plan_id)
    assert semanas[1]["factible"] == res.menu.factible


def test_asignar_dias_separa_repeticiones():
    from menu_app.optimizacion.planes import asignar_dias

    # Una receta de comida usada 2 veces en 7 dias no debe caer en dias seguidos.
    datos = {
        "dias": 7,
        "dias_bc": [],
        "seleccion_comida": {"A": 2, "B": 2, "C": 3},
        "seleccion_comida_bc": {},
        "seleccion_cena": {"X": 7},
    }
    asign = asignar_dias(datos, ["lun", "mar", "mie", "jue", "vie", "sab", "dom"])
    comidas = [comida for _dia, comida, _cena, _bc in asign]
    # 'A' aparece 2 veces y sus posiciones no son consecutivas.
    pos_a = [i for i, c in enumerate(comidas) if c == "A"]
    assert len(pos_a) == 2 and abs(pos_a[0] - pos_a[1]) >= 2


def test_raciones_fraccionables_en_solver():
    # Con una unica receta de 600 kcal/racion y banda estrecha, el solver debe
    # FRACCIONAR raciones para cuadrar la energia (con raciones enteras seria 4200).
    from menu_app.optimizacion.nutrientes import BandaNutriente
    from menu_app.optimizacion.solver import RecetaOpt, optimizar_comida_cena

    r = RecetaOpt("unica", "unica", 1.0, {"energia_kcal": 600.0})
    bandas = [BandaNutriente("energia_kcal", minimo=3500, maximo=3800, unidad="kcal", tipo="banda")]
    menu = optimizar_comida_cena(
        [r], bandas, dias=3, num_comensales=1, max_repeticiones=6,
        frac_espanola_min=0, racion_frac_min=0.75, racion_frac_max=1.25,
    )
    assert menu.factible
    total = menu.nutricion_total["energia_kcal"]
    assert 3500 <= total <= 3800
    # raciones totales fraccionadas (5.83, no un entero) — coherentes con la energia
    # salvo el redondeo informativo a 2 decimales.
    assert abs(sum(menu.raciones.values()) * 600 - total) < 10
    assert any(abs(x - round(x)) > 0.01 for x in menu.raciones.values())
