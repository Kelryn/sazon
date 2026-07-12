"""Limpieza y normalizacion de los productos crudos de Alcampo.

Convierte precios de texto a float y parsea el campo `formato` (p.ej. "6000ml",
"500g", "6 x 1 l", "750g - 1250g") en una cantidad + unidad manejables, mas una
cantidad normalizada a base (gramos o ml) util para comparar y para el matching
posterior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..ingesta.models import Product
from ..almacenamiento.modelos import ProductoNormalizado
from .clasificacion import ConfigClasificacion, es_apto_receta

# Factor de conversion a la unidad base (g para peso, ml para volumen) y tipo.
_UNIDAD_A_BASE: dict[str, tuple[float, str]] = {
    "kg": (1000.0, "peso"),
    "g": (1.0, "peso"),
    "gr": (1.0, "peso"),
    "l": (1000.0, "volumen"),
    "cl": (10.0, "volumen"),
    "ml": (1.0, "volumen"),
}
_UNIDADES_CONTEO = {"ud", "uds", "unidad", "unidades"}

_NUM = r"\d+(?:[.,]\d+)?"


def precio_a_float(valor: str | None) -> float | None:
    """"4,92" o "4.92" -> 4.92. Devuelve None si no hay numero."""
    if not valor:
        return None
    limpio = valor.strip().replace(",", ".")
    try:
        return round(float(limpio), 4)
    except ValueError:
        return None


@dataclass
class FormatoParseado:
    cantidad: float | None
    unidad: str | None
    cantidad_base_g_ml: float | None
    tipo_medida: str | None  # 'peso' | 'volumen' | 'unidad' | None


def parsear_formato(formato: str | None) -> FormatoParseado:
    """Extrae cantidad y unidad del texto de formato de Alcampo.

    Soporta packs ("6 x 1 l" -> 6 l), rangos de peso variable
    ("750g - 1250g" -> punto medio 1000 g) y formatos simples ("500g", "1l",
    "110 g."). Si no reconoce nada, devuelve todo a None.
    """
    if not formato:
        return FormatoParseado(None, None, None, None)

    texto = formato.lower().strip().rstrip(".")

    # Pack tipo "6 x 1 l" o "6x1l": multiplicador x cantidad unidad.
    pack = re.search(rf"(\d+)\s*x\s*({_NUM})\s*([a-z]+)", texto)
    if pack:
        multiplicador = float(pack.group(1))
        cantidad_unit = float(pack.group(2).replace(",", "."))
        unidad = pack.group(3)
        return _construir(multiplicador * cantidad_unit, unidad)

    # Rango de peso variable "750g - 1250g": punto medio.
    rango = re.search(rf"({_NUM})\s*([a-z]+)\s*-\s*({_NUM})\s*([a-z]+)", texto)
    if rango:
        a = float(rango.group(1).replace(",", "."))
        b = float(rango.group(3).replace(",", "."))
        unidad = rango.group(4)
        return _construir((a + b) / 2, unidad)

    # Formato simple "500g", "1 l", "110 g".
    simple = re.search(rf"({_NUM})\s*([a-z]+)", texto)
    if simple:
        cantidad = float(simple.group(1).replace(",", "."))
        unidad = simple.group(2)
        return _construir(cantidad, unidad)

    return FormatoParseado(None, None, None, None)


def _construir(cantidad: float, unidad: str) -> FormatoParseado:
    unidad = unidad.strip()
    if unidad in _UNIDAD_A_BASE:
        factor, tipo = _UNIDAD_A_BASE[unidad]
        return FormatoParseado(cantidad, unidad, round(cantidad * factor, 4), tipo)
    if unidad in _UNIDADES_CONTEO:
        return FormatoParseado(cantidad, "ud", None, "unidad")
    # Unidad no reconocida: guardamos cantidad y unidad pero sin base.
    return FormatoParseado(cantidad, unidad, None, None)


def normalizar_producto(
    producto: Product, config_clasificacion: ConfigClasificacion
) -> ProductoNormalizado:
    formato = parsear_formato(producto.formato)
    return ProductoNormalizado(
        retailer_product_id=producto.retailer_product_id,
        nombre=producto.nombre.strip(),
        marca=(producto.marca or "").strip() or None,
        categoria=producto.categoria,
        subcategoria=producto.subcategoria,
        precio_eur=precio_a_float(producto.precio_eur),
        precio_por_unidad=precio_a_float(producto.precio_por_unidad),
        unidad_medida=producto.unidad_medida,
        formato=producto.formato,
        cantidad_formato=formato.cantidad,
        unidad_formato=formato.unidad,
        cantidad_base_g_ml=formato.cantidad_base_g_ml,
        tipo_medida=formato.tipo_medida,
        disponible=producto.disponibilidad == "disponible",
        en_oferta=producto.oferta,
        precio_oferta=precio_a_float(producto.precio_oferta),
        url_producto=producto.url_producto,
        url_imagen=producto.url_imagen,
        apto_receta=es_apto_receta(producto.categoria, producto.subcategoria, config_clasificacion),
        fecha_extraccion=producto.fecha_extraccion,
    )
