"""Estacionalidad de frutas y verduras (España) — #11.

Premia recetas cuyas frutas/verduras estan de temporada en el mes actual: mas
baratas, mejor sabor y menor huella. Tabla determinista (meses 1-12) basada en
calendarios de temporada habituales en España. Solo puntuan los ingredientes que
estan en la tabla; el resto no penaliza.
"""

from __future__ import annotations

# produccion de temporada por producto -> conjunto de meses (1=enero .. 12=diciembre).
# Clave = subcadena que debe aparecer en el nombre normalizado del ingrediente.
_TEMPORADA: dict[str, set[int]] = {
    # Verduras / hortalizas
    "alcachofa": {1, 2, 3, 4, 11, 12},
    "acelga": {1, 2, 3, 4, 10, 11, 12},
    "espinaca": {1, 2, 3, 4, 11, 12},
    "brocoli": {1, 2, 3, 4, 11, 12},
    "coliflor": {1, 2, 3, 10, 11, 12},
    "col": {1, 2, 3, 11, 12},
    "puerro": {1, 2, 3, 4, 10, 11, 12},
    "cardo": {1, 2, 12},
    "guisante": {3, 4, 5},
    "haba": {3, 4, 5},
    "esparrago": {3, 4, 5, 6},
    "rabano": {3, 4, 5},
    "calabacin": {5, 6, 7, 8, 9},
    "pepino": {5, 6, 7, 8, 9},
    "pimiento": {6, 7, 8, 9, 10},
    "tomate": {6, 7, 8, 9, 10},
    "berenjena": {7, 8, 9, 10},
    "judia verde": {6, 7, 8, 9},
    "calabaza": {9, 10, 11, 12},
    "boniato": {10, 11, 12},
    "seta": {10, 11, 12},
    "champinon": {1, 2, 3, 10, 11, 12},
    "zanahoria": set(range(1, 13)),
    "cebolla": set(range(1, 13)),
    "patata": set(range(1, 13)),
    "ajo": set(range(1, 13)),
    # Frutas
    "naranja": {1, 2, 3, 4, 11, 12},
    "mandarina": {1, 2, 3, 10, 11, 12},
    "limon": set(range(1, 13)),
    "pomelo": {1, 2, 3, 12},
    "kiwi": {1, 2, 3, 4, 11, 12},
    "manzana": {1, 2, 8, 9, 10, 11, 12},
    "pera": {1, 8, 9, 10, 11, 12},
    "platano": set(range(1, 13)),
    "fresa": {3, 4, 5, 6},
    "nispero": {4, 5},
    "cereza": {5, 6},
    "albaricoque": {5, 6, 7},
    "ciruela": {6, 7, 8, 9},
    "melocoton": {6, 7, 8, 9},
    "nectarina": {6, 7, 8, 9},
    "sandia": {6, 7, 8, 9},
    "melon": {6, 7, 8, 9},
    "higo": {8, 9, 10},
    "uva": {9, 10, 11},
    "granada": {9, 10, 11, 12},
    "caqui": {10, 11, 12},
    "aguacate": {1, 2, 3, 4, 11, 12},
}


def es_temporada(ingrediente: str, mes: int) -> bool | None:
    """True/False si el ingrediente esta/​no de temporada ese mes; None si no es un
    producto estacional conocido (no cuenta)."""
    nombre = (ingrediente or "").lower()
    for clave, meses in _TEMPORADA.items():
        if clave in nombre:
            return mes in meses
    return None


def puntua_estacionalidad(ingredientes_norm, mes: int) -> float:
    """Fraccion 0..1 de los ingredientes ESTACIONALES de la receta que estan de
    temporada ese mes. 0 si la receta no tiene productos estacionales conocidos."""
    de_temporada = 0
    estacionales = 0
    for ing in ingredientes_norm or ():
        r = es_temporada(ing, mes)
        if r is None:
            continue
        estacionales += 1
        if r:
            de_temporada += 1
    return de_temporada / estacionales if estacionales else 0.0
