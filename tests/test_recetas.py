from __future__ import annotations

import json
from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.recetas.repositorio import RecetaRepository
from menu_app.recetas.scraper import parsear_html

URL = "https://recetas.elperiodico.com/receta-de-lentejas-58888.html"

# HTML minimo con JSON-LD schema.org/Recipe, como el que exponen las webs ES.
_JSONLD = {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Lentejas estofadas con verduras",
    "recipeYield": "4 raciones",
    "totalTime": "PT45M",
    "recipeCategory": "Plato principal",
    "recipeIngredient": [
        "300 gramos de lentejas",
        "2 dientes de ajo",
        "1 Cebolla",
        "Sal al gusto",
    ],
    "recipeInstructions": "Cocer las lentejas con las verduras.",
    "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.6", "ratingCount": "37"},
    "image": "https://example.com/lentejas.jpg",
}
HTML_RECETA = f'<html><head><script type="application/ld+json">{json.dumps(_JSONLD)}</script></head><body></body></html>'
HTML_SIN_RECETA = "<html><head></head><body><p>Un articulo sin receta</p></body></html>"


def test_parsear_html_receta_completa():
    receta = parsear_html(HTML_RECETA, URL)

    assert receta is not None
    assert receta.titulo == "Lentejas estofadas con verduras"
    assert receta.raciones == 4
    assert receta.tiempo_total_min == 45
    assert receta.rating == 4.6
    assert receta.rating_count == 37
    assert receta.fuente == "recetas.elperiodico.com"
    assert len(receta.ingredientes) == 4
    # Ingredientes parseados a cantidad/unidad/nombre.
    lentejas = receta.ingredientes[0]
    assert lentejas.cantidad == 300.0
    assert lentejas.unidad == "g"
    assert lentejas.nombre == "lentejas"


def test_parsear_html_sin_schema_devuelve_none():
    assert parsear_html(HTML_SIN_RECETA, URL) is None


@pytest.fixture
def repo(tmp_path: Path) -> RecetaRepository:
    conn = get_connection(tmp_path / "test.db")
    init_db(conn)
    return RecetaRepository(conn)


def test_upsert_receta_guarda_ingredientes(repo):
    receta = parsear_html(HTML_RECETA, URL)
    repo.upsert_receta(receta, "2026-07-09T10:00:00")

    assert repo.contar_recetas() == 1
    assert repo.contar_ingredientes() == 4
    assert repo.url_ya_ingerida(receta.id) is True


def test_upsert_receta_es_idempotente(repo):
    receta = parsear_html(HTML_RECETA, URL)
    repo.upsert_receta(receta, "2026-07-09T10:00:00")
    repo.upsert_receta(receta, "2026-07-09T11:00:00")  # reingesta

    assert repo.contar_recetas() == 1
    # Los ingredientes se reemplazan, no se duplican.
    assert repo.contar_ingredientes() == 4
