from __future__ import annotations

from dataclasses import dataclass, field

from .parseo_ingredientes import IngredienteReceta


@dataclass
class Receta:
    """Una receta extraida de una web (schema.org/Recipe via recipe-scrapers).

    `rating` y `rating_count` alimentan la palatabilidad (media bayesiana
    ponderada por nº de reseñas) de fases posteriores. Los ingredientes van ya
    parseados a cantidad/unidad/nombre para el matching con productos (Fase 4).
    """

    id: str  # hash estable de la url
    url: str
    fuente: str  # dominio
    titulo: str
    raciones: int | None
    tiempo_total_min: int | None
    categoria: str | None
    cocina: str | None
    rating: float | None
    rating_count: int | None
    imagen: str | None
    instrucciones: str | None
    ingredientes: list[IngredienteReceta] = field(default_factory=list)
