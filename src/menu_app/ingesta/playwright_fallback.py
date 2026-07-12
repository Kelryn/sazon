"""Fallback con Playwright para datos que el anti-bot de Alcampo bloquea via httpx.

Ver DISCOVERY.md seccion 3.2: tanto el detalle de producto
(PUT /api/webproductpagews/v6/products, con nutricion/EAN/ingredientes/
alergenos) como el cambio de codigo postal devuelven 403 cuando se llaman de
forma aislada, aunque funcionan perfectamente cuando los dispara la propia SPA
navegando de forma normal.

En vez de intentar reconstruir esas peticiones a mano (lo que equivaldria a
intentar evadir activamente su proteccion anti-bot), este modulo abre la
pagina real en un navegador y deja que sea la propia web quien dispare la
llamada, capturando la respuesta ya "legitimada" por el navegador.

Deliberadamente NO forma parte de AlcampoClient: es una estrategia de acceso
distinta (mas lenta, con Chromium de por medio), pensada para usarse puntual y
cacheada por producto, nunca en el camino critico del listado de catalogo
(ese va entero por AlcampoClient, ver alcampo_client.py).

Requiere el extra opcional `playwright`:
    uv sync --extra playwright
    uv run playwright install chromium
"""

from __future__ import annotations

from typing import Any

PRODUCT_DETAIL_PATH_FRAGMENT = "/api/webproductpagews/v6/products"


def fetch_product_detail_via_browser(
    retailer_product_id: str,
    slug: str = "producto",
    timeout_ms: int = 20_000,
) -> dict[str, Any] | None:
    """Abre la ficha de un producto y devuelve el JSON de detalle que la propia
    pagina pide internamente, o None si no se llego a capturar a tiempo.

    El slug es cosmetico (confirmado en vivo: la web redirige a la URL
    canonica solo con el ID), asi que el valor por defecto "producto" sirve
    para cualquier retailer_product_id.
    """
    from playwright.sync_api import sync_playwright  # import perezoso: extra opcional

    url = f"https://www.compraonline.alcampo.es/products/{slug}/{retailer_product_id}"
    captured: dict[str, Any] = {}

    def handle_response(response: Any) -> None:
        if response.request.method == "PUT" and PRODUCT_DETAIL_PATH_FRAGMENT in response.url:
            try:
                captured["data"] = response.json()
            except Exception:  # noqa: BLE001 - respuesta no JSON, se ignora
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.on("response", handle_response)
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        finally:
            browser.close()

    return captured.get("data")
