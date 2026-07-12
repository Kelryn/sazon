from __future__ import annotations

import pytest

from menu_app.normalizacion.nutricion_estimada import estimar


@pytest.mark.parametrize(
    "nombre,alimento_esperado",
    [
        ("Tomate rama al peso.", "tomate"),
        ("Aguacate malla de 500 g.", "aguacate"),
        ("PRODUCTO ALCAMPO Cebolla al peso", "cebolla"),
        ("Manzana Golden al peso", "manzana"),
        ("Plátano de Canarias", "platano"),
        ("LAGO Pechugas de pollo blanco ultracongeladas 1 kg.", "pechuga pollo"),
        ("Salmón fresco rodaja", "salmon"),
        ("Merluza del cabo pieza", "merluza"),
        ("Huevos frescos clase L docena", "huevo"),
        ("Espinacas frescas bolsa 250 g", "espinaca"),
    ],
)
def test_estimar_alimentos_frescos(nombre, alimento_esperado):
    res = estimar(nombre)
    assert res is not None, f"no caso: {nombre}"
    _macros, alimento = res
    assert alimento == alimento_esperado


def test_macros_tomate_razonables():
    macros, _ = estimar("Tomate pera al peso")
    # ~18 kcal/100g, alta agua, poca grasa/proteina (valores USDA).
    assert 10 < macros["energia_kcal"] < 30
    assert macros["grasas"] < 1
    assert macros["proteinas"] < 2


def test_pechuga_es_proteica():
    macros, alimento = estimar("Pechuga de pollo fresca")
    assert alimento == "pechuga pollo"
    assert macros["proteinas"] > 18  # carne magra
    assert macros["hidratos"] == 0


def test_producto_no_fresco_no_casa():
    # Sin palabra de alimento en la tabla -> None. (La estimacion real solo se
    # aplica a productos aptos para receta, asi que droguerias/bebidas ni entran.)
    assert estimar("Café en cápsulas Ristretto 20 uds.") is None
    assert estimar("Papel de cocina rollo doble") is None
    assert estimar("Rollos de aluminio 30 m") is None


def test_clave_compuesta_prioritaria():
    # 'jamon cocido' debe ganar a un generico; y 'serrano' -> jamon curado.
    _m, a = estimar("ELPOZO Jamón cocido extra lonchas 200 g")
    assert a == "jamon cocido"
