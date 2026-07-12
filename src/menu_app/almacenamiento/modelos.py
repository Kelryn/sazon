from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProductoNormalizado:
    """Producto ya limpio, tal como se guarda en SQLite.

    A diferencia del `Product` de ingesta (donde precios y cantidades son
    cadenas tal cual las da Alcampo), aqui los numeros son floats y el formato
    esta parseado en cantidad + unidad, listo para consultas y para el
    matching/optimizacion de fases posteriores.
    """

    retailer_product_id: str
    nombre: str
    marca: str | None
    categoria: str
    subcategoria: str
    precio_eur: float | None
    precio_por_unidad: float | None
    unidad_medida: str | None
    formato: str | None
    cantidad_formato: float | None
    unidad_formato: str | None
    cantidad_base_g_ml: float | None
    tipo_medida: str | None  # 'peso' | 'volumen' | 'unidad' | None
    disponible: bool
    en_oferta: bool
    precio_oferta: float | None
    url_producto: str
    url_imagen: str | None
    apto_receta: bool
    fecha_extraccion: str
