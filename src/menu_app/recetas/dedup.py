"""Deteccion de recetas CASI-DUPLICADAS (#45): mismo plato, distinta fuente.

Determinista: compara el titulo normalizado (primera palabra significativa, como
`familia_receta`) y el solapamiento de ingredientes (Jaccard). NO borra nada solo:
genera un reporte para que el usuario decida (ver menu-app-dedup-recetas).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_UMBRAL_JACCARD = 0.6  # fraccion de ingredientes compartidos para considerar duplicado


@dataclass
class GrupoDuplicado:
    familia: str
    recetas: list[tuple[str, str, str]]  # (id, titulo, fuente)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def encontrar_duplicados(conn: sqlite3.Connection) -> list[GrupoDuplicado]:
    """Agrupa por familia (misma primera palabra significativa del titulo) y, dentro
    de cada familia, junta las que comparten >=60% de sus ingredientes."""
    from ..optimizacion.servicio import familia_receta

    filas = conn.execute("SELECT id, titulo, fuente FROM recetas").fetchall()
    por_familia: dict[str, list[tuple[str, str, str]]] = {}
    for r in filas:
        fam = familia_receta(r["titulo"])
        if fam:
            por_familia.setdefault(fam, []).append((r["id"], r["titulo"], r["fuente"] or ""))

    ingredientes: dict[str, set[str]] = {}
    for row in conn.execute(
        "SELECT receta_id, nombre_normalizado FROM receta_ingredientes "
        "WHERE nombre_normalizado IS NOT NULL"
    ).fetchall():
        ingredientes.setdefault(row["receta_id"], set()).add(row["nombre_normalizado"])

    grupos: list[GrupoDuplicado] = []
    for fam, recetas in por_familia.items():
        if len(recetas) < 2:
            continue
        vistos: set[str] = set()
        for i, (rid_a, _t, _f) in enumerate(recetas):
            if rid_a in vistos:
                continue
            similares = [recetas[i]]
            for rid_b, t_b, f_b in recetas[i + 1:]:
                if rid_b in vistos:
                    continue
                if _jaccard(ingredientes.get(rid_a, set()), ingredientes.get(rid_b, set())) >= _UMBRAL_JACCARD:
                    similares.append((rid_b, t_b, f_b))
                    vistos.add(rid_b)
            if len(similares) > 1:
                vistos.add(rid_a)
                grupos.append(GrupoDuplicado(familia=fam, recetas=similares))
    return grupos
