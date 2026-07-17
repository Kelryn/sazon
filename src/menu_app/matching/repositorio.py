from __future__ import annotations

import sqlite3


class MatchingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def productos_aptos(self) -> list[tuple[str, str, str | None, float | None]]:
        """(retailer_product_id, nombre, marca, precio_por_unidad) de los productos
        aptos para receta. El precio permite desempatar por el mas barato (#15/#16)."""
        cur = self.conn.execute(
            "SELECT retailer_product_id, nombre, marca, precio_por_unidad "
            "FROM productos WHERE apto_receta = 1"
        )
        return [
            (r["retailer_product_id"], r["nombre"], r["marca"], r["precio_por_unidad"])
            for r in cur.fetchall()
        ]

    def ingredientes_distintos(self) -> list[str]:
        """Nombres normalizados distintos de ingredientes de receta (no vacios)."""
        cur = self.conn.execute(
            "SELECT DISTINCT nombre_normalizado FROM receta_ingredientes "
            "WHERE nombre_normalizado <> '' ORDER BY nombre_normalizado"
        )
        return [r["nombre_normalizado"] for r in cur.fetchall()]

    def upsert_mapeo(
        self,
        ingrediente_norm: str,
        clave_matching: str,
        match,  # matcher.Match | None
        metodo_sin_match: str,
        fecha: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO mapeo_ingr_producto
                (ingrediente_norm, clave_matching, retailer_product_id, producto_nombre,
                 score, metodo, fecha)
            VALUES (:ing, :clave, :rid, :nombre, :score, :metodo, :fecha)
            ON CONFLICT(ingrediente_norm) DO UPDATE SET
                clave_matching=excluded.clave_matching,
                retailer_product_id=excluded.retailer_product_id,
                producto_nombre=excluded.producto_nombre,
                score=excluded.score, metodo=excluded.metodo, fecha=excluded.fecha
            """,
            {
                "ing": ingrediente_norm,
                "clave": clave_matching,
                "rid": match.retailer_product_id if match else None,
                "nombre": match.producto_nombre if match else None,
                "score": match.score if match else None,
                "metodo": match.metodo if match else metodo_sin_match,
                "fecha": fecha,
            },
        )
        self.conn.commit()

    def contar_mapeos(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM mapeo_ingr_producto").fetchone()["n"]

    def contar_con_match(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM mapeo_ingr_producto WHERE retailer_product_id IS NOT NULL"
        ).fetchone()["n"]
