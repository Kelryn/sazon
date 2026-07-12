from __future__ import annotations

import sqlite3

from .modelos import Receta


class RecetaRepository:
    """Guarda y consulta recetas + sus ingredientes en SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_receta(self, receta: Receta, fecha_ingesta: str) -> None:
        """Inserta/reemplaza una receta y (re)escribe sus ingredientes."""
        self.conn.execute(
            """
            INSERT INTO recetas (id, url, fuente, titulo, raciones, tiempo_total_min,
                categoria, cocina, rating, rating_count, imagen, instrucciones, fecha_ingesta)
            VALUES (:id, :url, :fuente, :titulo, :raciones, :tiempo_total_min,
                :categoria, :cocina, :rating, :rating_count, :imagen, :instrucciones, :fecha_ingesta)
            ON CONFLICT(id) DO UPDATE SET
                titulo=excluded.titulo, raciones=excluded.raciones,
                tiempo_total_min=excluded.tiempo_total_min, categoria=excluded.categoria,
                cocina=excluded.cocina, rating=excluded.rating,
                rating_count=excluded.rating_count, imagen=excluded.imagen,
                instrucciones=excluded.instrucciones, fecha_ingesta=excluded.fecha_ingesta
            """,
            {
                "id": receta.id,
                "url": receta.url,
                "fuente": receta.fuente,
                "titulo": receta.titulo,
                "raciones": receta.raciones,
                "tiempo_total_min": receta.tiempo_total_min,
                "categoria": receta.categoria,
                "cocina": receta.cocina,
                "rating": receta.rating,
                "rating_count": receta.rating_count,
                "imagen": receta.imagen,
                "instrucciones": receta.instrucciones,
                "fecha_ingesta": fecha_ingesta,
            },
        )
        # Reemplaza los ingredientes (por si se reingesta la receta).
        self.conn.execute("DELETE FROM receta_ingredientes WHERE receta_id = ?", (receta.id,))
        self.conn.executemany(
            """
            INSERT INTO receta_ingredientes
                (receta_id, orden, texto_original, cantidad, unidad, nombre,
                 nombre_normalizado, cantidad_metrica, unidad_metrica)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    receta.id,
                    orden,
                    ing.texto_original,
                    ing.cantidad,
                    ing.unidad,
                    ing.nombre,
                    ing.nombre_normalizado,
                    ing.cantidad_metrica,
                    ing.unidad_metrica,
                )
                for orden, ing in enumerate(receta.ingredientes)
            ],
        )
        self.conn.commit()

    def contar_recetas(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM recetas").fetchone()["n"]

    def contar_ingredientes(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM receta_ingredientes").fetchone()["n"]

    def url_ya_ingerida(self, receta_id: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM recetas WHERE id = ? LIMIT 1", (receta_id,)
            ).fetchone()
            is not None
        )
