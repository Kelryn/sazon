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

from ..matching.matcher import IndiceProductos, MatcherLexico
from ..optimizacion.economia_recetas import _gramos_por_piezas
from .planes import cargar_plan

_COLS_PRODUCTO = (
    "nombre, url_producto, precio_eur, cantidad_base_g_ml, categoria, subcategoria, "
    "disponible, en_oferta, precio_oferta"
)


@dataclass
class LineaCompra:
    producto_id: str
    nombre: str
    url: str | None
    gramos_necesarios: float  # g o ml
    formato_g_ml: float | None  # tamaño del paquete (None si desconocido)
    unidades: int
    precio_unidad: float | None  # € por paquete (precio EFECTIVO: de oferta si la hay)
    total: float | None
    pasillo: str = "Otros"  # categoria/pasillo de Alcampo
    # Sustitucion automatica por agotado (#53): el producto elegido en el matching
    # estaba `disponible=0` en el catalogo, asi que se cambio por la mejor alternativa
    # disponible con el mismo texto de busqueda (clave_matching).
    sustituido: bool = False
    nombre_original: str | None = None
    # Oferta (#57): si el producto esta en oferta, el precio/total ya son el de
    # oferta; `ahorro` es lo que te ahorras frente al precio normal.
    en_oferta: bool = False
    ahorro: float = 0.0

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
    # Productos AGOTADOS en el catalogo sin alternativa disponible (#53): no se pudo
    # comprar ni sustituir; se listan para que el usuario decida.
    agotados_sin_sustituto: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(l.total for l in self.lineas if l.total is not None), 2)

    @property
    def ahorro_total(self) -> float:
        """Cuanto ahorras por las ofertas ya aplicadas en el total (#57/#59)."""
        return round(sum(l.ahorro for l in self.lineas), 2)

    @property
    def n_sustituidos(self) -> int:
        return sum(1 for l in self.lineas if l.sustituido)

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


def _indice_disponibles(
    conn: sqlite3.Connection, categoria: str | None = None, subcategoria: str | None = None
) -> IndiceProductos:
    """Indice (para el matcher) de productos APTOS y DISPONIBLES (#53), opcionalmente
    restringido a una categoria/subcategoria (para no sustituir por un producto de
    otro pasillo/familia que solo comparte una palabra: p.ej. cebolla fresca por
    cebolla DESHIDRATADA en especias)."""
    sql = "SELECT retailer_product_id, nombre, marca, precio_por_unidad FROM productos " \
          "WHERE apto_receta = 1 AND (disponible IS NULL OR disponible = 1)"
    params: list = []
    if subcategoria:
        sql += " AND subcategoria = ?"
        params.append(subcategoria)
    elif categoria:
        sql += " AND categoria = ?"
        params.append(categoria)
    cur = conn.execute(sql, params)
    return IndiceProductos.construir(
        [(r["retailer_product_id"], r["nombre"], r["marca"], r["precio_por_unidad"]) for r in cur.fetchall()]
    )


def _clave_matching(conn: sqlite3.Connection, rid: str) -> str | None:
    fila = conn.execute(
        "SELECT clave_matching FROM mapeo_ingr_producto WHERE retailer_product_id = ? LIMIT 1", (rid,)
    ).fetchone()
    return fila["clave_matching"] if fila else None


