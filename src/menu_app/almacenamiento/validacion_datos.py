"""Validación de datos del catálogo (#120): marca para REVISIÓN precios y
nutrientes fisicamente imposibles o inconsistentes. No corrige nada solo; el
usuario decide en /catalogo/{id} tras revisar.

Nota sobre alcance: se descartó un detector de precios "atípicos" por
subcategoría (ratio frente a la mediana) tras medirlo sobre el catálogo real:
incluso con un factor de 50x seguía marcando ~60 productos, porque dentro de
una misma subcategoría conviven productos legítimamente muy dispares en precio
(sal vs. azafrán en "Especias"). Los chequeos de abajo son deterministas sobre
límites FÍSICOS/lógicos, no estadísticos, así que no dan falsos positivos por
diversidad de producto.
"""

from __future__ import annotations

import sqlite3

# Densidad energetica maxima real (grasa pura ~884 kcal/100g); por encima es
# fisicamente imposible para un alimento.
KCAL_MAX_100G = 900.0
# Suma de macronutrientes (g/100g) no puede superar los 100g del propio alimento
# (con margen para redondeos de etiqueta).
MACROS_MAX_100G = 105.0


def validar_datos(conn: sqlite3.Connection) -> list[dict]:
    """Productos con precios/nutrientes que necesitan revisión manual."""
    problemas: list[dict] = []

    def _anadir(rid: str, nombre: str, problema: str) -> None:
        problemas.append({"retailer_product_id": rid, "nombre": nombre, "problema": problema})

    for r in conn.execute(
        "SELECT retailer_product_id, nombre FROM productos "
        "WHERE precio_eur < 0 OR precio_por_unidad < 0 OR precio_oferta < 0"
    ):
        _anadir(r["retailer_product_id"], r["nombre"], "precio negativo")

    for r in conn.execute(
        "SELECT retailer_product_id, nombre FROM productos "
        "WHERE en_oferta = 1 AND precio_oferta IS NOT NULL AND precio_eur IS NOT NULL "
        "AND precio_oferta > precio_eur"
    ):
        _anadir(r["retailer_product_id"], r["nombre"], "el precio de oferta es MAYOR que el normal")

    for r in conn.execute(
        "SELECT retailer_product_id, nombre, energia_kcal_100g FROM productos "
        "WHERE energia_kcal_100g > ? OR energia_kcal_100g < 0", (KCAL_MAX_100G,)
    ):
        _anadir(
            r["retailer_product_id"], r["nombre"],
            f"energía imposible: {r['energia_kcal_100g']:.0f} kcal/100g",
        )

    for r in conn.execute(
        "SELECT retailer_product_id, nombre, proteinas_100g, hidratos_100g, grasas_100g "
        "FROM productos WHERE "
        "(COALESCE(proteinas_100g,0) + COALESCE(hidratos_100g,0) + COALESCE(grasas_100g,0)) > ?",
        (MACROS_MAX_100G,),
    ):
        suma = (r["proteinas_100g"] or 0) + (r["hidratos_100g"] or 0) + (r["grasas_100g"] or 0)
        _anadir(r["retailer_product_id"], r["nombre"], f"macros suman {suma:.0f} g por 100 g")

    for r in conn.execute(
        "SELECT retailer_product_id, nombre, fibra_100g, hidratos_100g FROM productos "
        "WHERE fibra_100g IS NOT NULL AND hidratos_100g IS NOT NULL AND fibra_100g > hidratos_100g"
    ):
        _anadir(
            r["retailer_product_id"], r["nombre"],
            f"fibra ({r['fibra_100g']:.1f} g) mayor que los hidratos ({r['hidratos_100g']:.1f} g)",
        )

    for r in conn.execute(
        "SELECT retailer_product_id, nombre FROM productos WHERE "
        "grasas_100g < 0 OR grasas_sat_100g < 0 OR proteinas_100g < 0 OR "
        "azucares_100g < 0 OR sal_100g < 0 OR fibra_100g < 0"
    ):
        _anadir(r["retailer_product_id"], r["nombre"], "nutriente negativo")

    return problemas
