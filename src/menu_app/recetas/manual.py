"""Alta MANUAL de recetas (nombre + ingredientes con cantidades) y FAVORITAS.

El usuario puede añadir sus propias recetas indicando el titulo, las raciones y
una linea por ingrediente ("200 g de lentejas", "2 huevos", "1 cebolla"). Se
parsean igual que las recetas scrapeadas (cantidad/unidad -> metrico) para que
entren en el mismo motor: matching con productos, coste, nutricion y menu.

Una receta manual se puede marcar como FAVORITA: el solver la prioriza (bonus en
el objetivo) pero SIN saltarse el coste ni las bandas de nutrientes.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from ..matching.normalizar import clave_ingrediente
from ..optimizacion.batchcooking import es_batchcooking
from ..optimizacion.rol_plato import rol_receta
from .modelos import Receta
from .parseo_ingredientes import IngredienteReceta, parsear_ingrediente
from .repositorio import RecetaRepository

FUENTE_MANUAL = "manual"

# Unidades que ofrece el editor y su conversion a metrico (g o ml, o None=conteo).
UNIDADES = {
    "g": ("g", 1.0), "kg": ("g", 1000.0),
    "ml": ("ml", 1.0), "l": ("ml", 1000.0),
    "ud": (None, None), "cucharada": ("ml", 15.0), "cucharadita": ("ml", 5.0),
}


def _ingrediente_estructurado(nombre: str, cantidad: float, unidad: str) -> IngredienteReceta:
    """Construye el ingrediente desde (nombre, cantidad, unidad) del editor."""
    metrica_u, factor = UNIDADES.get(unidad, (None, None))
    cantidad_metrica = cantidad * factor if factor is not None else None
    return IngredienteReceta(
        texto_original=f"{cantidad:g} {unidad} de {nombre}",
        cantidad=cantidad,
        unidad=unidad,
        nombre=nombre,
        nombre_normalizado=clave_ingrediente(nombre),
        cantidad_metrica=cantidad_metrica,
        unidad_metrica=metrica_u,
    )


def _id_manual(titulo: str) -> tuple[str, str]:
    """Devuelve (id, url) estables para una receta manual, a partir del titulo."""
    base = "manual://" + titulo.strip().lower().replace(" ", "-")
    rid = "man" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:13]
    return rid, base


def guardar_receta(
    conn: sqlite3.Connection,
    titulo: str,
    raciones: int,
    ingredientes: list[dict],
    es_favorita: bool = False,
    es_plato_unico: bool = False,
    es_cena: bool = False,
    receta_id: str | None = None,
) -> str:
    """Crea o EDITA una receta manual con ingredientes estructurados.

    `ingredientes` es una lista de dicts {nombre, cantidad, unidad}. Si se pasa
    `receta_id`, se edita esa (aunque cambie el titulo); si no, el id se deriva
    del titulo. Devuelve el id.
    """
    if not titulo or not titulo.strip():
        raise ValueError("La receta necesita un titulo.")
    if raciones is None or raciones <= 0:
        raise ValueError("Las raciones deben ser un entero positivo.")
    parsed: list[IngredienteReceta] = []
    for ing in ingredientes or []:
        nombre = (ing.get("nombre") or "").strip()
        if not nombre:
            continue
        try:
            cantidad = float(ing.get("cantidad"))
        except (TypeError, ValueError):
            continue
        unidad = ing.get("unidad") or "g"
        parsed.append(_ingrediente_estructurado(nombre, cantidad, unidad))
    if not parsed:
        raise ValueError("La receta necesita al menos un ingrediente con cantidad.")

    rid = receta_id or _id_manual(titulo)[0]
    url = f"manual://{rid}"
    receta = Receta(
        id=rid, url=url, fuente=FUENTE_MANUAL, titulo=titulo.strip(), raciones=raciones,
        tiempo_total_min=None, categoria=None, cocina=None, rating=None, rating_count=None,
        imagen=None, instrucciones=None, ingredientes=parsed,
    )
    fecha = datetime.now(timezone.utc).isoformat(timespec="seconds")
    RecetaRepository(conn).upsert_receta(receta, fecha)
    conn.execute(
        "UPDATE recetas SET es_batchcooking = ?, rol = ?, es_favorita = ?, "
        "es_plato_unico = ?, es_cena = ? WHERE id = ?",
        (
            1 if (es_plato_unico or es_batchcooking(titulo)) else 0,
            "principal",
            1 if es_favorita else 0,
            1 if es_plato_unico else 0,
            1 if es_cena else 0,
            rid,
        ),
    )
    conn.commit()
    return rid


def añadir_receta_manual(
    conn: sqlite3.Connection,
    titulo: str,
    raciones: int,
    ingredientes: list[str],
    es_favorita: bool = False,
    tiempo_total_min: int | None = None,
    categoria: str | None = None,
) -> str:
    """Alta desde lineas de texto libre ("200 g de lentejas"). Compat con el CLI."""
    lineas = [linea for linea in (ingredientes or []) if linea and linea.strip()]
    if not lineas:
        raise ValueError("La receta necesita al menos un ingrediente.")
    estructurados = []
    for linea in lineas:
        p = parsear_ingrediente(linea)
        estructurados.append(
            {"nombre": p.nombre, "cantidad": p.cantidad or 1, "unidad": p.unidad or "g"}
        )
    return guardar_receta(
        conn, titulo=titulo, raciones=raciones, ingredientes=estructurados,
        es_favorita=es_favorita,
    )


def cargar_receta(conn: sqlite3.Connection, receta_id: str) -> dict | None:
    """Datos de una receta para el editor (cabecera + ingredientes)."""
    cab = conn.execute(
        "SELECT id, titulo, raciones, fuente, es_favorita, es_plato_unico, es_cena, "
        "es_batchcooking FROM recetas WHERE id = ?",
        (receta_id,),
    ).fetchone()
    if cab is None:
        return None
    ings = conn.execute(
        "SELECT nombre, cantidad, unidad FROM receta_ingredientes WHERE receta_id = ? ORDER BY orden",
        (receta_id,),
    ).fetchall()
    return {
        "id": cab["id"], "titulo": cab["titulo"], "raciones": cab["raciones"],
        "editable": cab["fuente"] == FUENTE_MANUAL,
        "es_favorita": bool(cab["es_favorita"]),
        "es_plato_unico": bool(cab["es_plato_unico"]),
        "es_cena": bool(cab["es_cena"]),
        "es_batchcooking": bool(cab["es_batchcooking"]),
        "ingredientes": [
            {"nombre": i["nombre"], "cantidad": i["cantidad"], "unidad": i["unidad"] or "g"}
            for i in ings
        ],
    }


def eliminar_receta(conn: sqlite3.Connection, receta_id: str) -> bool:
    cur = conn.execute("DELETE FROM recetas WHERE id = ? AND fuente = ?", (receta_id, FUENTE_MANUAL))
    conn.execute("DELETE FROM receta_ingredientes WHERE receta_id = ?", (receta_id,))
    conn.commit()
    return cur.rowcount > 0


def listar_recetas(conn: sqlite3.Connection, busqueda: str = "", limite: int = 100) -> list[dict]:
    """Lista recetas para el visor (filtra por titulo)."""
    q = "SELECT id, titulo, fuente, es_favorita FROM recetas"
    params: list = []
    if busqueda.strip():
        q += " WHERE lower(titulo) LIKE ?"
        params.append(f"%{busqueda.strip().lower()}%")
    q += " ORDER BY (fuente = 'manual') DESC, titulo LIMIT ?"
    params.append(limite)
    return [
        {"id": r["id"], "titulo": r["titulo"], "fuente": r["fuente"],
         "es_favorita": bool(r["es_favorita"]), "editable": r["fuente"] == FUENTE_MANUAL}
        for r in conn.execute(q, params).fetchall()
    ]


def marcar_favorita(conn: sqlite3.Connection, receta_id: str, favorita: bool = True) -> bool:
    """Marca/desmarca una receta (manual o scrapeada) como favorita. False si no existe."""
    cur = conn.execute(
        "UPDATE recetas SET es_favorita = ? WHERE id = ?", (1 if favorita else 0, receta_id)
    )
    conn.commit()
    return cur.rowcount > 0


def listar_favoritas(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """Devuelve (id, titulo, fuente) de las recetas marcadas como favoritas."""
    return [
        (r["id"], r["titulo"], r["fuente"])
        for r in conn.execute(
            "SELECT id, titulo, fuente FROM recetas WHERE es_favorita = 1 ORDER BY titulo"
        ).fetchall()
    ]
