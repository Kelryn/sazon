"""Descubre URLs de recetas y provee el dataset de arranque.

Las webs ES de recetas exponen sus URLs en sitemaps. Aqui se leen y se filtran
a las que son recetas de verdad (patron `receta-de-...`), descartando articulos.
El dataset de arranque son unas pocas recetas variadas ya verificadas, para
poder probar la ingesta sin depender de que un sitemap concreto responda.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "MenuAlcampoApp/0.1 (proyecto personal, menu semanal)"

# Fuentes de recetasgratis (dominio real: recetas.elperiodico.com).
SITEMAP_RECETASGRATIS = (
    "https://recetas.elperiodico.com/sitemaps/sitemap-recetasgratis-es-news.xml"
)
HOME_RECETASGRATIS = "https://recetas.elperiodico.com/"

# Solo las URLs que son receta (no articulos de blog).
_PATRON_RECETA = re.compile(r"/receta-de-", re.IGNORECASE)
_LINK_RECETA = re.compile(r"https://recetas\.elperiodico\.com/receta-de-[a-z0-9-]+\.html", re.I)

# Dataset de arranque: recetas ES reales y variadas, verificadas (200 + con
# schema). El id final de la URL es lo que identifica la receta en esta web.
DATASET_ARRANQUE: list[str] = [
    "https://recetas.elperiodico.com/receta-de-ajoblanco-de-la-abuela-el-plato-andaluz-que-siempre-triunfa-en-verano-y-se-prepara-en-solo-unos-minutos-78880.html",
    "https://recetas.elperiodico.com/receta-de-galletas-de-avena-faciles-y-rapidas-67303.html",
    "https://recetas.elperiodico.com/receta-de-galletas-de-mantequilla-caseras-31553.html",
    "https://recetas.elperiodico.com/receta-de-huevos-rellenos-de-atun-y-mayonesa-faciles-jugosos-y-perfectos-para-los-dias-de-mas-calor-78790.html",
    "https://recetas.elperiodico.com/receta-de-mousse-de-chocolate-con-solo-3-ingredientes-cremosa-facil-y-rapida-78832.html",
    "https://recetas.elperiodico.com/receta-de-pastel-frio-de-pollo-fresco-cremoso-y-muy-facil-de-hacer-78643.html",
    "https://recetas.elperiodico.com/receta-de-salmorejo-sin-pan-con-huevo-duro-la-version-mas-ligera-cremosa-y-rica-en-proteinas-78887.html",
    "https://recetas.elperiodico.com/receta-de-torta-tres-leches-8910.html",
]

# Dataset de arranque en INGLES (webs con soporte nativo en recipe-scrapers).
# Las medidas imperiales (cups, oz, lb...) se convierten a metrico al parsear.
DATASET_ARRANQUE_EN: list[str] = [
    "https://www.allrecipes.com/recipe/23600/worlds-best-lasagna/",
    "https://www.allrecipes.com/recipe/16354/easy-meatloaf/",
    "https://www.bbcgoodfood.com/recipes/best-spaghetti-bolognese-recipe",
    "https://www.bbcgoodfood.com/recipes/easy-chicken-curry",
    "https://www.seriouseats.com/the-best-slow-cooked-bolognese-sauce-recipe",
]


def dataset_arranque_completo() -> list[str]:
    """Recetas de arranque en español e ingles."""
    return list(DATASET_ARRANQUE) + list(DATASET_ARRANQUE_EN)


def urls_desde_sitemap(sitemap_url: str = SITEMAP_RECETASGRATIS, timeout: float = 30.0) -> list[str]:
    """Devuelve las URLs de receta (no articulos) que haya en un sitemap."""
    resp = httpx.get(
        sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", resp.text)
    return [u for u in locs if _PATRON_RECETA.search(u)]


def urls_desde_pagina(pagina_url: str = HOME_RECETASGRATIS, timeout: float = 30.0) -> list[str]:
    """Extrae los enlaces de receta que aparecen en una pagina de listado
    (home, categoria...). Mas productivo que el sitemap de noticias, que es
    pequeño. Devuelve URLs unicas conservando el orden de aparicion."""
    resp = httpx.get(
        pagina_url, headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    return list(dict.fromkeys(_LINK_RECETA.findall(resp.text)))


# Semillas saladas y ricas en proteina para arrancar el crawl (URLs verificadas,
# con atun/pollo/huevo). Sus "recetas relacionadas" son saladas-afines.
SEMILLAS_SALADAS: list[str] = [
    "https://recetas.elperiodico.com/receta-de-ajoblanco-de-la-abuela-el-plato-andaluz-que-siempre-triunfa-en-verano-y-se-prepara-en-solo-unos-minutos-78880.html",
    "https://recetas.elperiodico.com/receta-de-huevos-rellenos-de-atun-y-mayonesa-faciles-jugosos-y-perfectos-para-los-dias-de-mas-calor-78790.html",
    "https://recetas.elperiodico.com/receta-de-pastel-frio-de-pollo-fresco-cremoso-y-muy-facil-de-hacer-78643.html",
    "https://recetas.elperiodico.com/receta-de-salmorejo-sin-pan-con-huevo-duro-la-version-mas-ligera-cremosa-y-rica-en-proteinas-78887.html",
]


# Categorias-listado (…-busqCate-N.html) de PLATOS PRINCIPALES saludables de
# cocina española/mediterranea e ITALIANA. De aqui se cosechan recetas cuyos
# ingredientes estan casi todos en Alcampo (el objetivo del usuario).
CATEGORIAS_PRINCIPALES: list[str] = [
    # Española / mediterranea (cuchara, guisos, pescado, arroces, huevos)
    "Cocido", "Guiso", "Potajes", "Lentejas", "Garbanzos", "Alubias", "Paella",
    "Arroz-carne", "Tortilla", "Gazpachos", "Sopas", "Cremas", "Pescado-blanco",
    "Salmon", "Bacalao", "Atun", "Calamar", "Pulpo", "Pollo", "Ternera", "Cerdo",
    "Lomo", "Conejo", "Pavo", "Pato", "Berenjena", "calabacin", "Patatas",
    "Verduras-otros", "con-verduras", "Ensalada-saludables", "Ensaladas-con-pescado",
    "Croquetas", "Empanadas",
    # Italiana
    "Espaguetis", "Tallarines", "Lasana", "Pizza", "Pilaf", "Ensalada-pasta",
]

# Busquedas para cocina ITALIANA y GRIEGA (el usuario tiene esos ingredientes).
BUSQUEDAS_MEDITERRANEAS: list[str] = [
    "pasta italiana", "risotto", "lasana", "ñoquis", "canelones", "pesto",
    "caprese", "parmesana", "boloñesa", "carbonara", "minestrone", "focaccia",
    "moussaka", "tzatziki", "souvlaki", "ensalada griega", "gyros", "espanakopita",
    "dolmades", "hummus", "musaka", "pollo al limon griego",
]


def urls_desde_categorias(
    categorias: list[str], paginas: int = 2, intervalo_seg: float = 1.0
) -> list[str]:
    """Cosecha URLs de receta de las paginas de categoria (…-busqCate-N.html)."""
    urls: list[str] = []
    for cat in categorias:
        for n in range(1, paginas + 1):
            pagina = f"https://recetas.elperiodico.com/{cat}-busqCate-{n}.html"
            try:
                urls.extend(urls_desde_pagina(pagina))
            except httpx.HTTPError:
                break  # no hay mas paginas de esa categoria
            time.sleep(intervalo_seg)
    return list(dict.fromkeys(urls))


def urls_desde_busquedas(
    consultas: list[str], intervalo_seg: float = 1.0
) -> list[str]:
    """Cosecha URLs de receta del buscador del sitio para cada consulta."""
    import urllib.parse

    urls: list[str] = []
    headers = {"User-Agent": USER_AGENT}
    for q in consultas:
        url = f"https://recetas.elperiodico.com/busqueda?q={urllib.parse.quote(q)}"
        try:
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            urls.extend(_LINK_RECETA.findall(resp.text))
        except httpx.HTTPError:
            continue
        time.sleep(intervalo_seg)
    return list(dict.fromkeys(urls))


def urls_por_crawl(
    semillas: list[str],
    limite: int = 80,
    intervalo_seg: float = 1.5,
    max_paginas: int | None = None,
) -> list[str]:
    """Rastrea (BFS) recetas siguiendo los enlaces 'recetas relacionadas' de cada
    pagina, empezando por `semillas`, hasta reunir `limite` URLs distintas.

    Es la forma fiable de ampliar el corpus en este sitio (sus sitemaps completos
    estan bloqueados). Respeta un intervalo entre peticiones para ser buen
    ciudadano. `max_paginas` limita cuantas paginas se descargan (por defecto,
    hasta el doble del limite)."""
    max_paginas = max_paginas or limite * 2
    vistas: set[str] = set()
    frontera: deque[str] = deque(dict.fromkeys(semillas))
    recogidas: list[str] = []
    paginas = 0
    headers = {"User-Agent": USER_AGENT}

    while frontera and len(recogidas) < limite and paginas < max_paginas:
        url = frontera.popleft()
        if url in vistas:
            continue
        vistas.add(url)
        try:
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            paginas += 1
            if resp.status_code != 200:
                continue
        except httpx.HTTPError as e:
            logger.warning("crawl: fallo en %s: %s", url, e)
            continue

        if _PATRON_RECETA.search(url):
            recogidas.append(url)
        for enlace in dict.fromkeys(_LINK_RECETA.findall(resp.text)):
            if enlace not in vistas:
                frontera.append(enlace)
        time.sleep(intervalo_seg)

    return recogidas[:limite]
