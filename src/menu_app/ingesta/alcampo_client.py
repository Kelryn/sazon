from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .cache import HttpCache
from .exceptions import AlcampoAPIError, AlcampoBlockedError
from .rate_limit import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://www.compraonline.alcampo.es"
CATEGORY_TREE_PATH = "/api/webproductpagews/v1/categories"
PRODUCT_PAGES_PATH = "/api/webproductpagews/v6/product-pages"
# Detalle de producto (nutricion, ingredientes, origen). A diferencia del PUT
# de /products (bloqueado por el anti-bot), este GET si funciona con httpx.
PRODUCT_DETAIL_PATH = "/api/webproductpagews/v5/products/bop"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "MenuAlcampoBot/0.1 (+uso personal, contacto: kelryn123.1@gmail.com)"
)


class _RetryableStatusError(Exception):
    """Error interno para que tenacity reintente solo en 5xx/429, nunca en 403/404."""


@dataclass
class AlcampoClientConfig:
    base_url: str = BASE_URL
    min_request_interval_seconds: float = 1.5
    max_request_interval_jitter_seconds: float = 0.5
    cache_dir: Path = Path(".cache/alcampo")
    category_tree_ttl_seconds: int = 24 * 3600
    product_page_ttl_seconds: int = 6 * 3600
    timeout_seconds: float = 15.0
    user_agent: str = DEFAULT_USER_AGENT


class AlcampoClient:
    """Cliente de la API interna de Alcampo (Ocado Smart Platform).

    Cubre solo los endpoints GET de solo lectura confirmados en DISCOVERY.md
    (arbol de categorias + listado de categoria paginado por cursor). Esos dos
    endpoints bastan para el catalogo (nombre, marca, precio, promociones,
    imagenes). El endpoint de detalle de producto (nutricion/EAN/ingredientes)
    esta bloqueado por su anti-bot fuera del flujo real de la SPA -- para eso
    esta el fallback de playwright_fallback.py, deliberadamente fuera de esta
    clase para no mezclar las dos estrategias de acceso.
    """

    def __init__(self, config: AlcampoClientConfig | None = None) -> None:
        self.config = config or AlcampoClientConfig()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            http2=True,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9",
            },
            follow_redirects=True,
        )
        self._cache = HttpCache(self.config.cache_dir)
        self._rate_limiter = RateLimiter(
            self.config.min_request_interval_seconds,
            self.config.max_request_interval_jitter_seconds,
        )
        self._warmed_up = False

    def __enter__(self) -> AlcampoClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()
        self._cache.close()

    def warm_up(self) -> None:
        """Visita la home una vez para que el servidor fije cookies de sesion/region.

        Con IP de Madrid esto ya deja la sesion en la region correcta por geo-IP
        (ver DISCOVERY.md seccion 5) -- no hace falta fijar un codigo postal.
        """
        if self._warmed_up:
            return
        self._rate_limiter.wait()
        resp = self._client.get("/")
        resp.raise_for_status()
        self._warmed_up = True
        logger.info("warm-up OK, cookies: %s", list(self._client.cookies.keys()))

    def _get_json(self, path: str, params: dict[str, Any], ttl_seconds: int) -> dict[str, Any]:
        cache_key = self._cache.make_key(path, params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        self.warm_up()
        data = self._get_json_with_retry(path, params)
        self._cache.set(cache_key, data, ttl_seconds)
        return data

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type(_RetryableStatusError),
    )
    def _get_json_with_retry(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self._rate_limiter.wait()
        resp = self._client.get(path, params=params)

        if resp.status_code == 403:
            raise AlcampoBlockedError(
                f"403 en {path} -- bloqueado por el anti-bot (ver DISCOVERY.md 3.2)."
            )
        if resp.status_code >= 500 or resp.status_code == 429:
            raise _RetryableStatusError(f"HTTP {resp.status_code} en {path}")
        if resp.status_code != 200:
            raise AlcampoAPIError(
                f"HTTP inesperado {resp.status_code} en {path}: {resp.text[:200]!r}"
            )

        return resp.json()

    def get_category_tree(self) -> list[dict[str, Any]]:
        return self._get_json(
            CATEGORY_TREE_PATH, params={}, ttl_seconds=self.config.category_tree_ttl_seconds
        )

    def get_product_detail(self, retailer_product_id: str) -> dict[str, Any]:
        """Detalle de un producto (nutricion, ingredientes, origen) via `bop`.

        Devuelve el JSON crudo; el parseo a campos limpios lo hace
        normalizacion/detalle.py. Se cachea con el mismo TTL que los listados.
        """
        return self._get_json(
            PRODUCT_DETAIL_PATH,
            params={"retailerProductId": retailer_product_id},
            ttl_seconds=self.config.product_page_ttl_seconds,
        )

    def iter_leaf_categories(self, root_ids: set[str] | None = None) -> Iterator[dict[str, Any]]:
        """Recorre el arbol de categorias y devuelve las hojas (sin sub-categorias).

        Si `root_ids` se indica, solo desciende por esas ramas de nivel superior
        (p.ej. las categorias de alimentacion, ver categories.py).
        """
        tree = self.get_category_tree()
        roots = tree if root_ids is None else [n for n in tree if n["retailerCategoryId"] in root_ids]
        yield from self._walk_leaves(roots, path=[])

    def _walk_leaves(
        self, nodes: list[dict[str, Any]], path: list[str]
    ) -> Iterator[dict[str, Any]]:
        for node in nodes:
            children = node.get("childCategories") or []
            node_path = [*path, node["name"]]
            if not children:
                yield {**node, "path": node_path}
            else:
                yield from self._walk_leaves(children, node_path)

    def iter_category_products(
        self, retailer_category_id: str, max_page_size: int = 300
    ) -> Iterator[dict[str, Any]]:
        """Pagina un listado de categoria completo via metadata.nextPageToken.

        Confirmado en vivo (DISCOVERY.md 3.1): es paginacion por cursor, no por
        numero de pagina -- se sigue mientras `nextPageToken` no sea nulo.
        """
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "includeAdditionalPageInfo": "true",
                "maxPageSize": max_page_size,
                "maxProductsToDecorate": max_page_size,
                "retailerCategoryId": retailer_category_id,
                "sortOptionId": "favorite",
                "tag": ["web", "category-item"],
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._get_json(
                PRODUCT_PAGES_PATH, params=params, ttl_seconds=self.config.product_page_ttl_seconds
            )
            for group in data.get("productGroups", []):
                yield from group.get("decoratedProducts", [])

            page_token = (data.get("metadata") or {}).get("nextPageToken")
            if not page_token:
                break
