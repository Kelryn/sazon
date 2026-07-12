"""Clasifica cada producto segun si es un alimento util para cocinar recetas.

El usuario solo quiere, de cara al menu, los productos que sean "alimentos
susceptibles de utilizarse en una receta". Aqui NO se descarta nada: se marca
cada producto con un booleano `apto_receta`, y ya sera el pre-filtro de la
Fase 5 (o cualquier consulta SQL) quien filtre con `WHERE apto_receta = 1`.
Asi no se pierde informacion y el criterio se puede afinar sin re-extraer.

El criterio por defecto (todo configurable desde config.yaml, seccion
'normalizacion') excluye:
  - Toda la categoria raiz "Bebidas" (agua, refrescos, alcohol, vino, zumos...):
    son bebidas para beber, no ingredientes de receta. Ojo: la leche y las
    bebidas vegetales NO estan aqui, estan en "Leche, Huevos, Lacteos...", que
    si es apta.
  - Cualquier subcategoria de alcohol alla donde aparezca (p.ej. "Vino Vegano"
    dentro de la categoria "Veganos").
  - Suplementos y dieteticos: nutricion deportiva, complementos/herbolario,
    alimentos funcionales, dieteticos de control de peso, proteina vegana.
  - Restos no alimentarios que se cuelan en "Supermercado Ecologico"
    (drogueria y perfumeria ecologicas).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# --- Valores por defecto (se pueden sobrescribir desde config.yaml) ---

DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS: tuple[str, ...] = ("bebidas",)

# Alcohol de COCINA: se usa en recetas (vino blanco/tinto para guisos, jerez,
# brandy, ron, cerveza, cava...). Aunque este bajo "Bebidas", estas subcategorias
# SI se marcan aptas (excepcion a la exclusion de alcohol). No incluye refrescos,
# zumos ni aguas. Se comprueba por palabra clave contra la SUBCATEGORIA.
DEFAULT_SUBCAT_ALCOHOL_COCINA: tuple[str, ...] = (
    "vino tinto",
    "vino blanco",
    "vino rosado",
    "vino rosados",
    "dulces y olorosos",
    "cerveza",
    "champagne",
    "cava",
    "sidra",
    "licor",
    "bebidas alcoholicas",
)

DEFAULT_KEYWORDS_EXCLUIDAS: tuple[str, ...] = (
    # Alcohol (en cualquier categoria)
    "alcohol",
    "cerveza",
    "vino",
    "licor",
    "champagne",
    "cava",
    "sidra",
    "sangria",
    "vermut",
    "tinto de verano",
    # Suplementos / dieteticos / deportiva
    "nutricion deportiva",
    "complementos naturales",
    "herbolario",
    "funcional",
    "dietetico",
    "proteina vegana",
    # Caros y malos nutricionalmente pese a palatables (fuera por decision del usuario)
    "golosina",
    "bolleria",
    # No alimentario
    "drogueria",
    "perfumeria",
)


def _normalizar_texto(texto: str) -> str:
    """Minusculas y sin acentos, para comparar de forma robusta."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin_acentos.lower().strip()


@dataclass
class ConfigClasificacion:
    categorias_raiz_excluidas: tuple[str, ...] = DEFAULT_CATEGORIAS_RAIZ_EXCLUIDAS
    keywords_excluidas: tuple[str, ...] = DEFAULT_KEYWORDS_EXCLUIDAS
    subcat_alcohol_cocina: tuple[str, ...] = DEFAULT_SUBCAT_ALCOHOL_COCINA
    # Normalizadas una sola vez al construir, para no repetir el trabajo por fila.
    _raices_norm: frozenset[str] = field(init=False)
    _keywords_norm: tuple[str, ...] = field(init=False)
    _alcohol_cocina_norm: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_raices_norm", frozenset(_normalizar_texto(c) for c in self.categorias_raiz_excluidas)
        )
        object.__setattr__(
            self, "_keywords_norm", tuple(_normalizar_texto(k) for k in self.keywords_excluidas)
        )
        object.__setattr__(
            self, "_alcohol_cocina_norm",
            tuple(_normalizar_texto(k) for k in self.subcat_alcohol_cocina),
        )


def es_apto_receta(categoria: str, subcategoria: str, config: ConfigClasificacion) -> bool:
    """True si el producto sirve como ingrediente/alimento para una receta.

    Las categorias raiz excluidas se comprueban contra el nombre de la raiz;
    las keywords, solo contra la SUBCATEGORIA. Esto es a proposito: hay una
    raiz cuyo nombre contiene "Nutricion deportiva" y "Funcional" ("Sin Gluten
    / Sin Lactosa, Nutricion deportiva y Funcional") pero cuyo contenido es
    mayormente comida apta (sin gluten, semillas, sin lactosa...). Si las
    keywords se aplicaran al nombre de la raiz, tumbarian toda esa rama.
    """
    subcategoria_norm = _normalizar_texto(subcategoria)

    # Excepcion: el alcohol de COCINA (vino, cerveza, jerez...) si es apto aunque
    # este bajo "Bebidas" o lo pille una keyword de alcohol -> se usa en recetas.
    if any(k in subcategoria_norm for k in config._alcohol_cocina_norm):
        return True

    if _normalizar_texto(categoria) in config._raices_norm:
        return False

    return not any(keyword in subcategoria_norm for keyword in config._keywords_norm)
