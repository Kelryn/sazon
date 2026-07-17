"""Sugerencia de desayunos/meriendas de la semana (#50).

Deliberadamente SEPARADO del optimizador MILP de comida+cena: integrar una tercera
franja en el solver requeriria el mismo rediseño "modelo por dia" que #37/#38 (ver
PLAN_MEJORAS.md), arriesgado para el motor que ya funciona. En su lugar, esto es un
sugeridor determinista: rota recetas de rol='desayuno' sin repetir en la semana,
preferiendo coste bajo y buena valoracion. No entra en el coste/nutricion del menu
principal; es orientativo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .economia_recetas import calcular_todas
from .palatabilidad import palatabilidad_bayesiana


@dataclass
class SugerenciaDesayuno:
    receta_id: str
    titulo: str
    coste_racion: float


def sugerir_desayunos(conn: sqlite3.Connection, dias: int) -> list[SugerenciaDesayuno]:
    """`dias` sugerencias de desayuno/merienda, sin repetir si hay suficientes
    recetas de rol='desayuno' con coste conocido. Orden: mejor valoradas primero,
    desempate por coste; si faltan para cubrir `dias`, se repiten rotando."""
    palat = palatabilidad_bayesiana(conn)
    candidatas = [
        c for c in calcular_todas(conn)
        if c.rol == "desayuno" and c.coste_racion is not None and c.raciones
    ]
    candidatas.sort(key=lambda c: (-palat.get(c.receta_id, 0.5), c.coste_racion))
    if not candidatas:
        return []
    return [
        SugerenciaDesayuno(c.receta_id, c.titulo, round(c.coste_racion, 2))
        for c in (candidatas[i % len(candidatas)] for i in range(dias))
    ]
