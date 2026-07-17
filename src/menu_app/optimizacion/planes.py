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
from datetime import UTC, datetime

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
            "nutri": res.recetas[rid].nutri,  # Nutri-Score A-E (#2)
            # Sal y azucares por racion, para las alertas por comida (#10).
            "sal": round((res.recetas[rid].nutricion_racion or {}).get("sal", 0.0), 2),
            "azucares": round((res.recetas[rid].nutricion_racion or {}).get("azucares", 0.0), 1),
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
            datetime.now(UTC).isoformat(timespec="seconds"),
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


def _variar_grupos(dias_ord: list[str], asign: dict[str, str | None], grupo) -> None:
    """Reordena in-place las recetas asignadas a `dias_ord` para reducir dias
    consecutivos con el MISMO grupo de alimento (#27). Solo intercambia dias; no
    cambia que recetas hay. Heuristica voraz: si un dia repite grupo con el anterior,
    intercambia con un dia posterior cuyo grupo rompa la repeticion."""
    for i in range(1, len(dias_ord)):
        d, dp = dias_ord[i], dias_ord[i - 1]
        if asign.get(d) and grupo(asign.get(d)) == grupo(asign.get(dp)):
            for j in range(i + 1, len(dias_ord)):
                dj = dias_ord[j]
                if asign.get(dj) and grupo(asign.get(dj)) != grupo(asign.get(dp)):
                    asign[d], asign[dj] = asign[dj], asign[d]
                    break


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
        for dia, rid in zip(grupo_dias, reparto, strict=True):
            comida_por_dia[dia] = rid

    cenas = _distribuir(dict(datos.get("seleccion_cena") or {}), n)
    cena_por_dia = dict(zip(dias, cenas, strict=True))

    # VARIEDAD DE GRUPOS POR DIA (#27): reordena los dias (sin cambiar que recetas
    # entran) para que no se repita el mismo grupo de alimento en dias consecutivos.
    info = datos.get("recetas_info", {}) or {}

    def _grupo(rid):
        return (info.get(rid, {}) or {}).get("grupo", "otro") if rid else None

    _variar_grupos(dias_bc, comida_por_dia, _grupo)
    _variar_grupos(dias_libres, comida_por_dia, _grupo)
    _variar_grupos(dias, cena_por_dia, _grupo)

    # Evita misma receta en comida y cena del mismo dia (intercambio simple).
    for dia in dias:
        if cena_por_dia.get(dia) and cena_por_dia[dia] == comida_por_dia.get(dia):
            for otro in dias:
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


def _historico_semanas(conn: sqlite3.Connection, ventana: int) -> list[set[str]]:
    """Recetas usadas en las `ventana` semanas MAS RECIENTES ya guardadas (de planes
    anteriores), de mas nueva a mas antigua. Base de la ROTACION multi-semana (#28):
    un plan nuevo no repite lo cocinado en las ultimas semanas."""
    if ventana <= 0:
        return []
    filas = conn.execute(
        "SELECT datos FROM planes ORDER BY creado DESC, semana DESC LIMIT ?", (ventana,)
    ).fetchall()
    return [_usadas_en(json.loads(f["datos"])) for f in filas]


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
    # Microsegundos en el nombre: dos generaciones dentro del mismo segundo (dos
    # clics rapidos, o un script) no deben colisionar y pisarse el plan_id
    # (mismo bug ya visto y corregido en backups.py, Lote 8 #80).
    plan_id = datetime.now(UTC).strftime("plan-%Y%m%d-%H%M%S-%f")

    # Rotacion multi-semana (#28): parte del histórico de planes anteriores, para no
    # repetir lo cocinado en las ultimas `ventana` semanas aunque sea un plan nuevo.
    historico = _historico_semanas(conn, ventana)

    resultados: list[ResultadoMenu] = []
    previas: dict[int, dict] = {}
    for semana in range(1, n + 1):
        if ventana:
            # Ventana de `ventana` semanas: primero las de ESTE plan (mas recientes),
            # y si faltan, se rellena con el historico de planes anteriores.
            recientes = [_usadas_en(previas[s]) for s in range(semana - 1, 0, -1)]
            combinado = (recientes + historico)[:ventana]
            excluidas = frozenset().union(*combinado) if combinado else frozenset()
        else:
            excluidas = frozenset()
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


