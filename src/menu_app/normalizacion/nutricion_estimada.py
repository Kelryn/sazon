"""Nutricion ESTIMADA para alimentos frescos que Alcampo no etiqueta.

Los productos frescos a granel (fruta, verdura, carne, pescado, huevos, pan de
horno...) no traen tabla nutricional en el endpoint de Alcampo. Para no dejarlos
sin datos (lo que sesgaria el menu hacia lo envasado), se les asigna una
estimacion por 100 g tomada de fuentes verificadas de composicion de alimentos:
USDA FoodData Central (dominio publico, CC0) y BEDCA (Base de Datos Española de
Composicion de Alimentos). Valores para el alimento CRUDO por 100 g.

Se marca en la BD como fuente_nutricion='estimada' para distinguirla del dato
real de fabricante (fuente 'bop'). El emparejamiento es por palabra clave sobre
el nombre del producto; solo se aplica a productos SIN nutricion real, asi que el
riesgo de confundir "tomate" (fresco) con "tomate frito" (que si trae etiqueta)
es minimo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Orden de los macros (coincide con columnas *_100g de productos).
# (energia_kcal, grasas, grasas_sat, hidratos, azucares, proteinas, sal, fibra) por 100 g.
_M = (
    "energia_kcal",
    "grasas",
    "grasas_sat",
    "hidratos",
    "azucares",
    "proteinas",
    "sal",
    "fibra",
)


@dataclass
class AlimentoRef:
    nombre: str
    claves: tuple[str, ...]  # palabras que deben aparecer en el nombre del producto
    valores: tuple[float, ...]  # en el orden de _M


# Tabla de referencia (USDA FDC / BEDCA), por 100 g de alimento crudo.
# Ordenada de mas especifico a mas generico dentro de cada bloque.
TABLA: list[AlimentoRef] = [
    # --- Verduras y hortalizas ---
    AlimentoRef("ajo", ("ajo", "ajos"), (149, 0.5, 0.09, 33.0, 1.0, 6.4, 0.04, 2.1)),
    AlimentoRef("cebolla", ("cebolla", "cebolleta"), (40, 0.1, 0.04, 9.3, 4.2, 1.1, 0.01, 1.7)),
    AlimentoRef("tomate", ("tomate",), (18, 0.2, 0.03, 3.9, 2.6, 0.9, 0.01, 1.2)),
    AlimentoRef("zanahoria", ("zanahoria",), (41, 0.2, 0.04, 9.6, 4.7, 0.9, 0.16, 2.8)),
    AlimentoRef("patata", ("patata", "patatas"), (77, 0.1, 0.03, 17.0, 0.8, 2.0, 0.02, 2.2)),
    AlimentoRef("pimiento", ("pimiento", "pimientos"), (31, 0.3, 0.03, 6.0, 4.2, 1.0, 0.01, 2.1)),
    AlimentoRef("lechuga", ("lechuga",), (15, 0.2, 0.03, 2.9, 0.8, 1.4, 0.03, 1.3)),
    AlimentoRef("escarola", ("escarola",), (17, 0.2, 0.05, 3.4, 0.3, 1.3, 0.05, 3.1)),
    AlimentoRef("espinaca", ("espinaca", "espinacas"), (23, 0.4, 0.06, 3.6, 0.4, 2.9, 0.19, 2.2)),
    AlimentoRef("acelga", ("acelga", "acelgas"), (19, 0.2, 0.03, 3.7, 1.1, 1.8, 0.21, 1.6)),
    AlimentoRef("calabacin", ("calabacin",), (17, 0.3, 0.08, 3.1, 2.5, 1.2, 0.02, 1.0)),
    AlimentoRef("berenjena", ("berenjena",), (25, 0.2, 0.03, 6.0, 3.5, 1.0, 0.01, 3.0)),
    AlimentoRef("pepino", ("pepino",), (15, 0.1, 0.04, 3.6, 1.7, 0.7, 0.01, 0.5)),
    AlimentoRef("brocoli", ("brocoli",), (34, 0.4, 0.04, 6.6, 1.7, 2.8, 0.08, 2.6)),
    AlimentoRef("coliflor", ("coliflor",), (25, 0.3, 0.13, 5.0, 1.9, 1.9, 0.08, 2.0)),
    AlimentoRef("champinon", ("champinon", "champinones", "seta", "setas"), (22, 0.3, 0.05, 3.3, 2.0, 3.1, 0.01, 1.0)),
    AlimentoRef("puerro", ("puerro", "puerros"), (61, 0.3, 0.04, 14.0, 3.9, 1.5, 0.05, 1.8)),
    AlimentoRef("judia verde", ("judia", "judias", "vainas"), (31, 0.2, 0.05, 7.0, 3.3, 1.8, 0.02, 2.7)),
    AlimentoRef("guisante", ("guisante", "guisantes"), (81, 0.4, 0.07, 14.0, 5.7, 5.4, 0.01, 5.7)),
    AlimentoRef("calabaza", ("calabaza",), (26, 0.1, 0.05, 6.5, 2.8, 1.0, 0.03, 0.5)),
    AlimentoRef("col", ("col", "repollo", "coles"), (25, 0.1, 0.03, 5.8, 3.2, 1.3, 0.04, 2.5)),
    AlimentoRef("apio", ("apio",), (16, 0.2, 0.04, 3.0, 1.8, 0.7, 0.08, 1.6)),
    AlimentoRef("maiz", ("maiz", "mazorca"), (86, 1.2, 0.2, 19.0, 3.2, 3.3, 0.04, 2.7)),
    AlimentoRef("esparrago", ("esparrago", "esparragos"), (20, 0.1, 0.05, 3.9, 1.9, 2.2, 0.005, 2.1)),
    AlimentoRef("alcachofa", ("alcachofa", "alcachofas"), (47, 0.2, 0.04, 10.5, 1.0, 3.3, 0.07, 5.4)),
    AlimentoRef("remolacha", ("remolacha",), (43, 0.2, 0.03, 10.0, 6.8, 1.6, 0.19, 2.8)),
    AlimentoRef("nabo", ("nabo",), (28, 0.1, 0.01, 6.4, 3.8, 0.9, 0.16, 1.8)),
    # --- Frutas ---
    AlimentoRef("manzana", ("manzana",), (52, 0.2, 0.03, 14.0, 10.4, 0.3, 0.002, 2.4)),
    AlimentoRef("platano", ("platano", "banana"), (89, 0.3, 0.11, 23.0, 12.2, 1.1, 0.002, 2.6)),
    AlimentoRef("naranja", ("naranja", "naranjas"), (47, 0.1, 0.02, 12.0, 9.4, 0.9, 0.0, 2.4)),
    AlimentoRef("mandarina", ("mandarina", "mandarinas", "clementina"), (53, 0.3, 0.04, 13.0, 11.0, 0.8, 0.005, 1.8)),
    AlimentoRef("fresa", ("fresa", "fresas", "freson"), (32, 0.3, 0.02, 7.7, 4.9, 0.7, 0.002, 2.0)),
    AlimentoRef("uva", ("uva", "uvas"), (69, 0.2, 0.05, 18.0, 15.5, 0.7, 0.005, 0.9)),
    AlimentoRef("pera", ("pera", "peras"), (57, 0.1, 0.02, 15.0, 9.8, 0.4, 0.002, 3.1)),
    AlimentoRef("melocoton", ("melocoton", "nectarina"), (39, 0.25, 0.02, 9.5, 8.4, 0.9, 0.0, 1.5)),
    AlimentoRef("sandia", ("sandia",), (30, 0.15, 0.02, 7.6, 6.2, 0.6, 0.002, 0.4)),
    AlimentoRef("melon", ("melon",), (34, 0.2, 0.05, 8.2, 7.9, 0.8, 0.04, 0.9)),
    AlimentoRef("aguacate", ("aguacate",), (160, 14.7, 2.1, 8.5, 0.7, 2.0, 0.017, 6.7)),
    AlimentoRef("limon", ("limon", "lima"), (29, 0.3, 0.04, 9.3, 2.5, 1.1, 0.005, 2.8)),
    AlimentoRef("kiwi", ("kiwi",), (61, 0.5, 0.03, 15.0, 9.0, 1.1, 0.007, 3.0)),
    AlimentoRef("pina", ("pina",), (50, 0.1, 0.01, 13.0, 9.9, 0.5, 0.002, 1.4)),
    AlimentoRef("cereza", ("cereza", "cerezas", "picota"), (63, 0.2, 0.04, 16.0, 12.8, 1.1, 0.0, 2.1)),
    AlimentoRef("ciruela", ("ciruela", "ciruelas"), (46, 0.3, 0.02, 11.0, 9.9, 0.7, 0.0, 1.4)),
    AlimentoRef("albaricoque", ("albaricoque", "albaricoques"), (48, 0.4, 0.03, 11.0, 9.2, 1.4, 0.001, 2.0)),
    AlimentoRef("mango", ("mango",), (60, 0.4, 0.09, 15.0, 13.7, 0.8, 0.002, 1.6)),
    AlimentoRef("granada", ("granada",), (83, 1.2, 0.12, 19.0, 13.7, 1.7, 0.003, 4.0)),
    # --- Carne (cruda) ---
    AlimentoRef("pechuga pollo", ("pechuga", "pechugas"), (120, 2.6, 0.7, 0.0, 0.0, 22.5, 0.15, 0.0)),
    AlimentoRef("pollo", ("pollo", "pollos"), (150, 8.0, 2.3, 0.0, 0.0, 19.0, 0.15, 0.0)),
    AlimentoRef("pavo", ("pavo",), (111, 1.6, 0.5, 0.0, 0.0, 24.0, 0.16, 0.0)),
    AlimentoRef("ternera", ("ternera", "vacuno", "buey"), (172, 10.0, 4.0, 0.0, 0.0, 20.0, 0.15, 0.0)),
    AlimentoRef("cerdo", ("cerdo", "lomo", "solomillo"), (180, 12.0, 4.3, 0.0, 0.0, 19.0, 0.15, 0.0)),
    AlimentoRef("cordero", ("cordero",), (200, 14.0, 6.0, 0.0, 0.0, 18.0, 0.15, 0.0)),
    AlimentoRef("conejo", ("conejo",), (136, 5.5, 1.6, 0.0, 0.0, 20.0, 0.04, 0.0)),
    AlimentoRef("jamon curado", ("serrano", "iberico", "bellota", "curado", "paleta"), (240, 12.0, 4.0, 0.5, 0.0, 31.0, 5.0, 0.0)),
    AlimentoRef("jamon cocido", ("jamon cocido", "york", "fiambre"), (110, 4.0, 1.4, 1.5, 1.0, 18.0, 2.2, 0.0)),
    AlimentoRef("chorizo", ("chorizo", "salchichon", "fuet", "embutido"), (350, 30.0, 11.0, 2.0, 1.0, 20.0, 3.5, 0.0)),
    AlimentoRef("bacon", ("bacon", "panceta", "tocino"), (400, 40.0, 14.0, 1.0, 0.0, 12.0, 2.0, 0.0)),
    # --- Pescado y marisco (crudo) ---
    AlimentoRef("salmon", ("salmon",), (208, 13.0, 3.0, 0.0, 0.0, 20.0, 0.1, 0.0)),
    AlimentoRef("merluza", ("merluza", "pescadilla"), (90, 1.9, 0.3, 0.0, 0.0, 17.0, 0.2, 0.0)),
    AlimentoRef("bacalao", ("bacalao",), (82, 0.7, 0.14, 0.0, 0.0, 18.0, 0.2, 0.0)),
    AlimentoRef("atun", ("atun", "bonito"), (130, 5.0, 1.3, 0.0, 0.0, 23.0, 0.1, 0.0)),
    AlimentoRef("sardina", ("sardina", "sardinas", "boqueron", "anchoa"), (208, 11.0, 1.5, 0.0, 0.0, 25.0, 0.3, 0.0)),
    AlimentoRef("dorada", ("dorada", "lubina",), (97, 2.5, 0.5, 0.0, 0.0, 18.0, 0.15, 0.0)),
    AlimentoRef("trucha", ("trucha",), (119, 3.5, 0.7, 0.0, 0.0, 20.0, 0.05, 0.0)),
    AlimentoRef("gamba", ("gamba", "gambas", "langostino", "langostinos"), (85, 1.0, 0.3, 0.9, 0.0, 20.0, 0.5, 0.0)),
    AlimentoRef("mejillon", ("mejillon", "mejillones", "almeja", "berberecho"), (86, 2.2, 0.4, 3.7, 0.0, 12.0, 0.3, 0.0)),
    AlimentoRef("pulpo", ("pulpo",), (82, 1.0, 0.2, 2.2, 0.0, 15.0, 0.4, 0.0)),
    AlimentoRef("calamar", ("calamar", "sepia", "chipiron"), (92, 1.4, 0.4, 3.1, 0.0, 15.0, 0.2, 0.0)),
    # --- Huevos y otros frescos ---
    AlimentoRef("huevo", ("huevo", "huevos"), (143, 9.5, 3.1, 0.7, 0.4, 12.6, 0.35, 0.0)),
    AlimentoRef("queso fresco", ("queso fresco", "requeson", "burgos"), (98, 5.0, 3.2, 3.5, 3.0, 11.0, 0.6, 0.0)),
    AlimentoRef("pan", ("pan", "barra", "hogaza", "chapata"), (265, 3.3, 0.7, 49.0, 5.0, 9.0, 1.2, 2.7)),
]

_TABLA_POR_CLAVE: list[tuple[str, AlimentoRef]] = [
    (clave, alimento) for alimento in TABLA for clave in alimento.claves
]


def _norm(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.lower()


def estimar(nombre_producto: str) -> tuple[dict[str, float], str] | None:
    """Devuelve (macros_por_100g, nombre_alimento) si el producto casa con la
    tabla de frescos, o None. Prioriza claves de dos palabras y las primeras de
    la tabla (mas especificas)."""
    nombre = _norm(nombre_producto)
    # Primero claves compuestas (mas especificas), luego simples.
    for clave, alimento in sorted(_TABLA_POR_CLAVE, key=lambda p: -len(p[0])):
        patron = r"\b" + re.escape(clave) + r"\b"
        if re.search(patron, nombre):
            return dict(zip(_M, alimento.valores, strict=True)), alimento.nombre
    return None
