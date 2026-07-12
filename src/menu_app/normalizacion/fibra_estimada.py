"""Estimacion de FIBRA para productos que traen el resto de nutrientes pero no la
fibra.

Alcampo (endpoint `bop`) casi nunca declara fibra: es un dato OPCIONAL en el
etiquetado europeo, asi que ~80% de los productos con tabla nutricional la dejan
vacia. Eso hacia el suelo de fibra del menu inalcanzable por falta de DATO (no de
fibra real). Aqui se rellena SOLO la fibra (g/100 g) a partir de una tabla de
composicion (USDA FoodData Central / BEDCA), sin tocar el resto de valores reales.

El emparejamiento es por palabra clave sobre el nombre del producto, de mas
especifico a mas generico. Las LEGUMBRES distinguen forma seca vs cocida/conserva
(la cocida tiene menos fibra por 100 g por el agua absorbida).
"""

from __future__ import annotations

from ..matching.normalizar import quitar_acentos

# Marcas de que la legumbre/cereal viene ya cocido/en conserva (menos fibra/100 g).
_COCIDO = ("cocid", "conserva", "bote", "lata", "hervid", "guiso", "potaje", "en agua")

# Bebidas (leches vegetales, batidos, zumos...): son casi todo agua, asi que NO se
# les aplica la fibra del alimento solido ("bebida de avena" no tiene 10 g de fibra).
_BEBIDAS = (
    "bebida", "leche", "batido", "horchata", "zumo", "nectar", "refresco",
    "drink", "barista", "capuccino", "capuchino", "smoothie",
)


# (claves, fibra_seco_g_100g, fibra_cocido_o_None). Orden: especifico -> generico.
_REGLAS: list[tuple[tuple[str, ...], float, float | None]] = [
    # --- Semillas y salvado (muy alta) ---
    (("salvado",), 43.0, None),
    (("chia",), 34.0, None),
    (("lino", "linaza"), 27.0, None),
    (("sesamo", "ajonjoli"), 11.8, None),
    (("pipa", "pipas", "semilla", "semillas"), 8.6, None),
    # --- Frutos secos ---
    (("almendra", "almendras"), 12.5, None),
    (("pistacho", "pistachos"), 10.3, None),
    (("avellana", "avellanas"), 9.7, None),
    (("cacahuete", "cacahuetes", "mani"), 8.5, None),
    (("nuez", "nueces"), 6.7, None),
    (("anacardo", "anacardos"), 3.3, None),
    (("coco rallado", "coco deshidratado"), 16.0, None),
    # --- Harinas especificas antes que "harina" generica ---
    (("harina de garbanzo",), 10.8, None),
    (("harina integral", "harina de trigo integral"), 10.6, None),
    (("harina de avena",), 6.5, None),
    (("harina de almendra",), 12.5, None),
    (("harina", "harinas"), 2.7, None),
    # --- Cereales y derivados ---
    (("avena", "copos de avena"), 10.0, None),
    (("salvado de avena",), 15.0, None),
    (("centeno",), 15.0, None),
    (("bulgur",), 12.0, None),
    (("cuscus", "couscous"), 5.0, None),
    (("quinoa", "quinua"), 5.9, None),
    (("arroz integral",), 3.4, None),
    (("arroz",), 1.4, None),
    (("pasta integral", "espagueti integral", "macarron integral"), 8.0, None),
    (("pasta", "macarron", "macarrones", "espagueti", "espaguetis", "fideos", "tallarines"), 3.2, None),
    (("pan integral", "pan de centeno"), 7.0, None),
    (("pan rallado",), 4.0, None),
    (("pan de molde", "molde"), 3.5, None),
    (("pan", "barra", "hogaza", "chapata", "baguette"), 2.7, None),
    (("cereales integrales", "muesli", "granola"), 7.0, None),
    # --- Legumbres (seco / cocido) ---
    (("lenteja", "lentejas"), 11.0, 7.9),
    (("garbanzo", "garbanzos"), 12.2, 7.6),
    (
        ("alubia", "alubias", "judia blanca", "judias blancas", "faba", "fabes",
         "frijol", "frijoles", "judion", "judiones", "pochas", "poroto", "porotos"),
        15.5,
        6.4,
    ),
    (("soja",), 9.3, 6.0),
    (("guisante seco", "guisantes secos"), 8.3, None),
    # --- Frutas desecadas ---
    (("ciruela pasa", "ciruelas pasas"), 7.1, None),
    (("orejon", "orejones", "albaricoque seco"), 7.3, None),
    (("higo seco", "higos secos"), 9.8, None),
    (("datil", "datiles"), 8.0, None),
    (("pasa", "pasas", "uva pasa"), 4.0, None),
    (("arandano seco", "arandanos secos"), 5.7, None),
    # --- Otros ---
    (("tomate seco", "tomates secos"), 12.3, None),
    (("aceituna", "aceitunas", "oliva rellena"), 3.3, None),
    (("cacao puro", "cacao en polvo", "cacao desgrasado"), 33.0, None),
    (("chocolate negro", "chocolate 70", "chocolate 85"), 7.0, None),
]


def estimar_fibra(nombre: str) -> float | None:
    """Fibra estimada (g/100 g) para el producto, o None si no hay match fiable."""
    t = quitar_acentos(nombre or "")
    if not t:
        return None
    if any(b in t for b in _BEBIDAS):
        return None  # leches vegetales/batidos/zumos: no llevan la fibra del solido
    cocido = any(m in t for m in _COCIDO)
    for claves, seco, coc in _REGLAS:
        if any(k in t for k in claves):
            return coc if (cocido and coc is not None) else seco
    return None
