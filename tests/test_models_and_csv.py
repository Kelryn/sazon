from __future__ import annotations

from pathlib import Path

from menu_app.ingesta.csv_export import write_catalog_csv
from menu_app.ingesta.models import CSV_FIELDNAMES, product_from_decorated

# Forma real capturada en vivo contra la API (ver DISCOVERY.md), recortada a
# los campos que usamos.
RAW_PRODUCT_ON_OFFER = {
    "productId": "1773b242-70ab-426a-8e2d-2f4f959d5f99",
    "retailerProductId": "54186",
    "name": "AUCHAN Leche desnatada de vaca 6x 1 l Producto Alcampo.",
    "brand": "PRODUCTO ALCAMPO",
    "packSizeDescription": "6000ml",
    "price": {"amount": "4.92", "currency": "EUR"},
    "unitPrice": {"price": {"amount": "0.82", "currency": "EUR"}, "unitName": "PER_LITRE"},
    "available": True,
    "promotions": [{"description": "Producto en Folleto", "type": "OFFER"}],
    "image": {"src": "https://www.compraonline.alcampo.es/images-v3/x/y/300x300.jpg"},
}

RAW_PRODUCT_NO_OFFER = {
    "productId": "guid-2",
    "retailerProductId": "99999",
    "name": "Producto sin oferta",
    "brand": "MARCA",
    "price": {"amount": "1.00", "currency": "EUR"},
    "available": False,
    "promotions": [],
}


def test_product_from_decorated_maps_offer_fields():
    product = product_from_decorated(
        RAW_PRODUCT_ON_OFFER,
        category_path=["Leche, Huevos, Lácteos...", "Leche", "Leche desnatada"],
        fecha_extraccion="2026-07-09",
    )

    assert product.retailer_product_id == "54186"
    assert product.nombre == "AUCHAN Leche desnatada de vaca 6x 1 l Producto Alcampo."
    assert product.marca == "PRODUCTO ALCAMPO"
    assert product.categoria == "Leche, Huevos, Lácteos..."
    assert product.subcategoria == "Leche / Leche desnatada"
    assert product.precio_eur == "4.92"
    assert product.precio_por_unidad == "0.82"
    assert product.unidad_medida == "l"
    assert product.disponibilidad == "disponible"
    assert product.url_producto == "https://www.compraonline.alcampo.es/products/producto/54186"
    assert product.url_imagen == "https://www.compraonline.alcampo.es/images-v3/x/y/300x300.jpg"
    assert product.oferta is True
    assert product.precio_oferta == "4.92"


def test_product_from_decorated_without_offer():
    product = product_from_decorated(
        RAW_PRODUCT_NO_OFFER, category_path=["Alimentación"], fecha_extraccion="2026-07-09"
    )

    assert product.disponibilidad == "no_disponible"
    assert product.oferta is False
    assert product.precio_oferta is None
    assert product.subcategoria == ""


def test_write_catalog_csv_uses_bom_semicolon_and_full_header(tmp_path: Path):
    product = product_from_decorated(
        RAW_PRODUCT_ON_OFFER, category_path=["Leche"], fecha_extraccion="2026-07-09"
    )
    output_path = tmp_path / "catalogo.csv"

    total = write_catalog_csv([product], output_path)

    assert total == 1
    raw_bytes = output_path.read_bytes()
    assert raw_bytes.startswith(b"\xef\xbb\xbf")  # BOM de utf-8-sig

    text = output_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == ";".join(CSV_FIELDNAMES)
    assert "AUCHAN Leche desnatada de vaca 6x 1 l Producto Alcampo." in lines[1]
    assert lines[1].count(";") == len(CSV_FIELDNAMES) - 1


def test_csv_row_uses_comma_as_decimal_separator():
    product = product_from_decorated(
        RAW_PRODUCT_ON_OFFER, category_path=["Leche"], fecha_extraccion="2026-07-09"
    )

    row = product.to_csv_row()

    assert row["precio_eur"] == "4,92"
    assert row["precio_por_unidad"] == "0,82"
    assert row["precio_oferta"] == "4,92"
    assert "." not in row["precio_eur"]
    # El punto final de "Producto Alcampo." en el nombre no se toca -- la coma
    # decimal solo se aplica a las columnas numericas, no a cualquier texto.
    assert row["nombre"].endswith("Alcampo.")
