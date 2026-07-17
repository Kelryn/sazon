"""Detección de productos descatalogados y re-match automático — #117.

`actualizar_catalogo` nunca BORRA productos (ver almacenamiento/actualizar.py):
si Alcampo deja de vender uno, simplemente deja de aparecer en la siguiente
actualización de su categoría, así que su `fecha_actualizacion` se queda
CONGELADA mientras el resto de la categoría avanza. Esa es la señal: un
ingrediente cuyo producto emparejado tiene una fecha más antigua que la última
actualización global probablemente ya no se vende.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from .matcher import UMBRAL_LEXICO, IndiceProductos, MatcherLexico
from .repositorio import MatchingRepository


def productos_descatalogados(conn: sqlite3.Connection) -> list[dict]:
    """Ingredientes cuyo producto emparejado no aparecio en la ULTIMA
    actualizacion de SU CATEGORIA. No borra ni cambia nada; solo lo señala.

    Importante: la comparacion es POR CATEGORIA, no contra el maximo global —
    las categorias se actualizan de forma independiente (checkboxes en
    /catalogo), asi que una categoria que lleve un dia sin tocarse mientras
    otra se actualiza HOY no significa que sus productos esten descatalogados.
    """
    filas = conn.execute(
        """
        SELECT m.ingrediente_norm, m.clave_matching, m.retailer_product_id AS rid_actual,
               p.nombre, p.categoria, p.fecha_actualizacion
        FROM mapeo_ingr_producto m
        JOIN productos p ON p.retailer_product_id = m.retailer_product_id
        JOIN (
            SELECT categoria, MAX(fecha_actualizacion) AS ultima
            FROM productos GROUP BY categoria
        ) ult ON ult.categoria IS NOT DISTINCT FROM p.categoria
        WHERE m.retailer_product_id IS NOT NULL AND p.fecha_actualizacion < ult.ultima
        """
    ).fetchall()
    return [dict(f) for f in filas]


def rematch_descatalogados(conn: sqlite3.Connection, umbral: float = UMBRAL_LEXICO) -> dict:
    """Re-empareja los ingredientes descatalogados con un producto VIGENTE (de la
    última actualización), si el matcher léxico encuentra uno igual de bueno.
    Devuelve {revisados, reemparejados}. No toca los que ya estaban bien."""
    descatalogados = productos_descatalogados(conn)
    if not descatalogados:
        return {"revisados": 0, "reemparejados": 0}

    # "Vigente" = a la ultima actualizacion de SU categoria (no un valor global
    # unico), por la misma razon que arriba: cada categoria se actualiza aparte.
    vigentes = conn.execute(
        """
        SELECT p.retailer_product_id, p.nombre, p.marca, p.precio_por_unidad
        FROM productos p
        JOIN (
            SELECT categoria, MAX(fecha_actualizacion) AS ultima
            FROM productos GROUP BY categoria
        ) ult ON ult.categoria IS NOT DISTINCT FROM p.categoria
        WHERE p.apto_receta = 1 AND p.fecha_actualizacion >= ult.ultima
        """
    ).fetchall()
    indice = IndiceProductos.construir(
        [(r["retailer_product_id"], r["nombre"], r["marca"], r["precio_por_unidad"]) for r in vigentes]
    )
    matcher = MatcherLexico(indice, umbral=umbral)
    repo = MatchingRepository(conn)
    fecha = datetime.now(UTC).isoformat(timespec="seconds")

    reemparejados = 0
    for item in descatalogados:
        match = matcher.emparejar(item["clave_matching"])
        if match and match.retailer_product_id != item["rid_actual"]:
            repo.upsert_mapeo(item["ingrediente_norm"], item["clave_matching"], match, "auto", fecha)
            reemparejados += 1
    conn.commit()
    return {"revisados": len(descatalogados), "reemparejados": reemparejados}
