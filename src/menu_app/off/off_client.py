"""Cliente de búsqueda de Open Food Facts (por texto).

OFF no tiene el EAN de nuestros productos, asi que buscamos por nombre+marca
con su buscador de texto (`cgi/search.pl`). Su servidor de busqueda se
sobrecarga a menudo y responde 503; por eso hay reintentos con backoff y un
rate limit conservador. Las respuestas se cachean en disco para que re-ejecutar
el cruce no vuelva a golpear OFF.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..ingesta.cache import HttpCache
from ..ingesta.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
FIELDS = "code,product_name,brands,nutriscore_grade,nova_group,allergens_tags"

# OFF pide identificarse con un User-Agent honesto y ser gentil con su servidor.
DEFAULT_USER_AGENT = (
    "MenuAlcampoApp/0.1 (proyecto personal, contacto: kelryn123.1@gmail.com)"
)


class _OFFUnavailable(Exception):
    """OFF respondio 5xx/429 o no-JSON: reintentar con backoff."""


class OFFClient:
    def __init__(
        self,
        cache_dir: str | Path = ".cache/off",
        min_request_interval_seconds: float = 3.0,
        jitter_seconds: float = 1.0,
        cache_ttl_seconds: int = 30 * 24 * 3600,
        page_size: int = 5,
        timeout_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds, headers={"User-Agent": user_agent}, follow_redirects=True
        )
        self._cache = HttpCache(cache_dir)
        self._rate_limiter = RateLimiter(min_request_interval_seconds, jitter_seconds)
        self._cache_ttl = cache_ttl_seconds
        self._page_size = page_size

    def __enter__(self) -> OFFClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()
        self._cache.close()

    def buscar(self, texto: str) -> list[dict[str, Any]]:
        """Devuelve productos candidatos de OFF para un texto de busqueda."""
        params = {
            "search_terms": texto,
            "json": 1,
            "page_size": self._page_size,
            "fields": FIELDS,
        }
        cache_key = self._cache.make_key("off_search", params)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = self._buscar_con_retry(params)
        productos = data.get("products", [])
        self._cache.set(cache_key, productos, self._cache_ttl)
        return productos

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_OFFUnavailable),
    )
    def _buscar_con_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        self._rate_limiter.wait()
        resp = self._client.get(SEARCH_URL, params=params)
        if resp.status_code >= 500 or resp.status_code == 429:
            raise _OFFUnavailable(f"OFF HTTP {resp.status_code}")
        if not resp.headers.get("content-type", "").startswith("application/json"):
            raise _OFFUnavailable("OFF devolvio contenido no-JSON")
        return resp.json()
