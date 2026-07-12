"""Tests del parser de detalle nutricional, con HTML real del endpoint bop."""

from __future__ import annotations

from menu_app.normalizacion.detalle import parsear_detalle

# JSON real (recortado) del producto 54186 (AUCHAN Leche desnatada), capturado
# en vivo del endpoint /api/webproductpagews/v5/products/bop.
BOP_LECHE = {
    "bopData": {
        "fields": [
            {"title": "brand", "content": "PRODUCTO ALCAMPO"},
            {
                "title": "ingredients",
                "content": "<h4>Ingredientes:</h4>\n<p>LECHE DESNATADA DE VACA. ORIGEN DE LA LECHE: ESPAÑA.</p>\n",
            },
            {
                "title": "features",
                "content": (
                    "<table><tbody>"
                    "<tr><td>Nombre operador / Importador</td><td>Alcampo, S.A.</td></tr>"
                    "<tr><td>País de origen</td><td>España</td></tr>"
                    "<tr><td>Denominación legal del alimento</td><td>LECHE UHT DESNATADA</td></tr>"
                    "</tbody></table>"
                ),
            },
            {
                "title": "nutritionalData",
                "content": (
                    "<table><tbody>"
                    "<tr><th>Valores medios por:</th><th>100g</th></tr>"
                    "<tr><td><span>Valor energético (Kj)</span></td><td><span>146.0 Kj</span></td></tr>"
                    "<tr><td><span>Valor energético (Kcal)</span></td><td><span>35.0 Kcal</span></td></tr>"
                    "<tr><td><span>Grasas</span></td><td><span>0.3 g</span></td></tr>"
                    "<tr><td><span>Grasas saturadas</span></td><td><span>0.2 g</span></td></tr>"
                    "<tr><td><span>Hidratos de carbono</span></td><td><span>4.8 g</span></td></tr>"
                    "<tr><td><span>Azúcares</span></td><td><span>4.8 g</span></td></tr>"
                    "<tr><td><span>Proteinas</span></td><td><span>3.2 g</span></td></tr>"
                    "<tr><td><span>Sal</span></td><td><span>0.13 g</span></td></tr>"
                    "</tbody></table>"
                ),
            },
        ]
    }
}

# Producto fresco a granel: sin tablas de nutricion/ingredientes.
BOP_FRESCO = {"bopData": {"fields": [{"title": "brand", "content": "FRUTA"}]}}


def test_parsear_detalle_completo():
    d = parsear_detalle(BOP_LECHE)

    assert d.base_nutricional == "100g"
    assert d.energia_kcal_100g == 35.0
    assert d.grasas_100g == 0.3
    assert d.grasas_sat_100g == 0.2  # no confundido con "Grasas" a secas
    assert d.hidratos_100g == 4.8
    assert d.azucares_100g == 4.8
    assert d.proteinas_100g == 3.2
    assert d.sal_100g == 0.13
    assert d.origen == "España"
    assert "LECHE DESNATADA DE VACA" in d.ingredientes
    assert not d.ingredientes.lower().startswith("ingredientes")
    assert d.tiene_nutricion() is True


def test_grasas_vs_grasas_saturadas_no_se_confunden():
    d = parsear_detalle(BOP_LECHE)
    # "Grasas" -> grasas_100g, "Grasas saturadas" -> grasas_sat_100g
    assert d.grasas_100g == 0.3
    assert d.grasas_sat_100g == 0.2


def test_producto_fresco_sin_nutricion():
    d = parsear_detalle(BOP_FRESCO)
    assert d.tiene_nutricion() is False
    assert d.energia_kcal_100g is None
    assert d.ingredientes is None
    assert d.origen is None


def test_json_vacio_no_rompe():
    d = parsear_detalle({})
    assert d.tiene_nutricion() is False
