"""Calcula coste y nutricion reales de cada receta a partir de datos de Alcampo.

Une, para cada ingrediente de una receta:
    receta_ingredientes  --nombre_normalizado-->  mapeo_ingr_producto  --rid-->  productos

y con la cantidad del ingrediente (en g/ml, ya normalizada en Fase 3), el precio
por unidad del producto y su nutricion por 100 g, obtiene el coste y los
macronutrientes que aporta ese ingrediente. Sumando, sale el coste y la nutricion
de la receta completa (y por racion).

Aproximaciones honestas:
- Para liquidos se asume 1 ml ~ 1 g (suficiente para nutricion y coste €/l).
- Ingredientes sin producto mapeado o sin cantidad en g/ml no se pueden costear;
  se cuentan aparte y se reporta la COBERTURA (fraccion de ingredientes costeados)
  para saber cuanto de fiable es el numero.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# Nutrientes que manejamos (coinciden con las columnas *_100g de productos).
NUTRIENTES = [
    "energia_kcal",
    "grasas",
    "grasas_sat",
    "hidratos",
    "azucares",
    "proteinas",
    "sal",
    "fibra",
]
_COL_100G = {n: f"{n}_100g" for n in NUTRIENTES}

# Precio por unidad -> factor para pasar de gramos/ml del ingrediente a la unidad
# del precio. precio_por_unidad viene en €/kg, €/l, €/100g, €/100ml o €/ud.
_FACTOR_PRECIO = {  # g o ml del ingrediente -> multiplicador del precio_por_unidad
    "kg": 1 / 1000,
    "l": 1 / 1000,
    "100g": 1 / 100,
    "100ml": 1 / 100,
}

# Peso comestible aproximado (g) de UNA pieza de alimentos que las recetas cuentan
# por unidades ("1 cebolla", "2 zanahorias") en vez de en gramos. Permite costear
# y nutrir esos ingredientes (si no, se descartaban y bajaba la cobertura). Fuentes:
# pesos medios USDA/BEDCA. Claves sin acentos (sobre nombre_normalizado).
_PESO_PIEZA_G = {
    "cebolleta": 30, "cebolla": 150, "ajo": 5, "zanahoria": 80, "pimiento": 150,
    "tomate": 120, "patata": 150, "huevo": 60, "calabacin": 200, "berenjena": 250,
    "pepino": 300, "puerro": 100, "lechuga": 300, "apio": 40, "champinon": 20,
    "seta": 25, "guindilla": 10, "chile": 15, "manzana": 180, "platano": 120,
    "banana": 120, "naranja": 200, "limon": 100, "lima": 70, "pera": 180,
    "aguacate": 200, "kiwi": 75, "mandarina": 80, "melocoton": 150, "nectarina": 140,
    "ciruela": 60, "higo": 50, "mango": 200, "pina": 900, "granada": 250,
}


def _gramos_por_piezas(nombre_norm: str, unidad: str | None, cantidad: float | None) -> float | None:
    """Estima los gramos de un ingrediente contado por piezas ('1 cebolla')."""
    if cantidad is None:
        return None
    u = (unidad or "").lower()
    if "diente" in u:  # diente de ajo
        return cantidad * 5.0
    nombre = nombre_norm or ""
    for kw, gramos in _PESO_PIEZA_G.items():
        if kw in nombre:
            return cantidad * gramos
    return None


@dataclass
class RecetaCalculada:
    receta_id: str
    titulo: str
    fuente: str | None
    es_batchcooking: bool
    rol: str
    es_favorita: bool
    es_plato_unico: bool
    es_cena: bool
    raciones: int | None
    coste_total: float
    nutricion: dict[str, float]  # totales de la receta entera
    n_ingredientes: int
    n_costeados: int
    ingredientes_sin_producto: list[str] = field(default_factory=list)
    # True si el ingrediente PRINCIPAL (el de mayor peso en la receta) no tiene
    # producto en Alcampo: la receta no debe entrar en el menu (no se puede comprar).
    principal_sin_producto: bool = False
    # True si algun ingrediente NO OPCIONAL no tiene producto: la receta no se puede
    # cocinar completa comprando en Alcampo -> se excluye del menu.
    falta_no_opcional: bool = False
    # Nombre normalizado del ingrediente de mayor peso (para el grupo de alimento).
    ingrediente_principal: str | None = None
    # Productos de Alcampo (retailer_product_id) que usa la receta: sirven para
    # racionalizar la compra (que las recetas del menu compartan productos).
    productos: set[str] = field(default_factory=set)
    # Gramos TOTALES (receta entera) de cada producto de Alcampo: para penalizar la
    # sobra real (Enfoque B, #23/24). Se divide por raciones para el valor por racion.
    productos_gramos: dict[str, float] = field(default_factory=dict)
    # Nombres normalizados de TODOS los ingredientes (para excluir por lista negra).
    ingredientes_norm: set[str] = field(default_factory=set)
    # Tiempo total de preparacion en minutos (si la fuente lo da; None si no).
    tiempo_total_min: int | None = None

    @property
    def cobertura(self) -> float:
        return self.n_costeados / self.n_ingredientes if self.n_ingredientes else 0.0

    @property
    def coste_racion(self) -> float | None:
        return self.coste_total / self.raciones if self.raciones else None

    def nutricion_racion(self) -> dict[str, float]:
        if not self.raciones:
            return {}
        return {k: v / self.raciones for k, v in self.nutricion.items()}

    def nutricion_por_100g(self) -> dict[str, float]:
        """Composicion por 100 g de la receta (para el Nutri-Score). Usa el peso total
        de los productos casados; {} si no se conoce el peso."""
        total_g = sum(self.productos_gramos.values())
        if total_g <= 0:
            return {}
        return {k: v / total_g * 100.0 for k, v in self.nutricion.items()}


# Marcas de que un ingrediente es OPCIONAL / de adorno: si no casa, no descarta
# la receta (se puede cocinar sin el).
_OPCIONAL = (
    "opcional", "al gusto", "para decorar", "para adornar", "para servir",
    "para acompanar", "para acompañar", "para espolvorear", "para untar",
    "para pincelar", "para engrasar", "para freir", "para freír", "si se desea",
    "si lo desea", "optional", "to taste", "to serve", "to garnish", "for garnish",
    "for serving", "garnish", "topping", "toppings", "opzionale",
)


def _es_opcional(texto: str) -> bool:
    t = (texto or "").lower()
    return any(m in t for m in _OPCIONAL)


def _cargar_productos(conn: sqlite3.Connection) -> dict[str, dict]:
    cols = ", ".join(["retailer_product_id", "precio_por_unidad", "unidad_medida"] + list(_COL_100G.values()))
    cur = conn.execute(f"SELECT {cols} FROM productos WHERE apto_receta = 1")
    return {r["retailer_product_id"]: dict(r) for r in cur.fetchall()}


def _cargar_mapeo(conn: sqlite3.Connection) -> dict[str, str]:
    cur = conn.execute(
        "SELECT ingrediente_norm, retailer_product_id FROM mapeo_ingr_producto "
        "WHERE retailer_product_id IS NOT NULL"
    )
    return {r["ingrediente_norm"]: r["retailer_product_id"] for r in cur.fetchall()}


def calcular_receta(
    conn: sqlite3.Connection, receta_id: str, productos: dict[str, dict], mapeo: dict[str, str]
) -> RecetaCalculada:
    cab = conn.execute(
        "SELECT titulo, raciones, fuente, es_batchcooking, rol, es_favorita, "
        "es_plato_unico, es_cena, tiempo_total_min FROM recetas WHERE id = ?",
        (receta_id,),
    ).fetchone()
    ingredientes = conn.execute(
        "SELECT nombre_normalizado, cantidad, unidad, cantidad_metrica, unidad_metrica, "
        "texto_original FROM receta_ingredientes WHERE receta_id = ?",
        (receta_id,),
    ).fetchall()

    coste = 0.0
    nutricion = {n: 0.0 for n in NUTRIENTES}
    costeados = 0
    sin_producto: list[str] = []
    max_gramos = 0.0
    principal_sin_producto = False
    falta_no_opcional = False
    ingrediente_principal = None
    productos_usados: set[str] = set()
    productos_gramos: dict[str, float] = {}
    ingredientes_norm: set[str] = set()

    for ing in ingredientes:
        if ing["nombre_normalizado"]:
            ingredientes_norm.add(ing["nombre_normalizado"])
        rid = mapeo.get(ing["nombre_normalizado"])
        prod = productos.get(rid) if rid else None
        if prod is not None:
            productos_usados.add(rid)
        cantidad = ing["cantidad_metrica"]  # en g o ml
        if cantidad is None:
            # Ingrediente contado por piezas ("1 cebolla"): estima gramos por pieza.
            cantidad = _gramos_por_piezas(
                ing["nombre_normalizado"], ing["unidad"], ing["cantidad"]
            )
        # El ingrediente de mayor peso es el PRINCIPAL: si no se puede comprar en
        # Alcampo, la receta entera queda descartada para el menu.
        if cantidad is not None and cantidad > max_gramos:
            max_gramos = cantidad
            principal_sin_producto = prod is None
            ingrediente_principal = ing["nombre_normalizado"]
        if prod is None:
            sin_producto.append(ing["nombre_normalizado"])
            # Si el ingrediente que falta NO es opcional, la receta no se puede
            # cocinar comprando en Alcampo.
            if not _es_opcional(ing["texto_original"]):
                falta_no_opcional = True
            continue
        if cantidad is None:
            continue  # producto conocido pero sin cantidad ni peso por pieza -> no se prorratea

        productos_gramos[rid] = productos_gramos.get(rid, 0.0) + cantidad  # para la sobra (#23)

        # Coste del ingrediente.
        precio_u = prod["precio_por_unidad"]
        factor = _FACTOR_PRECIO.get(prod["unidad_medida"])
        if precio_u is not None and factor is not None:
            coste += cantidad * factor * precio_u

        # Nutricion del ingrediente (por 100 g/ml -> por la cantidad usada).
        for n in NUTRIENTES:
            v100 = prod[_COL_100G[n]]
            if v100 is not None:
                nutricion[n] += cantidad / 100.0 * v100
        costeados += 1

    return RecetaCalculada(
        receta_id=receta_id,
        titulo=cab["titulo"] if cab else receta_id,
        fuente=cab["fuente"] if cab else None,
        es_batchcooking=bool(cab["es_batchcooking"]) if cab else False,
        rol=(cab["rol"] if cab and cab["rol"] else "principal"),
        es_favorita=bool(cab["es_favorita"]) if cab else False,
        es_plato_unico=bool(cab["es_plato_unico"]) if cab else False,
        es_cena=bool(cab["es_cena"]) if cab else False,
        raciones=cab["raciones"] if cab else None,
        coste_total=round(coste, 2),
        nutricion={k: round(v, 1) for k, v in nutricion.items()},
        falta_no_opcional=falta_no_opcional,
        ingrediente_principal=ingrediente_principal,
        productos=productos_usados,
        productos_gramos=productos_gramos,
        ingredientes_norm=ingredientes_norm,
        tiempo_total_min=(cab["tiempo_total_min"] if cab else None),
        n_ingredientes=len(ingredientes),
        n_costeados=costeados,
        ingredientes_sin_producto=sin_producto,
        principal_sin_producto=principal_sin_producto,
    )


# Cache de calcular_todas (#34): recalcular coste/nutricion de ~4000 recetas en cada
# generacion es caro. Se cachea keyed por una FIRMA barata que cambia cuando cambian
# recetas, ingredientes, productos o el mapeo. Las ediciones de precio/nutricion de un
# producto no cambian los contadores -> el visor/catalogo llama a invalidar_cache().
_CACHE: dict = {"firma": None, "datos": None}


def _firma_cache(conn: sqlite3.Connection):
    try:
        archivo = conn.execute("PRAGMA database_list").fetchone()["file"]
    except Exception:  # noqa: BLE001
        archivo = "?"

    def _c(sql: str):
        return conn.execute(sql).fetchone()[0]

    return (
        archivo,
        _c("SELECT COUNT(*) FROM recetas"),
        _c("SELECT COUNT(*) FROM receta_ingredientes"),
        _c("SELECT COUNT(*) FROM productos"),
        _c("SELECT COUNT(*) FROM mapeo_ingr_producto"),
        _c("SELECT MAX(fecha) FROM mapeo_ingr_producto"),
    )


def invalidar_cache() -> None:
    """Fuerza el recalculo en la proxima llamada a calcular_todas (tras editar precios
    o nutricion de un producto, que no cambian los contadores de la firma)."""
    _CACHE["firma"] = None
    _CACHE["datos"] = None


def calcular_todas(conn: sqlite3.Connection, usar_cache: bool = True) -> list[RecetaCalculada]:
    if usar_cache:
        firma = _firma_cache(conn)
        if _CACHE["firma"] == firma and _CACHE["datos"] is not None:
            return _CACHE["datos"]
    productos = _cargar_productos(conn)
    mapeo = _cargar_mapeo(conn)
    ids = [r["id"] for r in conn.execute("SELECT id FROM recetas").fetchall()]
    datos = [calcular_receta(conn, rid, productos, mapeo) for rid in ids]
    if usar_cache:
        _CACHE["firma"] = firma
        _CACHE["datos"] = datos
    return datos
