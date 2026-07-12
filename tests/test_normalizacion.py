from __future__ import annotations

import pytest

from menu_app.ingesta.models import Product
from menu_app.normalizacion.clasificacion import ConfigClasificacion, es_apto_receta
from menu_app.normalizacion.limpieza import (
    normalizar_producto,
    parsear_formato,
    precio_a_float,
)


@pytest.mark.parametrize(
    "entrada,esperado",
    [("4,92", 4.92), ("4.92", 4.92), ("0,82", 0.82), ("", None), (None, None), ("abc", None)],
)
def test_precio_a_float(entrada, esperado):
    assert precio_a_float(entrada) == esperado


@pytest.mark.parametrize(
    "formato,cantidad,unidad,base,tipo",
    [
        ("500g", 500.0, "g", 500.0, "peso"),
        ("1 l", 1.0, "l", 1000.0, "volumen"),
        ("110 g.", 110.0, "g", 110.0, "peso"),
        ("6 x 1 l", 6.0, "l", 6000.0, "volumen"),
        ("6x1l", 6.0, "l", 6000.0, "volumen"),
        ("750g - 1250g", 1000.0, "g", 1000.0, "peso"),  # punto medio
        ("2 kg", 2.0, "kg", 2000.0, "peso"),
        ("33 cl", 33.0, "cl", 330.0, "volumen"),
    ],
)
def test_parsear_formato(formato, cantidad, unidad, base, tipo):
    resultado = parsear_formato(formato)
    assert resultado.cantidad == cantidad
    assert resultado.unidad == unidad
    assert resultado.cantidad_base_g_ml == base
    assert resultado.tipo_medida == tipo


def test_parsear_formato_desconocido():
    resultado = parsear_formato(None)
    assert resultado.cantidad is None
    assert resultado.tipo_medida is None


CONFIG = ConfigClasificacion()


@pytest.mark.parametrize(
    "categoria,subcategoria,esperado",
    [
        ("Frescos", "Verduras y hortalizas", True),
        ("Alimentación", "Arroz y Legumbres", True),
        ("Leche, Huevos, Lácteos, Yogures y Bebidas vegetales", "Huevos", True),
        ("Leche, Huevos, Lácteos, Yogures y Bebidas vegetales", "Bebidas vegetales", True),
        # Alcohol de COCINA (excepcion): apto porque se usa en recetas.
        ("Bebidas", "Vino Tinto", True),
        ("Bebidas", "Vino Blanco", True),
        ("Bebidas", "Cervezas", True),
        ("Bebidas", "Licores", True),
        ("Bebidas", "Champagne Cavas y Sidras", True),
        # No aptos:
        ("Bebidas", "Refrescos", False),
        ("Bebidas", "Zumos de Frutas", False),  # toda la raiz Bebidas fuera
        ("Bebidas", "Aguas", False),
        ("Veganos", "Vino Vegano", False),  # 'vino vegano' no es alcohol de cocina reconocido
        ("Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional", "Nutrición deportiva", False),
        ("Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional", "Complementos Naturales y Herbolario", False),
        ("Supermercado Ecológico", "Droguería Ecológica y sostenible", False),
        # Pero dentro de "Sin Gluten..." lo que SI es comida sigue apto:
        ("Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional", "Sin Gluten apto Celíacos", True),
    ],
)
def test_es_apto_receta(categoria, subcategoria, esperado):
    assert es_apto_receta(categoria, subcategoria, CONFIG) is esperado


def _producto(**kwargs) -> Product:
    base = dict(
        retailer_product_id="54186",
        nombre="  AUCHAN Leche desnatada 6x 1 l  ",
        marca="PRODUCTO ALCAMPO",
        categoria="Leche, Huevos, Lácteos, Yogures y Bebidas vegetales",
        subcategoria="Leche",
        precio_eur="4,92",
        precio_por_unidad="0,82",
        unidad_medida="l",
        formato="6 x 1 l",
        disponibilidad="disponible",
        url_producto="https://www.compraonline.alcampo.es/products/producto/54186",
        url_imagen="https://img/x.jpg",
        oferta=True,
        precio_oferta="4,92",
        fecha_extraccion="2026-07-09",
    )
    base.update(kwargs)
    return Product(**base)


def test_normalizar_producto():
    norm = normalizar_producto(_producto(), CONFIG)

    assert norm.nombre == "AUCHAN Leche desnatada 6x 1 l"  # sin espacios sobrantes
    assert norm.precio_eur == 4.92
    assert norm.precio_por_unidad == 0.82
    assert norm.cantidad_formato == 6.0
    assert norm.unidad_formato == "l"
    assert norm.cantidad_base_g_ml == 6000.0
    assert norm.tipo_medida == "volumen"
    assert norm.disponible is True
    assert norm.en_oferta is True
    assert norm.apto_receta is True


def test_normalizar_producto_marca_vacia_es_none():
    norm = normalizar_producto(_producto(marca=""), CONFIG)
    assert norm.marca is None
