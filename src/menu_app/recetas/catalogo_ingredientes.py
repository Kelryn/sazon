"""Catalogo de ingredientes para el editor de recetas.

Ofrece la lista de posibles ingredientes (nombres de producto aptos de Alcampo)
para el desplegable buscable, y el calculo de nutrientes de una receta que se
esta editando (para mostrar las barras).
"""

from __future__ import annotations

import sqlite3

from ..matching.matcher import MatcherLexico, indice_productos_aptos_cacheado
from ..matching.normalizar import clave_ingrediente
from ..matching.repositorio import MatchingRepository
from ..optimizacion.economia_recetas import NUTRIENTES, _gramos_por_piezas
from .manual import UNIDADES


def ingredientes_catalogo(conn: sqlite3.Connection) -> list[str]:
    """Nombres de producto aptos (para el desplegable). Ordenados alfabeticamente."""
    filas = conn.execute(
        "SELECT DISTINCT nombre FROM productos WHERE apto_receta = 1 AND nombre IS NOT NULL "
        "ORDER BY nombre"
    ).fetchall()
    return [f["nombre"] for f in filas]


def _nutricion_por_rid(conn: sqlite3.Connection) -> dict[str, dict]:
    cols = ", ".join([f"{n}_100g" for n in NUTRIENTES])
    return {
        f["retailer_product_id"]: dict(f)
        for f in conn.execute(
            f"SELECT retailer_product_id, {cols} FROM productos WHERE apto_receta = 1"
        ).fetchall()
    }


def nutrientes_receta(
    conn: sqlite3.Connection, ingredientes: list[dict], raciones: int
) -> dict[str, float]:
    """Nutrientes POR RACION de una receta en edicion (para las barras del editor).

    `ingredientes`: [{nombre, cantidad, unidad}]. Usa el MISMO matcher determinista
    que el menu para casar cada ingrediente con un producto de Alcampo (robusto
    aunque el nombre no sea exacto) y prorratea por 100 g/ml.
    """
    repo = MatchingRepository(conn)
    indice = indice_productos_aptos_cacheado(conn, repo.productos_aptos())
    matcher = MatcherLexico(indice)
    nutricion_rid = _nutricion_por_rid(conn)

    total = {n: 0.0 for n in NUTRIENTES}
    for ing in ingredientes:
        nombre = (ing.get("nombre") or "").strip()
        if not nombre:
            continue
        try:
            cantidad = float(ing.get("cantidad"))
        except (TypeError, ValueError):
            continue
        unidad = ing.get("unidad") or "g"
        _metrica, factor = UNIDADES.get(unidad, (None, None))
        gramos = cantidad * factor if factor is not None else _gramos_por_piezas(
            clave_ingrediente(nombre), unidad, cantidad
        )
        if gramos is None:
            continue
        match = matcher.emparejar(clave_ingrediente(nombre))
        prod = nutricion_rid.get(match.retailer_product_id) if match else None
        if not prod:
            continue
        for n in NUTRIENTES:
            v = prod.get(f"{n}_100g")
            if v is not None:
                total[n] += gramos / 100.0 * v
    raciones = raciones or 1
    return {n: v / raciones for n, v in total.items()}
