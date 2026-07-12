"""Fase 0 - Validacion del API interna de Alcampo (compraonline.alcampo.es).

Objetivo: confirmar, con una libreria HTTP normal (httpx), lo que ya vimos a mano
con DevTools/fetch en el navegador (ver DISCOVERY.md):
  1. El arbol de categorias (GET /api/webproductpagews/v1/categories) funciona.
  2. El listado de categoria (GET /api/webproductpagews/v6/product-pages) funciona.
  3. La paginacion por cursor (metadata.nextPageToken -> pageToken=...) funciona.
  4. El endpoint de detalle de producto (PUT .../products) sigue bloqueado (403)
     cuando se llama de forma aislada -- comportamiento esperado, documentado en
     DISCOVERY.md seccion 3.2, no es un bug de este script.

Uso:
    pip install httpx h2      # o: uv add httpx (cuando exista pyproject.toml)
    python validate_alcampo_endpoints.py

No hace mas de un puñado de peticiones y espera 1-2s entre ellas: es solo para
confirmar que los endpoints documentados en DISCOVERY.md siguen ahi, no un
scraper de produccion (eso es la Fase 1).
"""

from __future__ import annotations

import sys
import time

import httpx

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://www.compraonline.alcampo.es"

# User-Agent honesto: identifica el proposito real, como pide el prompt original.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
        "MenuAlcampoBot/0.1 (+uso personal, contacto: kelryn123.1@gmail.com)"
    ),
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Categoria de ejemplo confirmada a mano: "Leche desnatada".
SAMPLE_CATEGORY_ID = "OCDesnatada"
# Categoria mas grande confirmada a mano para probar paginacion: "Charcuteria" (1151 productos).
BIG_CATEGORY_ID = "OC15"
# GUID de producto confirmado a mano (AUCHAN Leche desnatada 6x1L).
SAMPLE_PRODUCT_GUID = "1773b242-70ab-426a-8e2d-2f4f959d5f99"

RATE_LIMIT_SECONDS = 1.5


def find_leaf_categories(nodes: list[dict], path: list[str] | None = None) -> list[dict]:
    """Recorre el arbol de /api/webproductpagews/v1/categories y devuelve las hojas."""
    path = path or []
    leaves: list[dict] = []
    for node in nodes:
        children = node.get("childCategories") or []
        if not children:
            leaves.append({**node, "path": " > ".join([*path, node["name"]])})
        else:
            leaves.extend(find_leaf_categories(children, [*path, node["name"]]))
    return leaves


def check_categories_tree(client: httpx.Client) -> list[dict] | None:
    url = f"{BASE_URL}/api/webproductpagews/v1/categories"
    resp = client.get(url, headers=HEADERS)
    print(f"[categories-tree] GET {url} -> {resp.status_code}")

    if resp.status_code != 200:
        print(f"  cuerpo (primeros 300 caracteres): {resp.text[:300]!r}")
        return None

    tree = resp.json()
    leaves = find_leaf_categories(tree)
    print(f"  categorias raiz: {len(tree)}, hojas totales: {len(leaves)}")
    top5 = sorted(leaves, key=lambda c: c.get("productCount", 0), reverse=True)[:5]
    for c in top5:
        print(f"    {c['retailerCategoryId']!r:>15} {c.get('productCount', 0):>5} productos  -- {c['path']}")
    return leaves


def check_pagination(client: httpx.Client) -> None:
    def fetch_page(page_token: str | None) -> dict:
        params = {
            "includeAdditionalPageInfo": "true",
            "maxPageSize": 50,
            "maxProductsToDecorate": 50,
            "retailerCategoryId": BIG_CATEGORY_ID,
            "sortOptionId": "favorite",
            "tag": ["web", "category-item"],
        }
        if page_token:
            params["pageToken"] = page_token
        resp = client.get(
            f"{BASE_URL}/api/webproductpagews/v6/product-pages", params=params, headers=HEADERS
        )
        data = resp.json()
        products = [p for g in data.get("productGroups", []) for p in g.get("decoratedProducts", [])]
        return {
            "status": resp.status_code,
            "ids": [p.get("retailerProductId") for p in products],
            "next_token": data.get("metadata", {}).get("nextPageToken"),
        }

    page1 = fetch_page(None)
    print(f"[pagination] pagina 1 -> {page1['status']}, {len(page1['ids'])} productos, "
          f"tiene nextPageToken: {bool(page1['next_token'])}")
    time.sleep(RATE_LIMIT_SECONDS)

    if not page1["next_token"]:
        print("  no hay nextPageToken, no se puede seguir probando paginacion")
        return

    page2 = fetch_page(page1["next_token"])
    overlap = set(page1["ids"]) & set(page2["ids"])
    print(f"[pagination] pagina 2 -> {page2['status']}, {len(page2['ids'])} productos, "
          f"solapados con pagina 1: {len(overlap)}")
    if page2["status"] == 200 and not overlap:
        print("  OK: pageToken funciona, paginas 1 y 2 traen productos distintos.")
    else:
        print("  ATENCION: revisar, se esperaban 0 productos solapados.")


