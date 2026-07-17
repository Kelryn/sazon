"""Palatabilidad de cada receta = lo sabroso que es, a partir de ratings reales.

Se usa la MEDIA BAYESIANA (ponderada por nº de reseñas) para no fiarse de una
receta con 5 estrellas y 1 voto frente a otra con 4,3 y 500 votos:

    bayes = (C * m + n * r) / (C + n)

donde m = media global de ratings, C = peso del prior (nº de "votos virtuales"),
r = rating de la receta, n = nº de reseñas. El resultado se normaliza a 0..1.
Las recetas sin rating reciben la media global (neutral).

Lote 12: si el usuario ha VALORADO una receta personalmente (cualquier baremo,
ver recetas/valoraciones.py), esa valoración pesa MÁS que el rating anónimo del
sitio de origen (es, al fin y al cabo, su propio gusto) — se mezcla con
`PESO_PERSONAL` en vez de sustituir el rating del sitio del todo.
"""

from __future__ import annotations

import sqlite3

PESO_PRIOR = 10  # C: cuantos votos "virtuales" pesa el prior
ESCALA_MAX = 5.0  # los ratings vienen en 0..5
PESO_PERSONAL = 0.6  # cuanto pesa la valoracion personal frente al rating del sitio


def _palatabilidad_personal(conn: sqlite3.Connection) -> dict[str, float]:
    """receta_id -> media de TODOS sus baremos valorados, 0..1. Vacio si el
    usuario no ha valorado nada todavia."""
    filas = conn.execute(
        "SELECT receta_id, AVG(estrellas) AS media FROM valoraciones GROUP BY receta_id"
    ).fetchall()
    return {f["receta_id"]: f["media"] / ESCALA_MAX for f in filas}


def palatabilidad_bayesiana(
    conn: sqlite3.Connection, peso_prior: int = PESO_PRIOR, peso_personal: float = PESO_PERSONAL
) -> dict[str, float]:
    """receta_id -> palatabilidad 0..1 (media bayesiana normalizada, mezclada
    con la valoración personal si existe)."""
    filas = conn.execute("SELECT id, rating, rating_count FROM recetas").fetchall()
    con_rating = [(f["rating"], f["rating_count"] or 0) for f in filas if f["rating"] is not None]

    if con_rating:
        # Media global ponderada por nº de votos (o simple si faltan counts).
        total_votos = sum(max(n, 1) for _, n in con_rating)
        m = sum(r * max(n, 1) for r, n in con_rating) / total_votos
    else:
        m = ESCALA_MAX / 2  # sin datos: neutral

    personal = _palatabilidad_personal(conn)
    resultado: dict[str, float] = {}
    for f in filas:
        r, n = f["rating"], f["rating_count"] or 0
        if r is None:
            bayes = m  # sin rating -> media global
        else:
            bayes = (peso_prior * m + n * r) / (peso_prior + n)
        valor = min(bayes / ESCALA_MAX, 1.0)
        if f["id"] in personal:
            valor = (1 - peso_personal) * valor + peso_personal * personal[f["id"]]
        resultado[f["id"]] = round(valor, 3)
    return resultado