def listar_planes(conn: sqlite3.Connection) -> list[dict]:
    """Historial de planes generados (#109): uno por plan_id, mas recientes primero,
    con nº de semanas y coste total sumado (para elegir cual repetir)."""
    filas = conn.execute(
        "SELECT plan_id, semana, creado, datos FROM planes ORDER BY creado"
    ).fetchall()
    por_plan: dict[str, dict] = {}
    for f in filas:
        p = por_plan.setdefault(
            f["plan_id"], {"plan_id": f["plan_id"], "creado": f["creado"],
                           "n_semanas": 0, "coste_total": 0.0}
        )
        p["creado"] = min(p["creado"], f["creado"])
        p["n_semanas"] += 1
        p["coste_total"] += float(json.loads(f["datos"]).get("coste_total") or 0.0)
    planes = list(por_plan.values())
    for p in planes:
        p["coste_total"] = round(p["coste_total"], 2)
    # Orden por creado Y plan_id: 'creado' solo tiene resolucion de segundos
    # (guardar_semana), asi que dos planes generados en el mismo segundo empatan;
    # el plan_id (con microsegundos, ver generar_plan) desempata de forma estable.
    planes.sort(key=lambda p: (p["creado"], p["plan_id"]), reverse=True)
    return planes


def repetir_semana(
    conn: sqlite3.Connection,
    origen_plan_id: str, origen_semana: int,
    destino_plan_id: str, destino_semana: int,
) -> bool:
    """Reutiliza una semana YA GENERADA de un plan anterior como una semana nueva
    de otro plan (#109: "repetir semana pasada"). Devuelve False si el origen no
    existe. No vuelve a resolver el MILP: copia la semana tal cual se sirvió."""
    fila = conn.execute(
        "SELECT datos FROM planes WHERE plan_id = ? AND semana = ?",
        (origen_plan_id, origen_semana),
    ).fetchone()
    if fila is None:
        return False
    conn.execute(
        "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(plan_id, semana) DO UPDATE SET datos = excluded.datos, creado = excluded.creado",
        (destino_plan_id, destino_semana, datetime.now(UTC).isoformat(timespec="seconds"), fila["datos"]),
    )
    conn.commit()
    return True


# Version del formato de exportacion (#114): permite detectar ficheros de una
# version futura incompatible si el formato cambia mas adelante.
_FORMATO_EXPORTACION = 1


def exportar_plan_json(conn: sqlite3.Connection, plan_id: str) -> bytes | None:
    """Serializa un plan completo (todas sus semanas) para compartirlo como un
    fichero .json (#114). None si el plan no existe."""
    _pid, semanas = cargar_plan(conn, plan_id)
    if not semanas:
        return None
    return json.dumps(
        {"formato": _FORMATO_EXPORTACION, "plan_id_original": plan_id, "semanas": semanas},
        ensure_ascii=False, indent=2,
    ).encode("utf-8")


def importar_plan_json(conn: sqlite3.Connection, contenido: bytes) -> str | None:
    """Importa un plan exportado con `exportar_plan_json` como un plan NUEVO
    (#114: compartir menús entre usuarios/instalaciones). Devuelve el plan_id
    nuevo, o None si el fichero no tiene el formato esperado."""
    try:
        datos = json.loads(contenido.decode("utf-8"))
        semanas = datos["semanas"]
        if not semanas:
            return None
    except (ValueError, KeyError, UnicodeDecodeError):
        return None
    plan_id = datetime.now(UTC).strftime("plan-importado-%Y%m%d-%H%M%S-%f")
    ahora = datetime.now(UTC).isoformat(timespec="seconds")
    for semana, contenido_semana in semanas.items():
        conn.execute(
            "INSERT INTO planes (plan_id, semana, creado, datos) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(plan_id, semana) DO UPDATE SET datos = excluded.datos, creado = excluded.creado",
            (plan_id, int(semana), ahora, json.dumps(contenido_semana, ensure_ascii=False)),
        )
    conn.commit()
    return plan_id