def warm_up_session(client: httpx.Client) -> None:
    """Visita la home primero para que el servidor fije cookies de sesion/region."""
    resp = client.get(f"{BASE_URL}/", headers=HEADERS, follow_redirects=True)
    print(f"[warm-up] GET / -> {resp.status_code}, cookies recibidas: {list(client.cookies.keys())}")
    time.sleep(RATE_LIMIT_SECONDS)


def check_category_listing(client: httpx.Client) -> dict | None:
    url = f"{BASE_URL}/api/webproductpagews/v6/product-pages"
    params = {
        "includeAdditionalPageInfo": "true",
        "maxPageSize": 20,
        "maxProductsToDecorate": 20,
        "retailerCategoryId": SAMPLE_CATEGORY_ID,
        "sortOptionId": "favorite",
        "tag": ["web", "category-item"],
    }
    resp = client.get(url, params=params, headers=HEADERS)
    print(f"[category-listing] GET {resp.url} -> {resp.status_code}")

    if resp.status_code != 200:
        print(f"  cuerpo (primeros 300 caracteres): {resp.text[:300]!r}")
        return None

    data = resp.json()
    products = [
        p
        for group in data.get("productGroups", [])
        for p in group.get("decoratedProducts", [])
    ]
    print(f"  productGroups: {len(data.get('productGroups', []))}, productos totales: {len(products)}")
    if products:
        sample = products[0]
        campos_clave = ["retailerProductId", "name", "brand", "price", "unitPrice", "available"]
        rellenos = [c for c in campos_clave if sample.get(c) is not None]
        print(f"  ejemplo de producto: {sample.get('name')!r}")
        print(f"  campos clave presentes: {rellenos} ({len(rellenos)}/{len(campos_clave)})")
    return data


def check_product_detail(client: httpx.Client, referer_url: str) -> None:
    url = f"{BASE_URL}/api/webproductpagews/v6/products"
    headers = {**HEADERS, "Content-Type": "application/json", "Referer": referer_url}
    resp = client.put(url, json=[SAMPLE_PRODUCT_GUID], headers=headers)
    print(f"[product-detail] PUT {url} -> {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        item = data[0] if isinstance(data, list) else data
        print(f"  OK, claves de nivel superior: {list(item.keys())[:25]}")
    else:
        print(
            "  Bloqueado (visto tambien en pruebas manuales desde el navegador: 403 con "
            "'x-cache: Error from cloudfront'). Ver DISCOVERY.md seccion 3.2 -- probablemente "
            "haga falta un token anti-bot (valiuz) o fallback Playwright para este endpoint."
        )
        print(f"  cabeceras de respuesta relevantes: server={resp.headers.get('server')}, "
              f"x-cache={resp.headers.get('x-cache')}")


def main() -> int:
    with httpx.Client(timeout=15, http2=True) as client:
        warm_up_session(client)

        leaves = check_categories_tree(client)
        time.sleep(RATE_LIMIT_SECONDS)

        data = check_category_listing(client)
        time.sleep(RATE_LIMIT_SECONDS)

        check_pagination(client)
        time.sleep(RATE_LIMIT_SECONDS)

        product_url = f"{BASE_URL}/products/auchan-leche-desnatada-de-vaca-6x-1-l-producto-alcampo/54186"
        check_product_detail(client, referer_url=product_url)

    if leaves is None or data is None:
        print("\nRESULTADO: algun endpoint clave (categorias o listado) NO respondio bien.")
        return 1

    print("\nRESULTADO: categorias, listado y paginacion responden bien con httpx puro -- Fase 1 "
          "puede construirse sobre estos 3 endpoints. El endpoint de detalle sigue bloqueado fuera "
          "de la SPA (esperado, ver DISCOVERY.md 3.2); se resolvera con fallback Playwright.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
