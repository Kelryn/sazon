"""Test de contrato contra la API REAL de Alcampo.

Deshabilitado por defecto (no queremos que cada `pytest` golpee su sitio).
Activalo a mano cuando quieras comprobar que no han cambiado la forma de la
API, con:

    RUN_LIVE_ALCAMPO_TESTS=1 uv run pytest tests/test_contract_live.py -v

Hace solo 2 peticiones reales (arbol de categorias + un listado pequeño),
respetando el rate limit configurado en AlcampoClientConfig.
"""

from __future__ import annotations

import os

import pytest

from menu_app.ingesta.alcampo_client import AlcampoClient, AlcampoClientConfig

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("RUN_LIVE_ALCAMPO_TESTS"),
        reason="test de contrato en vivo, deshabilitado por defecto (ver docstring del modulo)",
    ),
]


def test_category_tree_shape():
    with AlcampoClient(AlcampoClientConfig()) as client:
        tree = client.get_category_tree()

    assert isinstance(tree, list)
    assert len(tree) > 0
    node = tree[0]
    for key in ("name", "retailerCategoryId", "categoryId", "productCount", "childCategories"):
        assert key in node, f"la API cambio de forma: falta la clave {key!r} en un nodo de categoria"


def test_category_listing_shape():
    with AlcampoClient(AlcampoClientConfig()) as client:
        products = list(client.iter_category_products("OCDesnatada", max_page_size=5))

    assert len(products) > 0
    product = products[0]
    for key in ("retailerProductId", "name", "brand", "price", "available"):
        assert key in product, f"la API cambio de forma: falta la clave {key!r} en un producto"
    assert "amount" in product["price"]


def test_product_detail_shape():
    """El endpoint bop sigue trayendo la tabla nutricional parseable."""
    from menu_app.normalizacion.detalle import parsear_detalle

    with AlcampoClient(AlcampoClientConfig()) as client:
        # 54186 = AUCHAN Leche desnatada, producto envasado con nutricion.
        detalle = parsear_detalle(client.get_product_detail("54186"))

    assert detalle.tiene_nutricion(), "el endpoint bop dejo de traer nutricion parseable"
    assert detalle.energia_kcal_100g is not None
    assert detalle.ingredientes is not None
