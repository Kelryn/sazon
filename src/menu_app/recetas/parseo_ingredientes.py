"""Parsea una linea de ingrediente (ES o EN) a cantidad, unidad y nombre, y
ademas la convierte al sistema metrico con predileccion por gramos y mililitros.

Ejemplos:
    "200 mililitros de crema de leche"   -> 200 ml            (metrico: 200 ml)
    "2 cucharadas de aceite de oliva"    -> 2 cucharada       (metrico: 30 ml)
    "2 cups of flour"                    -> 2 taza / "flour"  (metrico: 480 ml)
    "8 oz cheese"                        -> 8 oz / "cheese"   (metrico: 226.8 g)
    "1 lb chicken breast"                -> 1 lb              (metrico: 453.59 g)
    "½ Cebolleta"                        -> 0.5 (sin unidad, es un conteo)

Regla de conversion: unidades de peso -> g; unidades de volumen -> ml; unidades
de conteo (diente, clove, loncha, lata, unidad...) no se convierten (no tienen
equivalente metrico universal sin densidad). Los "cups/tazas" de solidos se
pasan a ml (volumen); pasarlos a gramos exigiria la densidad del ingrediente
(pendiente para una fase posterior).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Fracciones unicode -> equivalente ascii "a/b".
_FRACCIONES = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5",
    "⅙": "1/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}

# Sinonimos de unidad (ES + EN) -> unidad canonica.
_UNIDADES = {
    # Peso metrico
    "g": "g", "gr": "g", "grs": "g", "gramo": "g", "gramos": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramo": "kg", "kilogramos": "kg",
    "kilogram": "kg", "kilograms": "kg",
    "mg": "mg", "miligramo": "mg", "miligramos": "mg", "milligram": "mg", "milligrams": "mg",
    # Peso imperial
    "oz": "oz", "onza": "oz", "onzas": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "libra": "lb", "libras": "lb", "pound": "lb", "pounds": "lb",
    # Volumen metrico
    "ml": "ml", "mililitro": "ml", "mililitros": "ml", "cc": "ml",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "l": "l", "litro": "l", "litros": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "cl": "cl", "centilitro": "cl", "centilitros": "cl",
    "dl": "dl", "decilitro": "dl", "decilitros": "dl",
    # Volumen "de cuchara/taza" (ES + EN)
    "cucharada": "cucharada", "cucharadas": "cucharada", "cda": "cucharada", "cdas": "cucharada",
    "tablespoon": "cucharada", "tablespoons": "cucharada", "tbsp": "cucharada", "tbsps": "cucharada",
    "tbs": "cucharada",
    "cucharadita": "cucharadita", "cucharaditas": "cucharadita", "cdta": "cucharadita",
    "teaspoon": "cucharadita", "teaspoons": "cucharadita", "tsp": "cucharadita", "tsps": "cucharadita",
    "taza": "taza", "tazas": "taza", "cup": "taza", "cups": "taza",
    "vaso": "vaso", "vasos": "vaso",
    # Volumen imperial de liquido
    "pint": "pint", "pints": "pint", "pinta": "pint", "pintas": "pint",
    "quart": "quart", "quarts": "quart",
    "gallon": "gallon", "gallons": "gallon", "galon": "gallon", "galones": "gallon",
    # Conteo (sin conversion metrica)
    "pizca": "pizca", "pizcas": "pizca", "pinch": "pizca", "pinches": "pizca",
    "diente": "diente", "dientes": "diente", "clove": "diente", "cloves": "diente",
    "rodaja": "rodaja", "rodajas": "rodaja",
    "loncha": "loncha", "lonchas": "loncha", "slice": "loncha", "slices": "loncha",
    "lata": "lata", "latas": "lata", "can": "lata", "cans": "lata",
    "sobre": "sobre", "sobres": "sobre",
    "ramita": "ramita", "ramitas": "ramita", "rama": "ramita", "ramas": "ramita",
    "sprig": "ramita", "sprigs": "ramita",
    "hoja": "hoja", "hojas": "hoja", "leaf": "hoja", "leaves": "hoja",
    "puñado": "puñado", "puñados": "puñado", "handful": "puñado", "handfuls": "puñado",
    "chorro": "chorro", "chorrito": "chorro",
    "manojo": "manojo", "manojos": "manojo", "bunch": "manojo",
    "stick": "stick", "sticks": "stick",
    "unidad": "ud", "unidades": "ud", "ud": "ud", "uds": "ud",
}

# Unidades de dos palabras (se comprueban antes que las de una).
_UNIDADES_MULTI = {
    "fl oz": "fl_oz", "fluid ounce": "fl_oz", "fluid ounces": "fl_oz",
}

# Unidad canonica -> (factor, unidad_metrica). Lo que no este aqui es conteo.
_A_METRICO: dict[str, tuple[float, str]] = {
    "g": (1.0, "g"), "mg": (0.001, "g"), "kg": (1000.0, "g"),
    "oz": (28.3495, "g"), "lb": (453.592, "g"),
    "ml": (1.0, "ml"), "cl": (10.0, "ml"), "dl": (100.0, "ml"), "l": (1000.0, "ml"),
    "cucharada": (15.0, "ml"), "cucharadita": (5.0, "ml"),
    "taza": (240.0, "ml"), "vaso": (200.0, "ml"),
    "fl_oz": (29.5735, "ml"), "pint": (473.176, "ml"),
    "quart": (946.353, "ml"), "gallon": (3785.41, "ml"),
}

# Modificadores que acompañan a "cucharada(s)" y no son parte del ingrediente.
_MODIF_UNIDAD = {"sopera", "soperas", "postre", "rasa", "rasas", "colmada", "colmadas"}

_AL_GUSTO = re.compile(
    r"\bal\s+gusto\b|\bto\s+taste\b|\bcantidad\s+necesaria\b", re.IGNORECASE
)
_CONECTOR_INICIAL = re.compile(
    r"^\s*(?:de\s+la|de\s+los|de\s+las|del|de|of)\s+", re.IGNORECASE
)


@dataclass
class IngredienteReceta:
    texto_original: str
    cantidad: float | None
    unidad: str | None
    nombre: str
    nombre_normalizado: str
    cantidad_metrica: float | None = None
    unidad_metrica: str | None = None  # "g" | "ml" | None (conteo/desconocido)


def _quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _a_numero(token: str) -> float | None:
    token = token.strip().replace(",", ".")
    m = re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", token)  # mixto "1 1/2"
    if m:
        entero, num, den = map(float, m.groups())
        return round(entero + num / den, 3) if den else None
    m = re.fullmatch(r"(\d+)/(\d+)", token)  # fraccion "1/2"
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return round(num / den, 3) if den else None
    try:
        return float(token)
    except ValueError:
        return None


def _normalizar_fracciones(texto: str) -> str:
    for frac, ascii_ in _FRACCIONES.items():
        texto = re.sub(rf"(\d)\s*{frac}", rf"\1 {ascii_}", texto)  # "1½" -> "1 1/2"
        texto = texto.replace(frac, ascii_)  # "½" -> "1/2"
    return texto


def _limpiar_nombre(nombre: str) -> str:
    nombre = _AL_GUSTO.sub("", nombre)
    nombre = _CONECTOR_INICIAL.sub("", nombre)
    return re.sub(r"\s+", " ", nombre).strip(" ,.-")


def _a_metrico(cantidad: float | None, unidad: str | None) -> tuple[float | None, str | None]:
    if cantidad is None or unidad is None or unidad not in _A_METRICO:
        return None, None
    factor, unidad_metrica = _A_METRICO[unidad]
    return round(cantidad * factor, 2), unidad_metrica


def parsear_ingrediente(texto: str) -> IngredienteReceta:
    original = texto.strip()
    trabajo = _normalizar_fracciones(original)

    cantidad: float | None = None
    unidad: str | None = None

    # Cantidad al principio: "200", "1.5", "1/2", "1 1/2", rango "1-2"/"1 a 2"/"1 to 2".
    m = re.match(
        r"^\s*(\d+(?:\s+\d+/\d+|/\d+|[.,]\d+)?)\s*(?:(?:-|a|to)\s*(\d+(?:[.,]\d+)?))?\s*(.*)$",
        trabajo,
    )
    resto = trabajo
    if m:
        c1 = _a_numero(m.group(1))
        c2 = _a_numero(m.group(2)) if m.group(2) else None
        if c1 is not None:
            cantidad = round((c1 + c2) / 2, 3) if c2 is not None else c1
        resto = m.group(3)

    palabras = resto.split()
    # Unidad de dos palabras ("fl oz", "fluid ounce").
    if len(palabras) >= 2:
        dos = f"{palabras[0].lower().strip('.')} {palabras[1].lower().strip('.')}"
        if dos in _UNIDADES_MULTI:
            unidad = _UNIDADES_MULTI[dos]
            palabras = palabras[2:]
    # Unidad de una palabra.
    if unidad is None and palabras and palabras[0].lower().strip(".") in _UNIDADES:
        unidad = _UNIDADES[palabras[0].lower().strip(".")]
        palabras = palabras[1:]
        if palabras and palabras[0].lower() in _MODIF_UNIDAD:  # "cucharadas soperas"
            palabras = palabras[1:]

    resto = " ".join(palabras)
    nombre = _limpiar_nombre(resto) or _limpiar_nombre(original)

    cantidad_metrica, unidad_metrica = _a_metrico(cantidad, unidad)
    return IngredienteReceta(
        texto_original=original,
        cantidad=cantidad,
        unidad=unidad,
        nombre=nombre,
        nombre_normalizado=_quitar_acentos(nombre.lower()).strip(),
        cantidad_metrica=cantidad_metrica,
        unidad_metrica=unidad_metrica,
    )
