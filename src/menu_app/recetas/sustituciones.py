"""Asistente de sustituciones de cocina — #100 ("no tengo nata, ¿por qué la
cambio?"). Tabla curada a mano, DETERMINISTA (sin IA): no es "otro producto de
la misma subcategoría de Alcampo" (eso ya lo resuelve el matcher del carrito,
ver optimizacion/compra.py #53), sino sustituciones CULINARIAS reales, con la
proporción cuando aplica.
"""

from __future__ import annotations

from ..matching.normalizar import quitar_acentos

# Clave = ingrediente normalizado (sin acentos, minuscula); valor = lista de
# alternativas con su equivalencia, de mas a menos parecida.
_SUSTITUCIONES: dict[str, list[str]] = {
    "nata": [
        "leche evaporada (misma cantidad, menos grasa)",
        "yogur griego natural (misma cantidad, sabor mas acido)",
        "leche + mantequilla (3/4 leche + 1/4 mantequilla fundida)",
    ],
    "nata para montar": [
        "nata de soja o avena para montar (misma cantidad, apta vegana)",
        "claras de huevo montadas a punto de nieve (para postres, no salsas)",
    ],
    "mantequilla": [
        "aceite de oliva suave (3/4 de la cantidad)",
        "margarina (misma cantidad)",
        "aceite de coco (misma cantidad, en reposteria)",
    ],
    "huevo": [
        "1 cucharada de semillas de lino molidas + 3 de agua, reposar 5 min (por huevo)",
        "60 g de compota de manzana sin azucar (por huevo, en reposteria)",
        "1/2 platano maduro machacado (por huevo, en reposteria dulce)",
    ],
    "leche": [
        "bebida de avena o soja (misma cantidad)",
        "leche evaporada + agua a partes iguales",
    ],
    "yogur": [
        "nata liquida + unas gotas de limon (misma cantidad)",
        "queso fresco batido (misma cantidad)",
    ],
    "azucar": [
        "miel (3/4 de la cantidad, reduce el liquido de la receta un poco)",
        "panela o azucar moreno (misma cantidad)",
        "edulcorante segun su equivalencia (mirar el envase)",
    ],
    "harina": [
        "harina de repostería sin gluten 1:1 (si no hay problema de gluten, no es necesario)",
        "maizena (mitad de cantidad, solo para espesar salsas, no para hornear)",
    ],
    "vino blanco": [
        "caldo de pollo o verduras + un chorrito de vinagre de manzana",
        "zumo de manzana + un chorrito de vinagre",
    ],
    "vino tinto": [
        "caldo de carne + un chorrito de vinagre de vino tinto",
    ],
    "caldo": [
        "pastilla o concentrado de caldo disuelto en agua caliente",
        "agua + un chorrito de salsa de soja (perfil mas salado, ajustar sal)",
    ],
    "queso parmesano": [
        "queso grana padano (misma cantidad)",
        "levadura nutricional (menos cantidad, sabor mas suave, apto vegano)",
    ],
    "limon": [
        "vinagre blanco (mitad de cantidad, el sabor es mas fuerte)",
        "acido citrico en polvo (una pizca por cada limon)",
    ],
    "cilantro": [
        "perejil fresco (sabor mas suave, misma cantidad)",
    ],
    "vinagre": [
        "zumo de limon (misma cantidad)",
    ],
    "levadura": [
        "1 cucharadita de bicarbonato + 1/2 de vinagre o zumo de limon (por cada sobre)",
    ],
    "pan rallado": [
        "copos de avena triturados (misma cantidad)",
        "harina de maiz o cuscurros de pan tostado triturados",
    ],
}

# Alias -> clave canonica (variantes habituales que apuntan a la misma entrada).
_ALIAS: dict[str, str] = {
    "crema de leche": "nata",
    "crema para batir": "nata para montar",
    "nata liquida": "nata",
    "mantequilla sin sal": "mantequilla",
    "azucar blanco": "azucar",
    "azucar blanca": "azucar",
    "leche entera": "leche",
    "leche semidesnatada": "leche",
    "yogur natural": "yogur",
    "harina de trigo": "harina",
    "queso parmesano rallado": "queso parmesano",
    "vino blanco seco": "vino blanco",
}


def buscar_sustitutos(ingrediente: str) -> tuple[str, list[str]] | None:
    """Busca sustituciones para `ingrediente` (texto libre, p.ej. de un buscador).
    Devuelve (clave_encontrada, [alternativas]) o None si no hay entrada.
    Coincide por CONTENCION (ambos sentidos) para admitir variantes con o sin
    adjetivos ("nata para cocinar" -> "nata")."""
    q = quitar_acentos(ingrediente or "").strip()
    if not q:
        return None
    q = _ALIAS.get(q, q)
    if q in _SUSTITUCIONES:
        return q, _SUSTITUCIONES[q]
    # Coincidencia parcial: la clave de la tabla aparece dentro de lo buscado,
    # o lo buscado aparece dentro de la clave (para variantes cortas/largas).
    candidatos = [
        clave for clave in _SUSTITUCIONES
        if clave in q or q in clave
    ]
    if candidatos:
        mejor = min(candidatos, key=len)  # la coincidencia mas especifica (mas corta)
        return mejor, _SUSTITUCIONES[mejor]
    return None
