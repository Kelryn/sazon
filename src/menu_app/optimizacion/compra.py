"""Lista de la compra del plan de menus (estilo recibo).

Agrega los ingredientes de TODAS las semanas del plan guardado, los traduce a
productos de Alcampo (por el mapeo determinista) y calcula cuantas UNIDADES de
cada producto hay que comprar segun su formato (paquete de X g/ml), con precio
unitario, total por linea y total del ticket. Cada linea lleva el enlace a la
web de Alcampo para echarlo al carrito.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field

from ..optimizacion.economia_recetas import _gramos_por_piezas
from .planes import cargar_plan


@dataclass
class LineaCompra:
    producto_id: str
    nombre: str
    url: str | None
    gramos_necesarios: float  # g o ml
    formato_g_ml: float | None  # tamaño del paquete (None si desconocido)
    unidades: int
    precio_unidad: float | None  # € por paquete
    total: float | None
    pasillo: str = "Otros"  # categoria/pasillo de Alcampo

    @property
    def cantidad_legible(self) -> str:
        if self.gramos_necesarios >= 1000:
            return f"{self.gramos_necesarios / 1000:.1f} kg"
        return f"{self.gramos_necesarios:.0f} g"


@dataclass
class Compra:
    plan_id: str | None
    semanas: int
    lineas: list[LineaCompra] = field(default_factory=list)
    sin_producto: list[str] = field(default_factory=list)  # ingredientes sin match

    @property
    def total(self) -> float:
        return round(sum(l.total for l in self.lineas if l.total is not None), 2)

    def por_pasillo(self) -> dict[str, list[LineaCompra]]:
        """Lineas agrupadas por pasillo/categoria (para la lista de la compra)."""
        grupos: dict[str, list[LineaCompra]] = {}
        for l in self.lineas:
            grupos.setdefault(l.pasillo, []).append(l)
        return dict(sorted(grupos.items()))


def _necesidades_gramos(
    conn: sqlite3.Connection, raciones_por_receta: dict[str, float], num_comensales: int
) -> tuple[dict[str, float], set[str]]:
    """gramos necesarios por producto (rid Alcampo) para servir esas raciones."""
    mapeo = {
        f["ingrediente_norm"]: f["retailer_product_id"]
        for f in conn.execute(
            "SELECT ingrediente_norm, retailer_product_id FROM mapeo_ingr_producto "
            "WHERE retailer_product_id IS NOT NULL"
        ).fetchall()
    }
    necesidades: dict[str, float] = {}
    sin_producto: set[str] = set()
    for receta_id, raciones in raciones_por_receta.items():
        cab = conn.execute("SELECT raciones FROM recetas WHERE id = ?", (receta_id,)).fetchone()
        raciones_receta = (cab["raciones"] if cab else None) or 1
        factor = raciones * num_comensales / raciones_receta  # fraccion de receta a cocinar
        for ing in conn.execute(
            "SELECT nombre_normalizado, cantidad, unidad, cantidad_metrica FROM receta_ingredientes "
            "WHERE receta_id = ?",
            (receta_id,),
        ).fetchall():
            gramos = ing["cantidad_metrica"]
            if gramos is None:
                gramos = _gramos_por_piezas(ing["nombre_normalizado"], ing["unidad"], ing["cantidad"])
            if gramos is None:
                continue
            rid = mapeo.get(ing["nombre_normalizado"])
            if rid is None:
                sin_producto.add(ing["nombre_normalizado"])
                continue
            necesidades[rid] = necesidades.get(rid, 0.0) + gramos * factor
    return necesidades, sin_producto


def lista_compra(
    conn: sqlite3.Connection, plan_id: str | None = None, despensa: list[str] | None = None
) -> Compra:
    """Construye la lista de la compra del plan (todas sus semanas).

    `despensa`: nombres de ingredientes que ya se tienen en casa; sus productos se
    omiten de la lista (se casan por subcadena en el nombre del producto)."""
    plan_id, semanas = cargar_plan(conn, plan_id)
    if not semanas:
        return Compra(plan_id=None, semanas=0)
    despensa_norm = [d.strip().lower() for d in (despensa or []) if d.strip()]

    raciones_totales: dict[str, float] = {}
    num_comensales = 2
    for datos in semanas.values():
        num_comensales = int(datos.get("num_comensales", num_comensales))
        for rid, x in (datos.get("raciones") or {}).items():
            raciones_totales[rid] = raciones_totales.get(rid, 0.0) + float(x)

    necesidades, sin_producto = _necesidades_gramos(conn, raciones_totales, num_comensales)

    lineas: list[LineaCompra] = []
    for rid, gramos in sorted(necesidades.items(), key=lambda kv: -kv[1]):
        p = conn.execute(
            "SELECT nombre, url_producto, precio_eur, cantidad_base_g_ml, categoria, subcategoria "
            "FROM productos WHERE retailer_product_id = ?",
            (rid,),
        ).fetchone()
        if p is None:
            continue
        # Despensa: si el producto casa con algo que ya tienes en casa, no se compra.
        if despensa_norm and any(d in (p["nombre"] or "").lower() for d in despensa_norm):
            continue
        base = p["cantidad_base_g_ml"]
        unidades = max(1, math.ceil(gramos / base)) if base and base > 0 else 1
        precio = p["precio_eur"]
        lineas.append(
            LineaCompra(
                producto_id=rid,
                nombre=p["nombre"],
                url=p["url_producto"],
                gramos_necesarios=round(gramos, 0),
                formato_g_ml=base,
                unidades=unidades,
                precio_unidad=precio,
                total=round(unidades * precio, 2) if precio is not None else None,
                pasillo=p["subcategoria"] or p["categoria"] or "Otros",
            )
        )
    return Compra(
        plan_id=plan_id, semanas=len(semanas), lineas=lineas, sin_producto=sorted(sin_producto)
    )
