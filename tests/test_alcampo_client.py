"""Tests offline del AlcampoClient, con la red simulada via pytest-httpx.

No golpean el sitio real -- eso es justo lo que queremos evitar en cada
`pytest` normal. El contrato contra la API real se comprueba aparte, en
test_contract_live.py (deshabilitado por defecto).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from menu_app.ingesta.alcampo_client import AlcampoClient, AlcampoClientConfig
from menu_app.ingesta.exceptions import AlcampoBlockedError

BASE_URL = "https://www.compraonline.alcampo.es"


@pytest.fixture
def client(tmp_path: Path) -> AlcampoClient:
    config = AlcampoClientConfig(
        cache_dir=tmp_path / "cache",
        min_request_interval_seconds=0.0,
        max_request_interval_jitter_seconds=0.0,
    )
    with AlcampoClient(config) as c:
        yield c


def _mock_warmup(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", url=f"{BASE_URL}/", status_code=200)


CATEGORY_TREE_FIXTURE = [
    {
        "name": "Leche, Huevos, Lácteos, Yogures y Bebidas vegetales",
        "retailerCategoryId": "OC16",
        "categoryId": "cat-16",
        "productCount": 1689,
        "childCategories": [
            {
                "name": "Leche",
                "retailerCategoryId": "OC1603",
                "categoryId": "cat-1603",
                "productCount": 120,
                "childCategories": [
                    {
                        "name": "Leche desnatada",
                        "retailerCategoryId": "OCDesnatada",
                        "categoryId": "cat-desnatada",
                        "productCount": 40,
                        "childCategories": [],
                    }
                ],
            }
        ],
    },
    {
        "name": "Droguería",
        "retailerCategoryId": "OCC14",
        "categoryId": "cat-drog",
        "productCount": 2121,
        "childCategories": [],
    },
]


def test_iter_leaf_categories_filters_by_root_and_builds_path(client, httpx_mock):
    _mock_warmup(httpx_mock)
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/webproductpagews/v1/categories",
        json=CATEGORY_TREE_FIXTURE,
    )

    leaves = list(client.iter_leaf_categories(root_ids={"OC16"}))

    assert len(leaves) == 1
    assert leaves[0]["retailerCategoryId"] == "OCDesnatada"
    assert leaves[0]["path"] == [
        "Leche, Huevos, Lácteos, Yogures y Bebidas vegetales",
        "Leche",
        "Leche desnatada",
    ]


def test_iter_leaf_categories_without_filter_returns_all_leaves(client, httpx_mock):
    _mock_warmup(httpx_mock)
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/webproductpagews/v1/categories",
        json=CATEGORY_TREE_FIXTURE,
    )

    leaves = list(client.iter_leaf_categories())

    retailer_ids = {leaf["retailerCategoryId"] for leaf in leaves}
    assert retailer_ids == {"OCDesnatada", "OCC14"}


def _product(retailer_product_id: str) -> dict:
    return {
        "productId": f"guid-{retailer_product_id}",
        "retailerProductId": retailer_product_id,
        "name": f"Producto {retailer_product_id}",
        "brand": "MARCA",
        "price": {"amount": "1.23", "currency": "EUR"},
        "available": True,
        "promotions": [],
    }


def test_iter_category_products_paginates_via_cursor(client, httpx_mock):
    _mock_warmup(httpx_mock)
    # Pagina 1: sin pageToken en la URL, trae nextPageToken="abc".
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r"^(?:(?!pageToken).)*retailerCategoryId=OC15(?:(?!pageToken).)*$"),
        json={
            "productGroups": [{"decoratedProducts": [_product("1"), _product("2")]}],
            "metadata": {"nextPageToken": "abc"},
        },
    )
    # Pagina 2: URL con pageToken=abc, ya no trae nextPageToken -> se acaba.
    httpx_mock.add_response(
        method="GET",
        url=re.compile(r".*pageToken=abc.*"),
        json={
            "productGroups": [{"decoratedProducts": [_product("3")]}],
            "metadata": {},
        },
    )

    products = list(client.iter_category_products("OC15", max_page_size=50))

    assert [p["retailerProductId"] for p in products] == ["1", "2", "3"]


def test_403_raises_alcampo_blocked_error_and_does_not_retry(client, httpx_mock):
    _mock_warmup(httpx_mock)
    httpx_mock.add_response(method="GET", status_code=403)

    with pytest.raises(AlcampoBlockedError):
        list(client.iter_category_products("OC15"))

    # Warm-up (1) + un unico intento a product-pages (1), sin reintentos.
    assert len(httpx_mock.get_requests()) == 2


def test_5xx_is_retried_until_success(client, httpx_mock):
    _mock_warmup(httpx_mock)
    httpx_mock.add_response(method="GET", status_code=503)
    httpx_mock.add_response(
        method="GET",
        json={"productGroups": [{"decoratedProducts": [_product("1")]}], "metadata": {}},
    )

    products = list(client.iter_category_products("OC15"))

    assert [p["retailerProductId"] for p in products] == ["1"]


def test_repeated_call_uses_cache_not_network(client, httpx_mock):
    _mock_warmup(httpx_mock)
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/webproductpagews/v1/categories",
        json=CATEGORY_TREE_FIXTURE,
    )

    first = client.get_category_tree()
    second = client.get_category_tree()

    assert first == second
    # warm-up + una sola llamada real al arbol de categorias.
    assert len(httpx_mock.get_requests()) == 2
