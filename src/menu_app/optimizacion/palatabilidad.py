"""Palatabilidad de cada receta = lo sabroso que es, a partir de ratings reales.

Se usa la MEDIA BAYESIANA (ponderada por nº de reseñas) para no fiarse de una
receta con 5 estrellas y 1 voto frente a otra con 4,3 y 500 votos:

    bayes = (C * m + n * r) / (C + n)

donde m = media global de ratings, C = peso del prior (nº de "votos virtuales"),
r = rating de la receta, n = nº de reseñas. El resultado se normaliza a 0..1.
Las recetas sin rating reciben la media global (neutral).
"""

from __future__ import annotations

import sqlite3

PESO_PRIOR = 10  # C: cuantos votos "virtuales" pesa el prior
ESCALA_MAX = 5.0  # los ratings vienen en 0..5


def palatabilidad_bayesiana(
    conn: sqlite3.Connection, peso_prior: int = PESO_PRIOR
) -> dict[str, float]:
    """receta_id -> palatabilidad 0..1 (media bayesiana normalizada)."""
    filas = conn.execute("SELECT id, rating, rating_count FROM recetas").fetchall()
    con_rating = [(f["rating"], f["rating_count"] or 0) for f in filas if f["rating"] is not None]

    if con_rating:
        # Media global ponderada por nº de votos (o simple si faltan counts).
        total_votos = sum(max(n, 1) for _, n in con_rating)
        m = sum(r * max(n, 1) for r, n in con_rating) / total_votos
    else:
        m = ESCALA_MAX / 2  # sin datos: neutral

    resultado: dict[str, float] = {}
    for f in filas:
        r, n = f["rating"], f["rating_count"] or 0
        if r is None:
            bayes = m  # sin rating -> media global
        else:
            bayes = (peso_prior * m + n * r) / (peso_prior + n)
        resultado[f["id"]] = round(min(bayes / ESCALA_MAX, 1.0), 3)
    return resultado
