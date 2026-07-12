from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from .modelos import ProductoNormalizado

_COLUMNAS = [
    "retailer_product_id",
    "nombre",
    "marca",
    "categoria",
    "subcategoria",
    "precio_eur",
    "precio_por_unidad",
    "unidad_medida",
    "formato",
    "cantidad_formato",
    "unidad_formato",
    "cantidad_base_g_ml",
    "tipo_medida",
    "disponible",
    "en_oferta",
    "precio_oferta",
    "url_producto",
    "url_imagen",
    "apto_receta",
    "fecha_extraccion",
    "fecha_actualizacion",
]

_UPSERT = f"""
INSERT INTO productos ({", ".join(_COLUMNAS)})
VALUES ({", ".join(":" + c for c in _COLUMNAS)})
ON CONFLICT(retailer_product_id) DO UPDATE SET
    {", ".join(f"{c} = excluded.{c}" for c in _COLUMNAS if c != "retailer_product_id")}
"""


class ProductoRepository:
    """Guarda y consulta productos normalizados en SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_muchos(
        self, productos: Iterable[ProductoNormalizado], fecha_actualizacion: str
    ) -> dict[str, int]:
        """Inserta/actualiza productos y registra los cambios de precio.

        Devuelve un pequeño resumen: cuantos productos se procesaron, cuantos
        eran nuevos y en cuantos cambio el precio respecto a lo ya almacenado.
        """
        productos = list(productos)
        ids = [p.retailer_product_id for p in productos]
        precios_previos = self._precios_actuales(ids)

        filas = []
        historico = []
        nuevos = 0
        cambios_precio = 0
        for p in productos:
            filas.append(_a_fila(p, fecha_actualizacion))

            previo = precios_previos.get(p.retailer_product_id, "_ausente_")
            if previo == "_ausente_":
                nuevos += 1
                historico.append((p.retailer_product_id, fecha_actualizacion, p.precio_eur))
            elif previo != p.precio_eur:
                cambios_precio += 1
                historico.append((p.retailer_product_id, fecha_actualizacion, p.precio_eur))

        self.conn.executemany(_UPSERT, filas)
        self.conn.executemany(
            "INSERT INTO precios_historico (retailer_product_id, fecha, precio_eur) "
            "VALUES (?, ?, ?)",
            historico,
        )
        self.conn.commit()
        return {
            "procesados": len(productos),
            "nuevos": nuevos,
            "cambios_precio": cambios_precio,
        }

    def _precios_actuales(self, ids: list[str]) -> dict[str, float | None]:
        if not ids:
            return {}
        marcadores = ", ".join("?" for _ in ids)
        cur = self.conn.execute(
            f"SELECT retailer_product_id, precio_eur FROM productos "
            f"WHERE retailer_product_id IN ({marcadores})",
            ids,
        )
        return {row["retailer_product_id"]: row["precio_eur"] for row in cur.fetchall()}

    def ids_sin_enriquecer(self, solo_aptos: bool = True, limite: int | None = None) -> list[str]:
        """Productos aun sin datos nutricionales (fecha_enriquecimiento NULL)."""
        sql = "SELECT retailer_product_id FROM productos WHERE fecha_enriquecimiento IS NULL"
        if solo_aptos:
            sql += " AND apto_receta = 1"
        sql += " ORDER BY retailer_product_id"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return [row["retailer_product_id"] for row in self.conn.execute(sql).fetchall()]

    def actualizar_detalle(self, retailer_product_id: str, detalle, fecha_enriquecimiento: str) -> None:
        """Guarda el detalle nutricional de un producto (marca la fecha aunque
        el producto no tenga nutricion, para no reintentarlo en cada pasada)."""
        self.conn.execute(
            """
            UPDATE productos SET
                energia_kcal_100g = :energia_kcal_100g,
                grasas_100g = :grasas_100g,
                grasas_sat_100g = :grasas_sat_100g,
                hidratos_100g = :hidratos_100g,
                azucares_100g = :azucares_100g,
                proteinas_100g = :proteinas_100g,
                sal_100g = :sal_100g,
                fibra_100g = :fibra_100g,
                ingredientes = :ingredientes,
                origen = :origen,
                base_nutricional = :base_nutricional,
                fecha_enriquecimiento = :fecha_enriquecimiento
            WHERE retailer_product_id = :rid
            """,
            {
                "energia_kcal_100g": detalle.energia_kcal_100g,
                "grasas_100g": detalle.grasas_100g,
                "grasas_sat_100g": detalle.grasas_sat_100g,
                "hidratos_100g": detalle.hidratos_100g,
                "azucares_100g": detalle.azucares_100g,
                "proteinas_100g": detalle.proteinas_100g,
                "sal_100g": detalle.sal_100g,
                "fibra_100g": detalle.fibra_100g,
                "ingredientes": detalle.ingredientes,
                "origen": detalle.origen,
                "base_nutricional": detalle.base_nutricional,
                "fecha_enriquecimiento": fecha_enriquecimiento,
                "rid": retailer_product_id,
            },
        )
        self.conn.commit()

    def contar_enriquecidos_con_nutricion(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM productos WHERE energia_kcal_100g IS NOT NULL"
        ).fetchone()["n"]

    def productos_sin_off(
        self, solo_aptos: bool = True, limite: int | None = None
    ) -> list[tuple[str, str, str | None]]:
        """(retailer_product_id, nombre, marca) de productos aun sin cruce OFF."""
        sql = "SELECT retailer_product_id, nombre, marca FROM productos WHERE fecha_off IS NULL"
        if solo_aptos:
            sql += " AND apto_receta = 1"
        sql += " ORDER BY retailer_product_id"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return [
            (r["retailer_product_id"], r["nombre"], r["marca"])
            for r in self.conn.execute(sql).fetchall()
        ]

    def actualizar_off(self, retailer_product_id: str, datos, fecha_off: str) -> None:
        """Guarda el cruce OFF (marca la fecha aunque no haya match, para no
        reintentarlo en cada pasada). `datos` es None si no hubo match fiable."""
        self.conn.execute(
            """
            UPDATE productos SET
                ean = :ean,
                nutri_score = :nutri_score,
                nova = :nova,
                alergenos = :alergenos,
                off_product_name = :off_product_name,
                off_match_score = :off_match_score,
                fecha_off = :fecha_off
            WHERE retailer_product_id = :rid
            """,
            {
                "ean": datos.ean if datos else None,
                "nutri_score": datos.nutri_score if datos else None,
                "nova": datos.nova if datos else None,
                "alergenos": datos.alergenos if datos else None,
                "off_product_name": datos.off_product_name if datos else None,
                "off_match_score": datos.match_score if datos else None,
                "fecha_off": fecha_off,
                "rid": retailer_product_id,
            },
        )
        self.conn.commit()

    def contar_con_off(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM productos WHERE off_match_score IS NOT NULL"
        ).fetchone()["n"]

    def contar(self, solo_aptos: bool = False) -> int:
        sql = "SELECT COUNT(*) AS n FROM productos"
        if solo_aptos:
            sql += " WHERE apto_receta = 1"
        return self.conn.execute(sql).fetchone()["n"]

    def contar_por_apto(self) -> dict[bool, int]:
        cur = self.conn.execute(
            "SELECT apto_receta, COUNT(*) AS n FROM productos GROUP BY apto_receta"
        )
        return {bool(row["apto_receta"]): row["n"] for row in cur.fetchall()}


def _a_fila(p: ProductoNormalizado, fecha_actualizacion: str) -> dict[str, object]:
    return {
        "retailer_product_id": p.retailer_product_id,
        "nombre": p.nombre,
        "marca": p.marca,
        "categoria": p.categoria,
        "subcategoria": p.subcategoria,
        "precio_eur": p.precio_eur,
        "precio_por_unidad": p.precio_por_unidad,
        "unidad_medida": p.unidad_medida,
        "formato": p.formato,
        "cantidad_formato": p.cantidad_formato,
        "unidad_formato": p.unidad_formato,
        "cantidad_base_g_ml": p.cantidad_base_g_ml,
        "tipo_medida": p.tipo_medida,
        "disponible": int(p.disponible),
        "en_oferta": int(p.en_oferta),
        "precio_oferta": p.precio_oferta,
        "url_producto": p.url_producto,
        "url_imagen": p.url_imagen,
        "apto_receta": int(p.apto_receta),
        "fecha_extraccion": p.fecha_extraccion,
        "fecha_actualizacion": fecha_actualizacion,
    }
