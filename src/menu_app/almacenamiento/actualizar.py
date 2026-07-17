"""Actualizacion del catalogo de Alcampo como funcion invocable (UI web).

Mismo pipeline que `menu-app-cargar-bd` (extraer -> normalizar -> upsert con
historico de precios), pero como funcion con callback de progreso para poder
lanzarlo desde la interfaz en segundo plano. Si el catalogo ya existe, actua de
ACTUALIZACION: refresca precios/ofertas y añade productos nuevos (upsert).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ..ingesta.alcampo_client import AlcampoClient, AlcampoClientConfig
from ..ingesta.categories import FOOD_CATEGORY_ROOTS
from ..ingesta.models import product_from_decorated
from ..normalizacion.clasificacion import (
    DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS,
    DEFAULT_KEYWORDS_EXCLUIDAS,
    ConfigClasificacion,
)
from ..normalizacion.limpieza import normalizar_producto
from .db import get_connection, init_db
from .repositorio import ProductoRepository


def _config_clasificacion(cfg: dict) -> ConfigClasificacion:
    norm = cfg.get("normalizacion", {}) or {}
    raices = norm.get("categorias_raiz_excluidas")
    keywords = norm.get("subcategorias_excluidas_keywords")
    alcohol = norm.get("subcat_alcohol_cocina")
    kwargs = dict(
        categorias_raiz_excluidas=tuple(raices) if raices else DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS,
        keywords_excluidas=tuple(keywords) if keywords else DEFAULT_KEYWORDS_EXCLUIDAS,
    )
    if alcohol:
        kwargs["subcat_alcohol_cocina"] = tuple(alcohol)
    return ConfigClasificacion(**kwargs)


def actualizar_catalogo(
    cfg: dict,
    progreso: Callable[[str], None] = lambda _m: None,
    refrescar_precios: bool = True,
    categorias: list[str] | None = None,
) -> dict:
    """Extrae/actualiza el catalogo y lo vuelca en SQLite. Devuelve el resumen.

    `refrescar_precios=True` ignora la cache de paginas de producto (TTL=0) para
    traer precios y ofertas frescos; el arbol de categorias si se cachea.
    `categorias`: ids de categoria raiz a recorrer (None = las de config o todas).
    """
    ingesta_cfg = cfg.get("ingesta", {}) or {}
    almac_cfg = cfg.get("almacenamiento", {}) or {}
    db_path = Path(almac_cfg.get("db_path", "data/menu.db"))
    root_ids = set(categorias or ingesta_cfg.get("category_roots") or FOOD_CATEGORY_ROOTS.keys())
    config_clas = _config_clasificacion(cfg)

    client_config = AlcampoClientConfig(
        cache_dir=Path(ingesta_cfg.get("cache_dir", ".cache/alcampo")),
        min_request_interval_seconds=float(ingesta_cfg.get("min_request_interval_seconds", 1.5)),
        max_request_interval_jitter_seconds=float(
            ingesta_cfg.get("max_request_interval_jitter_seconds", 0.5)
        ),
        category_tree_ttl_seconds=int(ingesta_cfg.get("category_tree_ttl_hours", 24)) * 3600,
        product_page_ttl_seconds=(
            0 if refrescar_precios else int(ingesta_cfg.get("product_page_ttl_hours", 6)) * 3600
        ),
    )

    ahora = datetime.now(UTC)
    fecha_extraccion = ahora.date().isoformat()
    fecha_actualizacion = ahora.isoformat(timespec="seconds")

    conn = get_connection(db_path)
    init_db(conn)
    repo = ProductoRepository(conn)

    seen_ids: set[str] = set()
    normalizados = []
    with AlcampoClient(client_config) as client:
        leaves = list(client.iter_leaf_categories(root_ids))
        progreso(f"Categorias a recorrer: {len(leaves)}")
        for i, leaf in enumerate(leaves, start=1):
            progreso(f"[{i}/{len(leaves)}] {' > '.join(leaf['path'])}")
            for raw in client.iter_category_products(leaf["retailerCategoryId"]):
                rpid = raw.get("retailerProductId")
                if rpid and rpid in seen_ids:
                    continue
                if rpid:
                    seen_ids.add(rpid)
                producto = product_from_decorated(raw, leaf["path"], fecha_extraccion)
                normalizados.append(normalizar_producto(producto, config_clas))

    resumen = repo.upsert_muchos(normalizados, fecha_actualizacion)
    conn.close()
    progreso(
        f"Hecho: {resumen['procesados']} productos ({resumen['nuevos']} nuevos, "
        f"{resumen['cambios_precio']} cambios de precio)."
    )
    return resumen
