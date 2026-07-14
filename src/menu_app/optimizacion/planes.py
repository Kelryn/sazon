"""Planes de menu MULTI-SEMANA con persistencia.

Genera N semanas seguidas cumpliendo la regla de repeticion del usuario
(`dias_repeticion`: cada cuantos dias puede volver a comerse una receta):
- Dentro de una semana el tope de usos sale de esa regla (>=7 dias -> 1 vez).
- Entre semanas, las recetas usadas en las `semanas_exclusion` semanas anteriores
  quedan vetadas (dias_repeticion=14 -> veta la semana previa, etc.).

Cada semana generada se guarda en la tabla `planes` (JSON) para poder navegar
entre semanas en la UI, regenerar alternativas y montar la lista de la compra
del plan completo.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .servicio import ResultadoMenu, generar_menu, por_que_receta, semanas_exclusion


def _serializar(res: ResultadoMenu, batchcooking: bool = False) -> str:
    m = res.menu
    usadas = set(m.seleccion_comida or {}) | set(m.seleccion_cena or {})
    recetas_info = {
        rid: {
            "titulo": res.recetas[rid].titulo,
            "coste_racion": res.recetas[rid].coste_racion,
            "es_favorita": res.recetas[rid].es_favorita,
            "es_batchcooking": res.recetas[rid].es_batchcooking,
            "grupo": res.recetas[rid].grupo,
            "por_que": por_que_receta(res.recetas[rid]),  # explicabilidad (#35)
        }
        for rid in usadas
        if rid in res.recetas
    }
    return json.dumps(
        {
            "factible": m.factible,
            "motivo": m.motivo,
            "coste_total": m.coste_total,
            "nutricion_total": m.nutricion_total,
            "deficit_blando": m.deficit_blando or {},
            "seleccion_comida": m.seleccion_comida or {},
            "seleccion_cena": m.seleccion_cena or {},
            "seleccion_comida_bc": m.seleccion_comida_bc or {},
            "raciones": m.raciones or {},
            "recetas_info": recetas_info,
            "dias_bc": res.dias_bc,
            "num_comensales": res.num_comensales,
            "dias": res.dias,
            "batchcooking_forzado": batchcooking,
        },
        ensure_ascii=False,
    )


def guardar_semana(
    conn: sqlite3.Connection, plan_id: str, semana: int, res: ResultadoMenu,
    batchcooking: bool = False,
) -> None:
    conn.execute(
        "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(plan_id, semana) DO UPDATE SET datos = excluded.datos, creado = excluded.creado",
        (
            plan_id, semana,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            _serializar(res, batchcooking),
        ),
    )
    conn.commit()


def cargar_plan(conn: sqlite3.Connection, plan_id: str | None = None) -> tuple[str | None, dict[int, dict]]:
    """Devuelve (plan_id, {semana: datos}) del plan pedido o del mas reciente."""
    if plan_id is None:
        fila = conn.execute(
            "SELECT plan_id FROM planes ORDER BY creado DESC, plan_id DESC LIMIT 1"
        ).fetchone()
        if fila is None:
            return None, {}
        plan_id = fila["plan_id"]
    semanas = {
        int(f["semana"]): json.loads(f["datos"])
        for f in conn.execute(
            "SELECT semana, datos FROM planes WHERE plan_id = ? ORDER BY semana", (plan_id,)
        ).fetchall()
    }
    return plan_id, semanas


def _distribuir(cuentas: dict[str, int], n: int) -> list[str | None]:
    """Reparte `cuentas` (receta -> nº de veces) en n huecos SEPARANDO las
    repeticiones: cada receta repetida se coloca en posiciones equiespaciadas
    (una receta 2 veces en 7 dias cae en los dias ~1 y ~4, no en dias seguidos)."""
    huecos: list[str | None] = [None] * n
    for rid, k in sorted(cuentas.items(), key=lambda kv: (-kv[1], kv[0])):
        k = int(k)
        for j in range(k):
            # Reparte las k apariciones lo MAS separadas posible dentro de los n
            # dias: en los extremos y equiespaciadas (k=2 en 5 -> dias 0 y 4).
            ideal = round((n - 1) / 2) if k == 1 else round(j * (n - 1) / (k - 1))
            libres = [p for p in range(n) if huecos[p] is None]
            if not libres:
                break
            mejor = min(libres, key=lambda p: (abs(p - ideal), p))
            huecos[mejor] = rid
    return huecos


def asignar_dias(datos: dict, dias_semana: list[str]) -> list[tuple[str, str | None, str | None, bool]]:
    """Asigna las selecciones guardadas a dias concretos: [(dia, comida, cena, es_bc)].

    Las comidas de dias batchcooking se reparten entre esos dias; las libres entre
    el resto; las cenas entre todos. Las recetas repetidas quedan lo mas separadas
    posible y nunca se repite la misma receta en comida y cena del MISMO dia si
    hay alternativa.
    """
    n = int(datos.get("dias", 7))
    dias = dias_semana[:n]
    dias_bc = [d for d in dias if d in (datos.get("dias_bc") or [])]
    dias_libres = [d for d in dias if d not in dias_bc]

    bc = dict(datos.get("seleccion_comida_bc") or {})
    libres = {
        rid: v - bc.get(rid, 0) for rid, v in (datos.get("seleccion_comida") or {}).items()
    }
    libres = {rid: v for rid, v in libres.items() if v > 0}

    comida_por_dia: dict[str, str | None] = {}
    for grupo_dias, cuentas in ((dias_bc, bc), (dias_libres, libres)):
        reparto = _distribuir(cuentas, len(grupo_dias))
        for dia, rid in zip(grupo_dias, reparto):
            comida_por_dia[dia] = rid

    cenas = _distribuir(dict(datos.get("seleccion_cena") or {}), n)
    cena_por_dia = dict(zip(dias, cenas))

    # Evita misma receta en comida y cena del mismo dia (intercambio simple).
    for i, dia in enumerate(dias):
        if cena_por_dia.get(dia) and cena_por_dia[dia] == comida_por_dia.get(dia):
            for j, otro in enumerate(dias):
                if (
                    otro != dia
                    and cena_por_dia.get(otro) != comida_por_dia.get(dia)
                    and cena_por_dia.get(dia) != comida_por_dia.get(otro)
                ):
                    cena_por_dia[dia], cena_por_dia[otro] = cena_por_dia[otro], cena_por_dia[dia]
                    break

    return [(d, comida_por_dia.get(d), cena_por_dia.get(d), d in dias_bc) for d in dias]


def _usadas_en(datos: dict) -> set[str]:
    return set(datos.get("seleccion_comida", {})) | set(datos.get("seleccion_cena", {}))


def _excluidas_para_semana(semanas: dict[int, dict], semana: int, ventana: int) -> frozenset[str]:
    """Recetas vetadas para `semana` por haberse usado en las `ventana` previas."""
    vetadas: set[str] = set()
    for s in range(max(1, semana - ventana), semana):
        if s in semanas:
            vetadas |= _usadas_en(semanas[s])
    return frozenset(vetadas)


def generar_plan(
    conn: sqlite3.Connection,
    cfg: dict,
    n_semanas: int | None = None,
    batchcooking: bool = False,
) -> tuple[str, list[ResultadoMenu]]:
    """Genera y guarda un plan completo de N semanas. Devuelve (plan_id, semanas)."""
    n = int(n_semanas if n_semanas is not None else cfg.get("semanas_plan", 1))
    n = max(1, n)
    ventana = semanas_exclusion(cfg)
    plan_id = datetime.now(timezone.utc).strftime("plan-%Y%m%d-%H%M%S")

    resultados: list[ResultadoMenu] = []
    previas: dict[int, dict] = {}
    for semana in range(1, n + 1):
        excluidas = _excluidas_para_semana(previas, semana, ventana) if ventana else frozenset()
        res = generar_menu(conn, cfg, batchcooking=batchcooking, excluidas=excluidas)
        resultados.append(res)
        guardar_semana(conn, plan_id, semana, res, batchcooking=batchcooking)
        previas[semana] = json.loads(_serializar(res))
        if not res.menu.factible:
            break  # sin recetas suficientes para mas semanas distintas: se informa
    return plan_id, resultados


def regenerar_semana(
    conn: sqlite3.Connection,
    cfg: dict,
    plan_id: str,
    semana: int,
    corte: set[str] | None = None,
    excluir: str | None = None,
    batchcooking: bool = False,
) -> ResultadoMenu:
    """Rehace UNA semana del plan guardado.

    - `corte`: ids del menu actual -> genera la ALTERNATIVA (segundo mejor).
    - `excluir`: id de una receta concreta -> la cambia por la siguiente mejor.
    Mantiene los vetos por repeticion respecto a las semanas anteriores del plan.
    """
    _pid, semanas = cargar_plan(conn, plan_id)
    ventana = semanas_exclusion(cfg)
    excluidas = set(_excluidas_para_semana(semanas, semana, ventana)) if ventana else set()
    if excluir:
        excluidas.add(excluir)
    res = generar_menu(
        conn, cfg, batchcooking=batchcooking,
        excluidas=frozenset(excluidas), corte=corte,
    )
    guardar_semana(conn, plan_id, semana, res, batchcooking=batchcooking)
    return res
