"""Clasificacion de recetas por GRUPO DE ALIMENTO del ingrediente principal.

Para equilibrar el menu al estilo de las guias AESAN/dieta mediterranea no basta
con los macronutrientes: interesa que la semana tenga suficiente verdura,
legumbre y pescado, y poca carne roja. Cada receta se asigna al grupo de su
ingrediente PRINCIPAL (el de mayor peso), por palabras clave sobre su nombre.

Grupos: verdura, fruta, legumbre, pescado, carne_roja, carne_blanca, cereal,
huevo, lacteo, otro.
"""

from __future__ import annotations

from ..matching.normalizar import quitar_acentos

VERDURA = "verdura"
FRUTA = "fruta"
LEGUMBRE = "legumbre"
PESCADO = "pescado"
CARNE_ROJA = "carne_roja"
CARNE_BLANCA = "carne_blanca"
CEREAL = "cereal"
HUEVO = "huevo"
LACTEO = "lacteo"
OTRO = "otro"

# Palabras clave por grupo (sin acentos). Orden de comprobacion: mas especifico
# primero (legumbre/pescado/carne antes que cereal/verdura genericos).
_REGLAS: list[tuple[str, tuple[str, ...]]] = [
    (LEGUMBRE, ("lenteja", "garbanzo", "alubia", "judia blanca", "judion", "faba",
                "fabada", "frijol", "poroto", "haba", "guisante", "soja", "pochas",
                "hummus")),
    (PESCADO, ("merluza", "bacalao", "atun", "bonito", "salmon", "sardina", "boqueron",
               "anchoa", "dorada", "lubina", "trucha", "pescado", "gamba", "langostino",
               "marisco", "mejillon", "almeja", "calamar", "pulpo", "sepia", "chipiron",
               "pota", "rape", "lenguado", "caballa", "pez", "surimi", "gambas")),
    (CARNE_ROJA, ("ternera", "vacuno", "buey", "res", "cerdo", "cordero", "lomo",
                  "solomillo", "chuleta", "costilla", "morcilla", "chorizo", "panceta",
                  "bacon", "jamon", "salchicha", "carne picada", "carne de", "cabrito",
                  "rabo", "carrillera", "secreto", "presa")),
    (CARNE_BLANCA, ("pollo", "pavo", "conejo", "pechuga", "muslo", "contramuslo",
                    "gallina", "codorniz", "pato")),
    (HUEVO, ("huevo", "tortilla", "revuelto")),
    (VERDURA, ("verdura", "espinaca", "acelga", "brocoli", "coliflor", "calabacin",
               "berenjena", "pimiento", "cebolla", "puerro", "zanahoria", "tomate",
               "calabaza", "alcachofa", "esparrago", "champinon", "seta", "col",
               "lechuga", "ensalada", "menestra", "pisto", "gazpacho", "salmorejo",
               "crema de", "guacamole", "escalibada", "ratatouille", "parrillada")),
    (CEREAL, ("arroz", "pasta", "espagueti", "macarron", "fideo", "tallarin", "pan",
              "pizza", "lasana", "canelon", "risotto", "cuscus", "quinoa", "polenta",
              "noqui", "raviol", "pilaf", "paella", "fideua")),
    (FRUTA, ("manzana", "platano", "naranja", "pera", "fresa", "melon", "sandia",
             "uva", "kiwi", "mango", "melocoton", "pina", "aguacate")),
    (LACTEO, ("queso", "yogur", "requeson", "mozzarella", "bechamel", "nata")),
]


def grupo_por_nombre(nombre: str) -> str:
    """Grupo de alimento a partir de un nombre (de receta o de ingrediente)."""
    t = quitar_acentos(nombre or "")
    for grupo, claves in _REGLAS:
        if any(c in t for c in claves):
            return grupo
    return OTRO


def grupo_receta(titulo: str, ingrediente_principal: str | None) -> str:
    """Grupo de la receta: manda el ingrediente PRINCIPAL; si no da pista, el titulo."""
    if ingrediente_principal:
        g = grupo_por_nombre(ingrediente_principal)
        if g != OTRO:
            return g
    return grupo_por_nombre(titulo)
