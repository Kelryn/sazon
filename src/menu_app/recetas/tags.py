"""Etiquetas deterministas de recetas (#46): rápida, picante, vegetariana... a partir
de datos ya disponibles (tiempo, ingredientes, flags del editor). Sin IA.
"""

from __future__ import annotations

_PICANTE = ("guindilla", "chile", "picante", "tabasco", "cayena", "jalapeno", "wasabi")
_CARNE_PESCADO = (
    "pollo", "pavo", "ternera", "cerdo", "cordero", "conejo", "jamon", "chorizo",
    "salchicha", "bacon", "panceta", "atun", "salmon", "merluza", "bacalao", "gamba",
    "langostino", "marisco", "pescado", "sepia", "calamar", "pulpo", "anchoa",
)


def generar_tags(
    *,
    tiempo_total_min: int | None,
    ingredientes_norm,
    es_batchcooking: bool = False,
    es_plato_unico: bool = False,
) -> list[str]:
    """Etiquetas deterministas a partir de datos ya disponibles de la receta."""
    ings = set(ingredientes_norm or ())
    tags: list[str] = []
    if tiempo_total_min and tiempo_total_min <= 20:
        tags.append("rápida")
    if any(any(p in ing for p in _PICANTE) for ing in ings):
        tags.append("picante")
    if ings and not any(any(c in ing for c in _CARNE_PESCADO) for ing in ings):
        tags.append("vegetariana")
    if es_batchcooking:
        tags.append("batchcooking")
    if es_plato_unico:
        tags.append("plato único")
    return tags
