"""Tests de grupos de alimento y restricciones de equilibrio del solver."""

from __future__ import annotations

import pytest

from menu_app.optimizacion.grupos_alimentos import grupo_por_nombre, grupo_receta
from menu_app.optimizacion.nutrientes import BandaNutriente
from menu_app.optimizacion.solver import RecetaOpt, optimizar_comida_cena


@pytest.mark.parametrize(
    "nombre,grupo",
    [
        ("lentejas", "legumbre"),
        ("garbanzos con espinacas", "legumbre"),
        ("merluza al horno", "pescado"),
        ("solomillo de ternera", "carne_roja"),
        ("pechuga de pollo", "carne_blanca"),
        ("espaguetis carbonara", "cereal"),  # por el nombre manda 'espagueti' -> cereal
        ("ensalada de tomate", "verdura"),
        ("arroz blanco", "cereal"),
        ("tortilla de patata", "huevo"),
    ],
)
def test_grupo_por_nombre(nombre, grupo):
    assert grupo_por_nombre(nombre) == grupo


def test_grupo_receta_manda_el_principal():
    # El titulo dice 'arroz' (cereal) pero el ingrediente principal es pollo.
    assert grupo_receta("Arroz con pollo", "pollo") == "carne_blanca"
    # Sin pista del principal, manda el titulo.
    assert grupo_receta("Lentejas de la abuela", None) == "legumbre"


def _r(id, grupo, coste=1.0):
    return RecetaOpt(
        id=id, titulo=id, coste_racion=coste,
        nutricion_racion={"energia_kcal": 500, "proteinas": 20.0}, grupo=grupo,
    )


def test_maximo_de_carne_roja_es_techo_duro():
    roja = _r("roja", "carne_roja", coste=0.2)  # barata
    pescado = _r("pescado", "pescado", coste=1.0)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=6000, unidad="kcal", tipo="banda")]
    menu = optimizar_comida_cena(
        [roja, pescado], bandas, dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_variedad=0, max_por_grupo={"carne_roja": 3},
    )
    assert menu.factible
    n_roja = sum(n for rid, n in menu.seleccion.items() if rid == "roja")
    assert n_roja <= 3  # no se pasa de 3 comidas de carne roja pese a ser barata


def test_minimo_de_pescado_fuerza_pescado():
    barata = _r("otra", "cereal", coste=0.2)
    pescado = _r("pescado", "pescado", coste=1.0)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=6000, unidad="kcal", tipo="banda")]
    menu = optimizar_comida_cena(
        [barata, pescado], bandas, dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_variedad=0, min_por_grupo={"pescado": 3},
    )
    assert menu.factible
    n_pesc = sum(n for rid, n in menu.seleccion.items() if rid == "pescado")
    assert n_pesc >= 3  # el suelo blando de pescado lo mete pese a ser mas caro
