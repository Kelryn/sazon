"""Clasificacion del grado de procesado (aproximacion NOVA) — #3.

Determinista y offline. Usa el `nova` de Open Food Facts si esta (muy poca
cobertura en Alcampo) y, si no, una heuristica a partir de: aditivos (numeros E) y
nº de ingredientes del campo `ingredientes`, palabras clave de la categoria, y la
composicion (azucar/grasa saturada/sal por 100 g). Nivel 1 = sin/minimamente
procesado; 4 = ultraprocesado.
"""

from __future__ import annotations

import re

_ADITIVOS = re.compile(r"\be\s?-?\d{3}\b", re.IGNORECASE)  # E-numbers: E-330, E621...

# Categorias/subcategorias tipicas de ultraprocesados (NOVA 4).
_KW_ULTRA = (
    "bolleria", "bollería", "galleta", "snack", "precocinad", "refresco", "golosina",
    "chuche", "aperitivo", "patatas fritas", "pizza", "nugget", "empanadilla",
    "croqueta", "salsa", "embutido", "cereales de desayuno", "barrita", "helado",
    "postre lacteo", "chocolatina", "bebida energetica", "flan", "natilla",
)
# Categorias de frescos / minimamente procesados (NOVA 1).
_KW_FRESCO = (
    "fruta", "verdura", "hortaliza", "carne", "pescado", "marisco", "huevo",
    "legumbre", "fresco", "cultivamos lo bueno",
)


def nivel_procesado(prod: dict) -> int:
    """Devuelve el grado de procesado 1-4 (aprox. NOVA) de un producto."""
    nova = prod.get("nova")
    if nova in (1, 2, 3, 4):
        return int(nova)

    ing = (prod.get("ingredientes") or "").lower()
    cat = ((prod.get("subcategoria") or "") + " " + (prod.get("categoria") or "")).lower()
    aditivos = len(_ADITIVOS.findall(ing))
    n_ing = (ing.count(",") + 1) if ing.strip() else 0
    azu = prod.get("azucares_100g") or 0
    sat = prod.get("grasas_sat_100g") or 0
    sal = prod.get("sal_100g") or 0

    if (
        any(k in cat for k in _KW_ULTRA)
        or aditivos >= 2
        or n_ing >= 6
        or azu >= 22
        or (sat >= 6 and sal >= 1.25)
    ):
        return 4
    if aditivos >= 1 or n_ing >= 4:
        return 3
    if any(k in cat for k in _KW_FRESCO) or n_ing <= 1:
        return 1
    return 2
