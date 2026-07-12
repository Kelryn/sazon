"""Categorias raiz de alimentacion, confirmadas en vivo contra la API real.

Salen de recorrer GET /api/webproductpagews/v1/categories (ver DISCOVERY.md
seccion 3.1.1) y quedarnos con las 10 ramas de nivel superior que son comida o
bebida, descartando droguería, perfumería, bebe, electrodomesticos,
juguetería, etc. "Folletos y Promociones" tambien se descarta a proposito:
son productos duplicados de otras categorias, no una seccion propia.
"""

FOOD_CATEGORY_ROOTS: dict[str, str] = {
    "OC2112": "Frescos",
    "OC16": "Leche, Huevos, Lácteos, Yogures y Bebidas vegetales",
    "OCC10": "Alimentación",
    "OC10": "Desayuno y Merienda",
    "OC200220183": "Congelados",
    "OC20022018": "Comida Preparada",
    "OC26112021": "Supermercado Ecológico",
    "OCC11": "Bebidas",
    "OCSINGSINL": "Sin Gluten / Sin Lactosa, Nutrición deportiva y Funcional",
    "OC09112021": "Veganos",
}
