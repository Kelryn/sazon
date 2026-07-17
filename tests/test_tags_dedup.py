"""Tests de etiquetas deterministas (#46) y deteccion de duplicados (#45)."""

from __future__ import annotations

from menu_app.recetas.dedup import GrupoDuplicado, _jaccard
from menu_app.recetas.tags import generar_tags


def test_tag_rapida_por_tiempo():
    assert "rápida" in generar_tags(tiempo_total_min=15, ingredientes_norm={"pollo"})
    assert "rápida" not in generar_tags(tiempo_total_min=45, ingredientes_norm={"pollo"})


def test_tag_picante_por_ingrediente():
    tags = generar_tags(tiempo_total_min=30, ingredientes_norm={"guindilla", "tomate"})
    assert "picante" in tags


def test_tag_vegetariana_sin_carne_ni_pescado():
    assert "vegetariana" in generar_tags(tiempo_total_min=30, ingredientes_norm={"tomate", "arroz"})
    assert "vegetariana" not in generar_tags(tiempo_total_min=30, ingredientes_norm={"pollo", "arroz"})


def test_tags_batchcooking_y_plato_unico():
    tags = generar_tags(
        tiempo_total_min=None, ingredientes_norm=set(), es_batchcooking=True, es_plato_unico=True
    )
    assert "batchcooking" in tags
    assert "plato único" in tags


def test_jaccard_identico_y_disjunto():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert _jaccard({"a"}, {"b"}) == 0.0
    assert _jaccard(set(), {"a"}) == 0.0
