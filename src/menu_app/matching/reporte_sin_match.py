"""Informe (.md) de ingredientes que NO han casado con ningun producto de Alcampo.

Sirve para revisar a mano por que no casan y decidir si (a) falta un sinonimo en
el glosario, (b) el alimento no lo vende Alcampo, o (c) es un no-ingrediente
(agua, cantidades sueltas, alcohol excluido, error de parseo).

Categoriza cada ingrediente sin match y, cuando hay un candidato fuzzy razonable,
lo muestra para facilitar el triaje.
"""

from __future__ import annotations

import sqlite3

from rapidfuzz import fuzz, process

from .matcher import IndiceProductos, MatcherLexico
from .normalizar import clave_ingrediente
from .repositorio import MatchingRepository

# Pistas de que el "ingrediente" no es realmente comprable en el super.
_ALCOHOL = ("vino", "cerveza", "ron", "brandy", "vodka", "whisky", "licor", "cava",
            "champan", "sidra", "vermut", "coñac", "conac", "ginebra", "tequila",
            "soda", "chicha")
_NO_ALIMENTO = ("agua", "centimetros cubicos", "para acompanar", "para decorar",
                "al gusto", "cantidad", "suficiente", "hielo")
# Ingredientes tipicos de cocina internacional que Alcampo no suele vender.
_EXOTICO = ("aji panca", "aji amarillo", "aji mirasol", "huacatay", "epazote",
            "olluco", "mondongo", "chicha de jora", "nopal", "chayote", "agraz",
            "arrachera", "wantan", "chorizo amazonico", "ajinomoto", "maracuya",
            "tapioca", "mejorana", "chile guajillo", "chile ancho", "chile morita",
            "chile pasilla", "kimchi", "miso", "mirin", "dashi", "galanga",
            "lemongrass", "hierbaluisa", "quinua", "kale")


def _categoria(ing: str) -> str:
    t = ing.lower()
    if any(a in t for a in _ALCOHOL):
        return "Alcohol / bebida (excluido del catálogo apto)"
    if any(a in t for a in _NO_ALIMENTO):
        return "No es un alimento comprable (agua, cantidades, adornos)"
    if any(a in t for a in _EXOTICO):
        return "Probablemente no lo vende Alcampo (cocina internacional)"
    return "Revisar: podría faltar sinónimo o producto"


def generar_reporte(conn: sqlite3.Connection) -> str:
    """Devuelve el contenido markdown del informe de ingredientes sin match."""
    indice = IndiceProductos.construir(MatchingRepository(conn).productos_aptos())
    matcher = MatcherLexico(indice)

    filas = conn.execute(
        """SELECT m.ingrediente_norm AS ing, COUNT(ri.id) AS usos
           FROM mapeo_ingr_producto m
           JOIN receta_ingredientes ri ON ri.nombre_normalizado = m.ingrediente_norm
           WHERE m.retailer_product_id IS NULL
           GROUP BY m.ingrediente_norm ORDER BY usos DESC, ing"""
    ).fetchall()

    # Recetas de origen por ingrediente (consulta aparte: los titulos llevan comas
    # y group_concat las usaria de separador, rompiendo el resultado).
    recetas_por_ing: dict[str, list[str]] = {}
    for r in conn.execute(
        """SELECT DISTINCT ri.nombre_normalizado AS ing, rc.titulo AS titulo
           FROM mapeo_ingr_producto m
           JOIN receta_ingredientes ri ON ri.nombre_normalizado = m.ingrediente_norm
           JOIN recetas rc ON rc.id = ri.receta_id
           WHERE m.retailer_product_id IS NULL"""
    ).fetchall():
        recetas_por_ing.setdefault(r["ing"], []).append(r["titulo"])

    total_ing = conn.execute(
        "SELECT COUNT(DISTINCT ingrediente_norm) FROM mapeo_ingr_producto"
    ).fetchone()[0]
    casados = total_ing - len(filas)
    pct = 100 * casados / total_ing if total_ing else 0

    # Metrica PONDERADA POR USO (la que de verdad importa para los menus): que
    # fraccion de las APARICIONES de ingrediente en recetas tienen producto.
    usos_tot = conn.execute("SELECT COUNT(*) FROM receta_ingredientes").fetchone()[0]
    usos_cas = conn.execute(
        "SELECT COUNT(*) FROM receta_ingredientes ri JOIN mapeo_ingr_producto m "
        "ON m.ingrediente_norm = ri.nombre_normalizado WHERE m.retailer_product_id IS NOT NULL"
    ).fetchone()[0]
    pct_uso = 100 * usos_cas / usos_tot if usos_tot else 0

    # Agrupa por categoria y calcula el mejor candidato fuzzy (para triaje).
    grupos: dict[str, list[tuple]] = {}
    for f in filas:
        ing = f["ing"]
        clave = clave_ingrediente(ing)
        mejor = ""
        if clave and indice.textos:
            cand = process.extractOne(clave, indice.textos, scorer=fuzz.token_set_ratio)
            if cand:
                mejor = f"{indice.nombres[cand[2]][:45]} ({cand[1]:.0f})"
        grupos.setdefault(_categoria(ing), []).append(
            (f["usos"], ing, mejor, _recetas_origen(recetas_por_ing.get(ing, [])))
        )

    lineas = [
        "# Ingredientes sin correspondencia en Alcampo",
        "",
        f"- **Cobertura ponderada por uso: {pct_uso:.1f}%** "
        f"({usos_cas}/{usos_tot} apariciones de ingrediente en recetas tienen producto). "
        "Es la métrica relevante para los menús.",
        f"- Ingredientes *distintos* totales: **{total_ing}** · casados "
        f"**{casados} ({pct:.0f}%)** · sin casar **{len(filas)} ({100 - pct:.0f}%)**.",
        "- El % de distintos es más bajo porque lo lastran cientos de ingredientes de un "
        "solo uso propios de cocina internacional (ajíes peruanos, hierbas exóticas…) que "
        "Alcampo no vende.",
        "",
        "El «mejor candidato» es la sugerencia fuzzy más cercana (0-100) solo para "
        "ayudar a decidir; un número bajo suele indicar que Alcampo no lo vende.",
        "",
    ]
    orden = [
        "Revisar: podría faltar sinónimo o producto",
        "Probablemente no lo vende Alcampo (cocina internacional)",
        "Alcohol / bebida (excluido del catálogo apto)",
        "No es un alimento comprable (agua, cantidades, adornos)",
    ]
    for cat in orden:
        items = grupos.get(cat)
        if not items:
            continue
        lineas.append(f"## {cat} ({len(items)})")
        lineas.append("")
        lineas.append("| Usos | Ingrediente | Receta(s) de origen | Mejor candidato (score) |")
        lineas.append("|---:|---|---|---|")
        for usos, ing, mejor, recetas in items:
            lineas.append(f"| {usos} | {ing} | {recetas} | {mejor} |")
        lineas.append("")
    return "\n".join(lineas)


def _recetas_origen(titulos: list[str], maximo: int = 4) -> str:
    """Lista de titulos de receta -> texto corto y legible para la tabla."""
    vistos: list[str] = []
    for titulo in titulos:
        t = (titulo or "").strip()
        if t.lower().startswith("receta de "):
            t = t[len("receta de "):]
        t = t.replace("|", "/")  # no romper la tabla markdown
        if t and t not in vistos:
            vistos.append(t)
    if len(vistos) > maximo:
        return "; ".join(vistos[:maximo]) + f" … (+{len(vistos) - maximo})"
    return "; ".join(vistos)
