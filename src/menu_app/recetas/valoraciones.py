"""Sistema de valoración personal de recetas (Lote 12).

Clasifica cada receta YA COCINADA con varios baremos de 1-5 estrellas, para
afinar el gusto y la adherencia a la dieta: la valoración alimenta la
palatabilidad del solver (ver optimizacion/palatabilidad.py) y permite
recomendar recetas afines por similitud de ingredientes.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from ..optimizacion.planes import cargar_plan, listar_planes

# Baremos por defecto (el usuario puede pedir ajustar esta lista; ver PLAN_MEJORAS.md).
# clave -> etiqueta mostrada.
BAREMOS: tuple[tuple[str, str], ...] = (
    ("sabor", "Sabor"),
    ("frescura", "Frescura (más de verano ↔ invierno)"),
    ("recepcion_estomacal", "Sentó bien"),
    ("saciedad", "Saciedad"),
    ("facilidad", "Facilidad de preparación"),
    ("se_repetiria", "¿Se repetiría?"),
    ("calidad_precio", "Relación calidad/precio"),
    ("apetecible_frio", "Apetecible en frío/tupper"),
)
_CLAVES_BAREMOS = frozenset(k for k, _ in BAREMOS)


def _semanas_recientes(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """(semanas del plan actual, semanas del plan anterior) para la cola de
    valoración ("esta semana o una semana anterior")."""
    _pid, semanas_actual = cargar_plan(conn)
    planes = listar_planes(conn)
    semanas_anterior: dict = {}
    if len(planes) > 1:
        _pid2, semanas_anterior = cargar_plan(conn, planes[1]["plan_id"])
    return semanas_actual, semanas_anterior


def recetas_para_valorar(conn: sqlite3.Connection) -> list[dict]:
    """Recetas cocinadas esta semana o la semana anterior que AÚN no tienen
    ninguna valoración (#Lote12: "al valorar una, no se vuelve a pedir")."""
    semanas_actual, semanas_anterior = _semanas_recientes(conn)
    ids: set[str] = set()
    titulos: dict[str, str] = {}
    for semanas in (semanas_actual, semanas_anterior):
        for datos in semanas.values():
            info = datos.get("recetas_info", {}) or {}
            for rid in set(datos.get("seleccion_comida", {}) or {}) | set(
                datos.get("seleccion_cena", {}) or {}
            ):
                ids.add(rid)
                titulos[rid] = info.get(rid, {}).get("titulo", rid)
    if not ids:
        return []
    ya_valoradas = {
        r["receta_id"]
        for r in conn.execute(
            f"SELECT DISTINCT receta_id FROM valoraciones WHERE receta_id IN "
            f"({', '.join('?' for _ in ids)})",
            list(ids),
        ).fetchall()
    }
    pendientes = sorted(ids - ya_valoradas)
    return [{"receta_id": rid, "titulo": titulos.get(rid, rid)} for rid in pendientes]


def valoraciones_de(conn: sqlite3.Connection, receta_id: str) -> dict[str, int]:
    """{baremo: estrellas} de una receta (vacio si no se ha valorado nunca)."""
    return {
        r["baremo"]: r["estrellas"]
        for r in conn.execute(
            "SELECT baremo, estrellas FROM valoraciones WHERE receta_id = ?", (receta_id,)
        ).fetchall()
    }


def detalle_de(conn: sqlite3.Connection, receta_id: str) -> dict[str, list[str]]:
    """{'ingrediente': [...], 'metodo': [...]} de la ultima valoracion guardada."""
    salida: dict[str, list[str]] = {"ingrediente": [], "metodo": []}
    for r in conn.execute(
        "SELECT tipo, valor FROM valoracion_detalle WHERE receta_id = ? ORDER BY id", (receta_id,)
    ).fetchall():
        salida.setdefault(r["tipo"], []).append(r["valor"])
    return salida


def guardar_valoracion(
    conn: sqlite3.Connection,
    receta_id: str,
    estrellas_por_baremo: dict[str, int],
    ingredientes_destacados: list[str] | None = None,
    metodo_destacado: list[str] | None = None,
) -> None:
    """Guarda (o re-valora, pisando lo anterior) una receta. Ignora baremos
    desconocidos y estrellas fuera de 1-5 en vez de fallar toda la operación."""
    fecha = datetime.now(UTC).isoformat(timespec="seconds")
    for baremo, estrellas in estrellas_por_baremo.items():
        if baremo not in _CLAVES_BAREMOS:
            continue
        estrellas = int(estrellas)
        if not 1 <= estrellas <= 5:
            continue
        conn.execute(
            "INSERT INTO valoraciones (receta_id, baremo, estrellas, fecha) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(receta_id, baremo) DO UPDATE SET estrellas=excluded.estrellas, "
            "fecha=excluded.fecha",
            (receta_id, baremo, estrellas, fecha),
        )
    conn.execute("DELETE FROM valoracion_detalle WHERE receta_id = ?", (receta_id,))
    for valor in ingredientes_destacados or []:
        valor = valor.strip()
        if valor:
            conn.execute(
                "INSERT INTO valoracion_detalle (receta_id, tipo, valor, fecha) "
                "VALUES (?, 'ingrediente', ?, ?)",
                (receta_id, valor, fecha),
            )
    for valor in metodo_destacado or []:
        valor = valor.strip()
        if valor:
            conn.execute(
                "INSERT INTO valoracion_detalle (receta_id, tipo, valor, fecha) "
                "VALUES (?, 'metodo', ?, ?)",
                (receta_id, valor, fecha),
            )
    conn.commit()


def _ingredientes_por_receta(conn: sqlite3.Connection) -> dict[str, set[str]]:
    mapa: dict[str, set[str]] = {}
    for r in conn.execute(
        "SELECT receta_id, nombre_normalizado FROM receta_ingredientes "
        "WHERE nombre_normalizado IS NOT NULL"
    ).fetchall():
        mapa.setdefault(r["receta_id"], set()).add(r["nombre_normalizado"])
    return mapa


def _recetas_bien_valoradas(conn: sqlite3.Connection, umbral: float = 4.0) -> set[str]:
    """Recetas cuya media de estrellas (todos los baremos) es >= umbral."""
    return {
        r["receta_id"]
        for r in conn.execute(
            "SELECT receta_id, AVG(estrellas) AS media FROM valoraciones "
            "GROUP BY receta_id HAVING media >= ?", (umbral,),
        ).fetchall()
    }


def recetas_afines(conn: sqlite3.Connection, receta_id: str, limite: int = 5) -> list[dict]:
    """Recetas más similares a `receta_id` por solapamiento de ingredientes
    (índice de Jaccard), con un pequeño empujón si esa afín ya está BIEN
    valorada por el usuario (#99: recomendador por afinidad)."""
    mapa = _ingredientes_por_receta(conn)
    base = mapa.get(receta_id, set())
    if not base:
        return []
    bien_valoradas = _recetas_bien_valoradas(conn)
    titulos = {r["id"]: r["titulo"] for r in conn.execute("SELECT id, titulo FROM recetas")}

    puntuadas = []
    for rid, ings in mapa.items():
        if rid == receta_id or not ings:
            continue
        jaccard = len(base & ings) / len(base | ings)
        if jaccard <= 0:
            continue
        # El bonus solo desempata el ORDEN (favorece lo bien valorado); el
        # numero de similitud mostrado es el Jaccard real, sin inflar a >100%.
        puntuadas.append({
            "receta_id": rid, "titulo": titulos.get(rid, rid),
            "similitud": round(jaccard, 3), "_bien_valorada": rid in bien_valoradas,
        })
    puntuadas.sort(key=lambda p: (-p["similitud"], not p["_bien_valorada"]))
    for p in puntuadas:
        del p["_bien_valorada"]
    return puntuadas[:limite]


def listar_recetas_valoradas(conn: sqlite3.Connection, q: str = "") -> list[dict]:
    """Recetas ya valoradas (para re-valorar), con su media de estrellas.
    `q` filtra por título (para el buscador)."""
    sql = (
        "SELECT r.id, r.titulo, AVG(v.estrellas) AS media, COUNT(*) AS n_baremos "
        "FROM valoraciones v JOIN recetas r ON r.id = v.receta_id"
    )
    params: list = []
    if q.strip():
        sql += " WHERE lower(r.titulo) LIKE ?"
        params.append(f"%{q.strip().lower()}%")
    sql += " GROUP BY r.id ORDER BY r.titulo"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]
