"""Tests de puntua_temporada_festiva (#110): tema de temporada/festivo segun el
titulo de la receta y el mes."""

from __future__ import annotations

from menu_app.optimizacion.temporada_festiva import puntua_temporada_festiva


def test_diciembre_premia_titulos_navidenos():
    assert puntua_temporada_festiva("cordero asado de navidad", 12) == 1.0
    assert puntua_temporada_festiva("turron de chocolate", 12) == 1.0


def test_verano_premia_barbacoa_y_platos_frios():
    assert puntua_temporada_festiva("costillas a la barbacoa", 7) == 1.0
    assert puntua_temporada_festiva("gazpacho andaluz", 8) == 1.0


def test_titulo_sin_tema_puntua_cero():
    assert puntua_temporada_festiva("lentejas con chorizo", 7) == 0.0


def test_mes_sin_tema_definido_puntua_cero():
    assert puntua_temporada_festiva("cordero asado de navidad", 3) == 0.0


def test_titulo_vacio_puntua_cero():
    assert puntua_temporada_festiva("", 12) == 0.0
