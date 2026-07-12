"""Clasificador determinista de recetas aptas para BATCHCOOKING.

Batchcooking = cocinar en tanda para varios dias: la receta debe aguantar bien
guardada/refrigerada, recalentarse sin estropearse y transportarse (tupper a la
oficina). Guisos, legumbres, arroces melosos/al horno, sopas y cremas, asados,
pasta al horno, currys y potajes son ideales. Las ENSALADAS tambien valen (se
preparan la vispera con el aliño aparte y se montan en la oficina). Frituras que se
reblandecen, planchas y crudos NO lo son (se comen al momento).

La clasificacion es 100% determinista (palabras clave sobre titulo + categoria +
cocina, sin acentos), en linea con el motor sin IA. Regla: apta si aparece alguna
senal POSITIVA y ninguna NEGATIVA fuerte.
"""

from __future__ import annotations

import sqlite3

from ..matching.normalizar import quitar_acentos

# Senales de que la receta SE COCINA EN TANDA y aguanta/recalienta/transporta bien.
_POSITIVAS = (
    "guiso", "guisad", "guisant", "estofad", "estofa", "potaje", "cocido",
    "puchero", "olla", "caldereta", "caldeirada", "marmitako", "fricando",
    "ragu", "bolonesa", "bolognesa", "albondiga", "lenteja", "garbanzo",
    "alubia", "judia", "judion", "faba", "fabada", "frijol", "pochas",
    "chili", "chile con carne", "curry", "curri", "dahl", "dal ", "sopa",
    "crema de", "pure", "gazpacho", "salmorejo", "lasana", "lasaña",
    "canelon", "macarron", "arroz", "paella", "fideua", "risotto", "pisto",
    "ratatouille", "samfaina", "asad", "al horno", "hornead", "empanada",
    "croqueta", "escudella", "callos", "rabo de toro", "carrillera",
    "ossobuco", "redondo", "ropa vieja", "boeuf", "goulash", "tajine",
    "tortilla de patata", "tortilla espanola", "quiche", "pastel de",
    "menestra", "cazuela", "caponata", "chana", "moussaka", "hummus",
    # Proteina en salsa / caldos: aguantan y se recalientan sin problema.
    "en salsa", "caldo", "bolognese", "tinga", "adobo", "encebollad",
    "al ajillo", "brasead", "confitad", "chilindron", "agridulce",
    "a la jardinera", "en su jugo", "guisad", "estofad",
    # Ensaladas: se preparan la vispera y el aliño aparte -> se montan en la oficina.
    # (incluye ensaladilla). Cabe el batchcooking segun el usuario.
    "ensalad",
)

# Senales de que la receta SE COME AL MOMENTO / se estropea guardada.
_NEGATIVAS = (
    "a la plancha", " plancha", "frito", "frita", "fritos",
    "fritas", "rebozad", "tempura", "bunuelo", "tartar", "ceviche",
    "carpaccio", "sashimi", "sushi", "bocadillo", "sandwich", "tosta ",
    "tostada", "montadito", "revuelto", "huevo frito", "huevos fritos",
    "gofre", "wrap", "nachos", "crudite", "a la brasa", "brocheta",
)


def _texto(titulo: str | None, categoria: str | None = None, cocina: str | None = None) -> str:
    partes = [p for p in (titulo, categoria, cocina) if p]
    return quitar_acentos(" ".join(partes))


def es_batchcooking(
    titulo: str | None, categoria: str | None = None, cocina: str | None = None
) -> bool:
    """True si la receta es optima para cocinar en tanda (batchcooking)."""
    t = _texto(titulo, categoria, cocina)
    if not t:
        return False
    if any(neg in t for neg in _NEGATIVAS):
        return False
    return any(pos in t for pos in _POSITIVAS)


def clasificar_recetas(conn: sqlite3.Connection) -> dict[str, int]:
    """Recalcula es_batchcooking para todas las recetas. Devuelve un resumen."""
    filas = conn.execute("SELECT id, titulo, categoria, cocina, fuente FROM recetas").fetchall()
    total = aptas = aptas_esp = 0
    for f in filas:
        apta = es_batchcooking(f["titulo"], f["categoria"], f["cocina"])
        conn.execute(
            "UPDATE recetas SET es_batchcooking = ? WHERE id = ?", (1 if apta else 0, f["id"])
        )
        total += 1
        if apta:
            aptas += 1
            fuente = f["fuente"] or ""
            if fuente.endswith(".es") or "elperiodico" in fuente or "recetasgratis" in fuente:
                aptas_esp += 1
    conn.commit()
    return {
        "total": total,
        "batchcooking": aptas,
        "no_batchcooking": total - aptas,
        "batchcooking_espanolas": aptas_esp,
    }
