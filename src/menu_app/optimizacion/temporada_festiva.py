"""Menús por temporada/festivos — #110 (Navidad, verano, barbacoa).

Premia, segun el MES actual, recetas cuyo TITULO contiene palabras del tema de
esa epoca (a diferencia de estacionalidad.py, que mira ingredientes de fruta/
verdura). Deterministico, sin IA: una tabla de palabras por mes.
"""

from __future__ import annotations

# Mes (1-12) -> palabras que identifican el tema de esa epoca en el TITULO de la
# receta (ya normalizado: sin acentos, minusculas). Un mes puede tener varios
# temas simultaneos (p.ej. verano: barbacoa Y platos frios).
_TEMAS: dict[int, tuple[str, ...]] = {
    6: ("barbacoa", "parrilla", "brasa", "gazpacho", "salmorejo", "ensalada", "helado", "sandia", "melon"),
    7: ("barbacoa", "parrilla", "brasa", "gazpacho", "salmorejo", "ensalada", "helado", "sandia", "melon"),
    8: ("barbacoa", "parrilla", "brasa", "gazpacho", "salmorejo", "ensalada", "helado", "sandia", "melon"),
    12: ("navidad", "navideñ", "turron", "roscon", "marisco", "cordero asado", "besugo"),
}


def puntua_temporada_festiva(titulo_norm: str, mes: int) -> float:
    """1.0 si el titulo (ya normalizado) contiene una palabra del tema de ese mes,
    0.0 si no hay tema para el mes o no coincide."""
    temas = _TEMAS.get(mes)
    if not temas or not titulo_norm:
        return 0.0
    return 1.0 if any(palabra in titulo_norm for palabra in temas) else 0.0
