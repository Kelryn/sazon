"""Avisos de subida de precio (#118): compara los DOS puntos mas recientes de
`precios_historico` (que ya se rellena en cada actualizacion del catalogo, ver
ProductoRepository.upsert_muchos) y señala subidas relevantes."""

from __future__ import annotations

import sqlite3

UMBRAL_PCT_DEFECTO = 8.0


def subidas_de_precio(
    conn: sqlite3.Connection,
    rids: list[str] | None = None,
    umbral_pct: float = UMBRAL_PCT_DEFECTO,
) -> list[dict]:
    """Productos cuyo precio ha SUBIDO al menos `umbral_pct`% entre los dos
    últimos puntos de su histórico. `rids`: si se da (incluida una lista
    vacía), limita la búsqueda a esos productos (p.ej. los de la lista de la
    compra actual); None = sin filtro, todo el catálogo."""
    if rids is not None and not rids:
        return []
    sql = "SELECT retailer_product_id, fecha, precio_eur FROM precios_historico"
    params: list = []
    if rids is not None:
        marcadores = ", ".join("?" for _ in rids)
        sql += f" WHERE retailer_product_id IN ({marcadores})"
        params = list(rids)
    sql += " ORDER BY retailer_product_id, fecha"

    por_producto: dict[str, list[tuple[str, float]]] = {}
    for fila in conn.execute(sql, params).fetchall():
        if fila["precio_eur"] is None:
            continue
        por_producto.setdefault(fila["retailer_product_id"], []).append(
            (fila["fecha"], fila["precio_eur"])
        )

    avisos: list[dict] = []
    for rid, puntos in por_producto.items():
        if len(puntos) < 2:
            continue
        (_f_ant, precio_ant), (_f_nuevo, precio_nuevo) = puntos[-2], puntos[-1]
        if precio_ant <= 0:
            continue
        subida_pct = (precio_nuevo - precio_ant) / precio_ant * 100
        if subida_pct < umbral_pct:
            continue
        fila_nombre = conn.execute(
            "SELECT nombre FROM productos WHERE retailer_product_id = ?", (rid,)
        ).fetchone()
        avisos.append({
            "retailer_product_id": rid,
            "nombre": fila_nombre["nombre"] if fila_nombre else rid,
            "precio_anterior": precio_ant,
            "precio_actual": precio_nuevo,
            "subida_pct": round(subida_pct, 1),
        })
    avisos.sort(key=lambda a: -a["subida_pct"])
    return avisos
