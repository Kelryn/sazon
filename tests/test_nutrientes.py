from __future__ import annotations

import pytest

from menu_app.optimizacion.nutrientes import (
    ConfigNutricion,
    objetivos_semanales,
)


def _por(nombre, bandas):
    return next(b for b in bandas if b.nutriente == nombre)


# Config sin escalado de ingesta (frac=1.0) para probar la logica base por nutriente.
def _cfg(**kw):
    kw.setdefault("fraccion_ingesta_menu", 1.0)
    return ConfigNutricion(**kw)


def test_proteina_tiene_suelo_no_evitable():
    # 1 persona, 2000 kcal, 70 kg, 7 dias.
    bandas = objetivos_semanales(_cfg(), num_comensales=1)
    prot = _por("proteinas", bandas)
    # suelo = 0.9 g/kg * 70 kg * 7 dias = 441 g/semana
    assert prot.minimo == 0.9 * 70 * 7
    assert prot.minimo > 0  # el solver NO puede bajar de aqui
    assert prot.tipo == "min"


def test_fraccion_ingesta_escala_todos_los_objetivos():
    # Las comidas del menu cubren solo una fraccion del dia -> todo escala igual.
    completo = objetivos_semanales(ConfigNutricion(fraccion_ingesta_menu=1.0), 1)
    medio = objetivos_semanales(ConfigNutricion(fraccion_ingesta_menu=0.5), 1)
    for nombre in ("energia_kcal", "proteinas", "hidratos", "sal", "fibra"):
        bc = _por(nombre, completo)
        bm = _por(nombre, medio)
        if bc.minimo is not None:
            assert bm.minimo == pytest.approx(bc.minimo * 0.5)
        if bc.maximo is not None:
            assert bm.maximo == pytest.approx(bc.maximo * 0.5)


def test_escala_con_comensales_y_dias():
    b1 = _por("proteinas", objetivos_semanales(ConfigNutricion(), 1))
    b4 = _por("proteinas", objetivos_semanales(ConfigNutricion(), 4))
    assert b4.minimo == b1.minimo * 4  # 4 personas -> x4


def test_energia_es_banda_con_tolerancia():
    bandas = objetivos_semanales(_cfg(kcal_por_comensal_dia=2000), 1)
    e = _por("energia_kcal", bandas)
    total = 2000 * 7
    assert e.minimo == pytest.approx(total * 0.9)
    assert e.maximo == pytest.approx(total * 1.1)


def test_hidratos_y_grasa_desde_porcentaje_energia():
    bandas = objetivos_semanales(_cfg(kcal_por_comensal_dia=2000), 1)
    hid = _por("hidratos", bandas)
    # 45% de 2000 kcal / 4 kcal/g = 225 g/dia * 7 = 1575 g
    assert round(hid.minimo) == round(0.45 * 2000 / 4 * 7)
    assert round(hid.maximo) == round(0.60 * 2000 / 4 * 7)
    gra = _por("grasas", bandas)
    assert round(gra.maximo) == round(0.35 * 2000 / 9 * 7)


def test_sat_azucar_sal_solo_techo():
    bandas = objetivos_semanales(ConfigNutricion(), 1)
    for nombre in ("grasas_sat", "azucares", "sal"):
        b = _por(nombre, bandas)
        assert b.minimo is None and b.maximo is not None and b.tipo == "max"


def test_fibra_solo_suelo():
    b = _por("fibra", objetivos_semanales(_cfg(), 1))
    assert b.maximo is None and b.minimo == 25 * 7 and b.tipo == "min"


def test_sal_maximo_5g_dia():
    b = _por("sal", objetivos_semanales(_cfg(sal_g_max_dia=5), num_comensales=2))
    assert b.maximo == 5 * 7 * 2