def lista_compra(
    conn: sqlite3.Connection, plan_id: str | None = None, despensa: list[str] | None = None
) -> Compra:
    """Construye la lista de la compra del plan (todas sus semanas).

    `despensa`: nombres de ingredientes que ya se tienen en casa; sus productos se
    omiten de la lista (se casan por subcadena en el nombre del producto).

    Si un producto esta AGOTADO (`disponible=0`) en el catalogo, se sustituye
    automaticamente por la mejor alternativa disponible con el mismo texto de
    busqueda (#53); si no hay alternativa, se excluye y se reporta en
    `agotados_sin_sustituto`. Los productos en OFERTA usan el precio de oferta y
    suman a `ahorro_total` (#57/#59)."""
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
    agotados_sin_sustituto: list[str] = []
    # Indices lazy, restringidos por categoria (evita sustituir cebolla fresca por
    # cebolla deshidratada de especias: mismo token, pasillo/familia distinta).
    indices_por_subcat: dict[str, IndiceProductos] = {}
    indices_por_cat: dict[str, IndiceProductos] = {}

    for rid, gramos in sorted(necesidades.items(), key=lambda kv: -kv[1]):
        p = conn.execute(f"SELECT {_COLS_PRODUCTO} FROM productos WHERE retailer_product_id = ?", (rid,)).fetchone()
        if p is None:
            continue

        nombre_original = None
        rid_final, p_final = rid, p
        if p["disponible"] == 0:
            clave = _clave_matching(conn, rid)
            sustituto_rid = None
            if clave:
                subcat, cat = p["subcategoria"], p["categoria"]
                if subcat:
                    if subcat not in indices_por_subcat:
                        indices_por_subcat[subcat] = _indice_disponibles(conn, subcategoria=subcat)
                    m = MatcherLexico(indices_por_subcat[subcat]).emparejar(clave)
                    if m:
                        sustituto_rid = m.retailer_product_id
                if sustituto_rid is None and cat:
                    if cat not in indices_por_cat:
                        indices_por_cat[cat] = _indice_disponibles(conn, categoria=cat)
                    m = MatcherLexico(indices_por_cat[cat]).emparejar(clave)
                    if m:
                        sustituto_rid = m.retailer_product_id
                # SIN respaldo global: un producto de otro pasillo que solo comparte
                # una palabra (p.ej. especias vs frescos) suele ser mal sustituto;
                # mejor reportarlo como agotado sin sustituto que comprar algo erroneo.
            if sustituto_rid is None:
                agotados_sin_sustituto.append(p["nombre"])
                continue
            nombre_original = p["nombre"]
            rid_final = sustituto_rid
            p_final = conn.execute(
                f"SELECT {_COLS_PRODUCTO} FROM productos WHERE retailer_product_id = ?", (rid_final,)
            ).fetchone()
            if p_final is None:
                agotados_sin_sustituto.append(nombre_original)
                continue

        # Despensa: si el producto casa con algo que ya tienes en casa, no se compra.
        if despensa_norm and any(d in (p_final["nombre"] or "").lower() for d in despensa_norm):
            continue

        base = p_final["cantidad_base_g_ml"]
        unidades = max(1, math.ceil(gramos / base)) if base and base > 0 else 1
        precio_normal = p_final["precio_eur"]
        en_oferta = bool(p_final["en_oferta"]) and p_final["precio_oferta"] is not None
        precio_efectivo = p_final["precio_oferta"] if en_oferta else precio_normal
        ahorro = (
            round((precio_normal - precio_efectivo) * unidades, 2)
            if en_oferta and precio_normal is not None else 0.0
        )
        lineas.append(
            LineaCompra(
                producto_id=rid_final,
                nombre=p_final["nombre"],
                url=p_final["url_producto"],
                gramos_necesarios=round(gramos, 0),
                formato_g_ml=base,
                unidades=unidades,
                precio_unidad=precio_efectivo,
                total=round(unidades * precio_efectivo, 2) if precio_efectivo is not None else None,
                pasillo=p_final["subcategoria"] or p_final["categoria"] or "Otros",
                sustituido=nombre_original is not None,
                nombre_original=nombre_original,
                en_oferta=en_oferta,
                ahorro=ahorro,
            )
        )
    return Compra(
        plan_id=plan_id,
        semanas=len(semanas),
        lineas=lineas,
        sin_producto=sorted(sin_producto),
        agotados_sin_sustituto=sorted(set(agotados_sin_sustituto)),
    )
