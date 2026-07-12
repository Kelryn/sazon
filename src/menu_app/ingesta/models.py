from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Orden y nombres de columna del CSV de catalogo.
#
# Solo contiene lo que la API de listado de Alcampo ofrece de forma fiable. Las
# columnas nutricionales, EAN, ingredientes, alergenos y origen se quitaron a
# proposito: ese endpoint esta bloqueado por el anti-bot fuera de la SPA (ver
# DISCOVERY.md 3.2), asi que en la practica siempre venian vacias. La nutricion
# para el scoring de salud se resolvera aparte (ver nota en Fase 2), no en este
# CSV de catalogo.
CSV_FIELDNAMES = [
    "nombre",
    "marca",
    "categoria",
    "subcategoria",
    "precio_eur",
    "precio_por_unidad",
    "unidad_medida",
    "formato",
    "disponibilidad",
    "url_producto",
    "url_imagen",
    "oferta",
    "precio_oferta",
    "fecha_extraccion",
]

# Traduce el unitName de la API a la unidad que se muestra en el CSV.
UNIT_LABELS = {
    "PER_1KG": "kg",
    "PER_LITRE": "l",
    "PER_100G": "100g",
    "PER_100ML": "100ml",
    "PER_UNIT": "ud",
}


def _decimal_coma(value: str | None) -> str:
    """Coma como separador decimal (convencion española), no punto.

    Los precios llegan de la API con punto decimal (p.ej. "4.44"); aqui solo se
    cambia el separador para el CSV, el resto del codigo sigue trabajando con
    punto.
    """
    return value.replace(".", ",") if value else ""


@dataclass
class Product:
    """Una fila del catalogo de Alcampo.

    `retailer_product_id` no se vuelca al CSV (es ruido para revisarlo a mano),
    pero se conserva en el modelo porque es la clave primaria estable que usa
    el almacenamiento en SQLite (Fase 2).
    """

    retailer_product_id: str
    nombre: str
    marca: str | None
    categoria: str
    subcategoria: str
    precio_eur: str | None
    precio_por_unidad: str | None
    unidad_medida: str | None
    formato: str | None
    disponibilidad: str
    url_producto: str
    url_imagen: str | None
    oferta: bool
    precio_oferta: str | None
    fecha_extraccion: str

    def to_csv_row(self) -> dict[str, str]:
        return {
            "nombre": self.nombre,
            "marca": self.marca or "",
            "categoria": self.categoria,
            "subcategoria": self.subcategoria,
            "precio_eur": _decimal_coma(self.precio_eur),
            "precio_por_unidad": _decimal_coma(self.precio_por_unidad),
            "unidad_medida": self.unidad_medida or "",
            "formato": self.formato or "",
            "disponibilidad": self.disponibilidad,
            "url_producto": self.url_producto,
            "url_imagen": self.url_imagen or "",
            "oferta": "si" if self.oferta else "no",
            "precio_oferta": _decimal_coma(self.precio_oferta),
            "fecha_extraccion": self.fecha_extraccion,
        }


def product_from_decorated(
    raw: dict[str, Any], category_path: list[str], fecha_extraccion: str
) -> Product:
    """Mapea un `decoratedProduct` crudo de la API a nuestro modelo de producto.

    `category_path` es la ruta de nombres desde la raiz hasta la categoria hoja
    de la que vino este producto (ver AlcampoClient.iter_leaf_categories).
    """
    retailer_product_id = str(raw.get("retailerProductId") or raw.get("productId") or "")

    price = (raw.get("price") or {}).get("amount")
    unit_price_block = raw.get("unitPrice") or {}
    unit_price = (unit_price_block.get("price") or {}).get("amount")
    unit_name = unit_price_block.get("unitName")
    promotions = raw.get("promotions") or []
    image = raw.get("image") or {}

    categoria = category_path[0] if category_path else ""
    subcategoria = " / ".join(category_path[1:]) if len(category_path) > 1 else ""

    return Product(
        retailer_product_id=retailer_product_id,
        nombre=raw.get("name", ""),
        marca=raw.get("brand"),
        categoria=categoria,
        subcategoria=subcategoria,
        precio_eur=price,
        precio_por_unidad=unit_price,
        unidad_medida=UNIT_LABELS.get(unit_name, unit_name),
        formato=raw.get("packSizeDescription"),
        disponibilidad="disponible" if raw.get("available") else "no_disponible",
        # El slug es cosmetico: la propia web redirige a la URL canonica solo
        # con el retailerProductId (confirmado en vivo, DISCOVERY.md seccion 3.1).
        url_producto=f"https://www.compraonline.alcampo.es/products/producto/{retailer_product_id}",
        url_imagen=image.get("src"),
        oferta=bool(promotions),
        # La API de listado no expone el precio "antes de oferta", solo el
        # precio final ya aplicado -- ver limitacion anotada en DISCOVERY.md.
        precio_oferta=price if promotions else None,
        fecha_extraccion=fecha_extraccion,
    )
