"""Utensilios necesarios por receta (#47): deteccion determinista por palabras clave
en el titulo y las instrucciones. Sirve para filtrar recetas segun lo que tengas.
"""

from __future__ import annotations

_UTENSILIOS = {
    "horno": ("horno", "hornear", "gratinar", "asar al horno"),
    "olla exprés": ("olla exprés", "olla express", "olla a presión", "olla rapida"),
    "batidora": ("batidora", "turmix", "minipimer"),
    "robot de cocina": ("robot de cocina", "thermomix", "monsieur cuisine"),
    "freidora": ("freidora", "airfryer", "freidora de aire"),
    "plancha": ("plancha",),
    "microondas": ("microondas",),
    "barbacoa": ("barbacoa", "parrilla"),
}


def detectar_utensilios(titulo: str, instrucciones: str | None) -> set[str]:
    """Utensilios detectados en el titulo+instrucciones (minusculas, sin acentos ya
    normalizado por el llamador si hace falta)."""
    texto = f"{titulo or ''} {instrucciones or ''}".lower()
    return {nombre for nombre, claves in _UTENSILIOS.items() if any(c in texto for c in claves)}
