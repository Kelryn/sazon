"""Extrae recetas de webs ES con recipe-scrapers (wild_mode / schema.org).

`recipe-scrapers` lanza excepcion en cuanto un campo no esta en el JSON-LD; por
eso cada campo se extrae de forma defensiva (si falta, queda a None) y una
receta sin el schema simplemente se descarta (devuelve None), sin tumbar la
ingesta. Peticiones con rate limit, User-Agent honesto y cache en disco.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

import httpx
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import NoSchemaFoundInWildMode

from ..ingesta.cache import HttpCache
from ..ingesta.rate_limit import RateLimiter
from .modelos import Receta
from .parseo_ingredientes import parsear_ingrediente

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 MenuAlcampoApp/0.1 (proyecto personal, menu semanal)"
)

# Enlaces a recetas de la fuente (recetasgratis / recetas.elperiodico.com).
_LINK_RECETA = re.compile(r"https://recetas\.elperiodico\.com/receta-de-[a-z0-9-]+\.html", re.I)


def _id_desde_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _safe(fn, transform=None):
    """Llama a un getter de recipe-scrapers y devuelve None si falla."""
    try:
        valor = fn()
    except Exception:  # noqa: BLE001 - recipe-scrapers lanza si el campo no esta
        return None
    if valor in (None, "", []):
        return None
    return transform(valor) if transform else valor


def _raciones(texto) -> int | None:
    m = re.search(r"\d+", str(texto))
    return int(m.group()) if m else None


class RecetaScraper:
    def __init__(
        self,
        cache_dir: str | Path = ".cache/recetas",
        min_request_interval_seconds: float = 2.0,
        jitter_seconds: float = 1.0,
        cache_ttl_seconds: int = 30 * 24 * 3600,
        timeout_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds, headers={"User-Agent": user_agent}, follow_redirects=True
        )
        self._cache = HttpCache(cache_dir)
        self._rate_limiter = RateLimiter(min_request_interval_seconds, jitter_seconds)
        self._cache_ttl = cache_ttl_seconds

    def __enter__(self) -> "RecetaScraper":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()
        self._cache.close()

    def _get_html(self, url: str) -> str:
        cache_key = self._cache.make_key("receta_html", {"url": url})
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        self._rate_limiter.wait()
        resp = self._client.get(url)
        resp.raise_for_status()
        self._cache.set(cache_key, resp.text, self._cache_ttl)
        return resp.text

    def scrape(self, url: str) -> Receta | None:
        """Devuelve la Receta, o None si la pagina no tiene schema de receta."""
        html = self._get_html(url)
        return parsear_html(html, url)

    def scrape_con_enlaces(self, url: str) -> tuple[Receta | None, list[str]]:
        """Como scrape, pero ademas devuelve los enlaces a recetas relacionadas
        de la MISMA descarga (para crawl+ingesta en una sola peticion por pagina)."""
        html = self._get_html(url)
        receta = parsear_html(html, url)
        enlaces = list(dict.fromkeys(_LINK_RECETA.findall(html)))
        return receta, enlaces


def parsear_html(html: str, url: str) -> Receta | None:
    """Parsea el HTML de una receta a `Receta` (sin red; testeable). None si no
    hay schema de receta o no se puede sacar ni el titulo."""
    try:
        s = scrape_html(html, org_url=url, supported_only=False)
    except NoSchemaFoundInWildMode:
        logger.info("Sin schema de receta: %s", url)
        return None

    titulo = _safe(s.title)
    if not titulo:
        return None

    ingredientes_raw = _safe(s.ingredients) or []
    ingredientes = [parsear_ingrediente(t) for t in ingredientes_raw if t and t.strip()]

    return Receta(
        id=_id_desde_url(url),
        url=url,
        fuente=urlparse(url).netloc.replace("www.", ""),
        titulo=titulo,
        raciones=_safe(s.yields, _raciones),
        tiempo_total_min=_safe(s.total_time, lambda v: int(v) if v else None),
        categoria=_safe(s.category),
        cocina=_safe(s.cuisine),
        rating=_safe(s.ratings, lambda v: round(float(v), 2)),
        rating_count=_safe(getattr(s, "ratings_count", lambda: None), lambda v: int(v)),
        imagen=_safe(s.image),
        instrucciones=_safe(s.instructions),
        ingredientes=ingredientes,
    )
