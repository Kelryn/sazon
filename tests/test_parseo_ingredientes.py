from __future__ import annotations

import pytest

from menu_app.recetas.parseo_ingredientes import parsear_ingrediente


@pytest.mark.parametrize(
    "texto,cantidad,unidad,nombre",
    [
        ("200 mililitros de crema de leche para batir", 200.0, "ml", "crema de leche para batir"),
        ("70 gramos de chocolate negro al 70 % de cacao", 70.0, "g", "chocolate negro al 70 % de cacao"),
        ("15 gramos de azúcar glas", 15.0, "g", "azúcar glas"),
        ("2 dientes de ajo", 2.0, "diente", "ajo"),
        ("1 pizca de Sal", 1.0, "pizca", "Sal"),
        ("500 g de harina", 500.0, "g", "harina"),
        ("1 kg de patatas", 1.0, "kg", "patatas"),
        ("2 cucharadas de aceite de oliva", 2.0, "cucharada", "aceite de oliva"),
        ("1 lata de atún", 1.0, "lata", "atún"),
    ],
)
def test_parseo_basico(texto, cantidad, unidad, nombre):
    ing = parsear_ingrediente(texto)
    assert ing.cantidad == cantidad
    assert ing.unidad == unidad
    assert ing.nombre == nombre


def test_fraccion_unicode():
    ing = parsear_ingrediente("½ Cebolleta")
    assert ing.cantidad == 0.5
    assert ing.unidad is None
    assert ing.nombre == "Cebolleta"


def test_fraccion_mixta_unicode():
    ing = parsear_ingrediente("1½ litros de caldo")
    assert ing.cantidad == 1.5
    assert ing.unidad == "l"
    assert ing.nombre == "caldo"


def test_fraccion_ascii():
    ing = parsear_ingrediente("1/2 taza de leche")
    assert ing.cantidad == 0.5
    assert ing.unidad == "taza"
    assert ing.nombre == "leche"


def test_rango_toma_punto_medio():
    ing = parsear_ingrediente("2-3 zanahorias")
    assert ing.cantidad == 2.5
    assert ing.nombre == "zanahorias"


def test_sin_cantidad_al_gusto():
    ing = parsear_ingrediente("Sal al gusto")
    assert ing.cantidad is None
    assert ing.unidad is None
    assert ing.nombre == "Sal"


def test_cucharadas_soperas_no_ensucia_el_nombre():
    ing = parsear_ingrediente("2 cucharadas soperas de vinagre de Jerez")
    assert ing.cantidad == 2.0
    assert ing.unidad == "cucharada"
    assert ing.nombre == "vinagre de Jerez"


def test_conteo_sin_unidad():
    ing = parsear_ingrediente("1 Solomillo de cerdo")
    assert ing.cantidad == 1.0
    assert ing.unidad is None
    assert ing.nombre == "Solomillo de cerdo"


def test_nombre_normalizado_sin_acentos_ni_mayusculas():
    ing = parsear_ingrediente("2 dientes de Ajo")
    assert ing.nombre_normalizado == "ajo"


def test_texto_original_se_conserva():
    ing = parsear_ingrediente("  200 ml de leche  ")
    assert ing.texto_original == "200 ml de leche"


# --- Ingredientes en INGLES + conversion metrica (g/ml) ---


@pytest.mark.parametrize(
    "texto,cantidad,unidad,nombre",
    [
        ("2 cups of flour", 2.0, "taza", "flour"),
        ("2 cups flour", 2.0, "taza", "flour"),
        ("1 tablespoon olive oil", 1.0, "cucharada", "olive oil"),
        ("1/2 teaspoon salt", 0.5, "cucharadita", "salt"),
        ("8 oz cream cheese", 8.0, "oz", "cream cheese"),
        ("1 lb ground beef", 1.0, "lb", "ground beef"),
        ("3 cloves garlic", 3.0, "diente", "garlic"),
        ("2 fl oz milk", 2.0, "fl_oz", "milk"),
    ],
)
def test_parseo_ingles(texto, cantidad, unidad, nombre):
    ing = parsear_ingrediente(texto)
    assert ing.cantidad == cantidad
    assert ing.unidad == unidad
    assert ing.nombre == nombre


@pytest.mark.parametrize(
    "texto,cant_metrica,unidad_metrica",
    [
        ("2 cups of flour", 480.0, "ml"),          # 2 * 240 ml
        ("1 tablespoon olive oil", 15.0, "ml"),    # 1 * 15 ml
        ("1/2 teaspoon salt", 2.5, "ml"),          # 0.5 * 5 ml
        ("8 oz cream cheese", 226.8, "g"),         # 8 * 28.3495
        ("1 lb ground beef", 453.59, "g"),         # 1 * 453.592
        ("2 fl oz milk", 59.15, "ml"),             # 2 * 29.5735
        ("1 kg de patatas", 1000.0, "g"),          # metrico ya, kg -> g
        ("2 litros de caldo", 2000.0, "ml"),       # l -> ml
        ("200 gramos de azúcar", 200.0, "g"),
    ],
)
def test_conversion_metrica(texto, cant_metrica, unidad_metrica):
    ing = parsear_ingrediente(texto)
    assert ing.cantidad_metrica == cant_metrica
    assert ing.unidad_metrica == unidad_metrica


def test_conteo_sin_conversion_metrica():
    # Los conteos (dientes, unidades...) no tienen equivalente metrico.
    ing = parsear_ingrediente("3 cloves garlic")
    assert ing.cantidad_metrica is None
    assert ing.unidad_metrica is None


def test_al_gusto_ingles():
    ing = parsear_ingrediente("Salt to taste")
    assert ing.cantidad is None
    assert ing.nombre == "Salt"
