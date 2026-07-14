"""Optimizador MILP del menu semanal (PuLP) — el "problema de la dieta".

Elige cuantas veces entra cada receta en la semana para MINIMIZAR el coste,
sujeto a:
  - cubrir el nº de comidas de la semana,
  - las BANDAS de nutrientes (ver nutrientes.py): proteina y fibra con suelo,
    grasa saturada / azucares / sal con techo, energia e hidratos por banda.
    Aqui es donde el suelo de proteina impide que el solver la elimine por ser
    el alimento mas caro (que es justo lo que se queria evitar),
  - un tope de repeticiones por receta.
La palatabilidad (ratings) entra como bonus en el objetivo: a igual coste,
prefiere recetas mejor valoradas.
"""

from __future__ import annotations

from dataclasses import dataclass

import pulp

from .nutrientes import BandaNutriente


@dataclass
class RecetaOpt:
    id: str
    titulo: str
    coste_racion: float  # €/racion
    nutricion_racion: dict[str, float]  # por racion, claves = nutriente
    palatabilidad: float = 0.0  # 0..1 (media bayesiana de ratings, normalizada)
    es_espanola: bool = True  # receta de fuente española (para el minimo de cocina local)
    es_batchcooking: bool = False  # apta para cocinar en tanda (catalogo exclusivo)
    aptitud_cena: float = 0.0  # 0..1: cuanto de ligera+sencilla es (para las cenas)
    familia: str = ""  # tipo de plato (p.ej. "salmorejo") para penalizar monotonia
    grupo: str = "otro"  # grupo de alimento del ingrediente principal (AESAN)
    es_favorita: bool = False  # marcada por el usuario: se prioriza (bonus en objetivo)
    productos: frozenset[str] = frozenset()  # productos Alcampo que usa (racionalizar compra)
    salud: float = 0.0  # -1..1: cuanto de sana es (grupos buenos - grasa sat/azucar/sal)
    tiempo_min: int | None = None  # tiempo de preparacion (min), para el "por que" (#35)
    productos_gramos: dict[str, float] = None  # gramos POR RACION de cada producto (#23)
    nutri: str = ""  # letra Nutri-Score A-E (#2), "" si no se pudo calcular
    procesado: float = 0.0  # fraccion 0..1 de gramos ultraprocesados (NOVA 4) (#3)


# Nutrientes cuyo SUELO se trata como blando (se penaliza el deficit en vez de
# bloquear el menu). La fibra va aqui porque Alcampo casi nunca la declara en la
# etiqueta (dato opcional en la UE) -> exigirla como suelo duro haria el problema
# infactible por falta de DATO, no por falta de fibra real. Se puede quitar cuando
# mejore la cobertura del dato.
SUELOS_BLANDOS_DEFECTO = frozenset({"fibra"})

# Penalizacion por gramo de deficit de un suelo blando. Muy alta frente al coste
# (euros) para que el solver acerque el nutriente a su objetivo siempre que pueda.
_PESO_DEFICIT = 1000.0


@dataclass
class MenuOptimizado:
    seleccion: dict[str, int]  # receta_id -> nº de comidas
    coste_total: float
    nutricion_total: dict[str, float]
    factible: bool
    motivo: str = ""
    deficit_blando: dict[str, float] = None  # nutriente -> gramos por debajo del suelo
    seleccion_comida: dict[str, int] = None  # receta_id -> nº de comidas (mediodia)
    seleccion_cena: dict[str, int] = None  # receta_id -> nº de cenas
    # Subconjunto de seleccion_comida reservado a los DIAS BATCHCOOKING (dia
    # laboral: plato unico en tanda). El resto de comidas va a los dias libres.
    seleccion_comida_bc: dict[str, int] = None
    # Raciones POR PERSONA realmente servidas de cada receta en el total del menu
    # (fraccionables: 0.8, 1.25...). Coste y nutricion salen de aqui.
    raciones: dict[str, float] = None
    raciones_comida: dict[str, float] = None  # solo las servidas en la comida
    raciones_cena: dict[str, float] = None    # solo las servidas en la cena


def optimizar(
    recetas: list[RecetaOpt],
    bandas: list[BandaNutriente],
    n_comidas: int,
    num_comensales: int,
    max_repeticiones: int = 3,
    peso_palatabilidad: float = 0.0,
    frac_espanola_min: float = 0.5,
    solo_batchcooking: bool = False,
    suelos_blandos: frozenset[str] = SUELOS_BLANDOS_DEFECTO,
) -> MenuOptimizado:
    """Devuelve el menu de minimo coste que cumple las bandas, o factible=False.

    Si solo_batchcooking=True, el menu se elige exclusivamente entre las recetas
    aptas para batchcooking (dia laboral con cocinado en tanda).

    Los nutrientes en `suelos_blandos` no bloquean el menu: su suelo se persigue
    penalizando el deficit en el objetivo (util cuando el DATO del nutriente esta
    poco cubierto, p.ej. la fibra en las etiquetas de Alcampo).
    """
    if solo_batchcooking:
        recetas = [r for r in recetas if r.es_batchcooking]
    if not recetas:
        return MenuOptimizado({}, 0.0, {}, False, "sin recetas")

    prob = pulp.LpProblem("menu_semanal", pulp.LpMinimize)
    # u[r] = nº de comidas de la semana que usan la receta r (cada una para num_comensales).
    u = {
        r.id: pulp.LpVariable(f"u_{i}", lowBound=0, upBound=max_repeticiones, cat="Integer")
        for i, r in enumerate(recetas)
    }
    por_id = {r.id: r for r in recetas}

    # Objetivo: coste (para num_comensales) menos un bonus por palatabilidad.
    objetivo = pulp.lpSum(
        u[r.id] * (r.coste_racion * num_comensales - peso_palatabilidad * r.palatabilidad)
        for r in recetas
    )

    # Cubrir exactamente las comidas de la semana.
    prob += pulp.lpSum(u.values()) == n_comidas

    # Al menos una fraccion del menu debe ser de cocina española.
    if frac_espanola_min > 0:
        prob += (
            pulp.lpSum(u[r.id] for r in recetas if r.es_espanola)
            >= frac_espanola_min * n_comidas,
            "min_espanolas",
        )

    # Bandas de nutrientes (total semanal para num_comensales).
    deficit_vars: dict[str, pulp.LpVariable] = {}
    for banda in bandas:
        total = pulp.lpSum(
            u[r.id] * r.nutricion_racion.get(banda.nutriente, 0.0) * num_comensales
            for r in recetas
        )
        if banda.minimo is not None:
            if banda.nutriente in suelos_blandos:
                # Suelo blando: total + deficit >= minimo, y se penaliza el deficit.
                s = pulp.LpVariable(f"deficit_{banda.nutriente}", lowBound=0)
                deficit_vars[banda.nutriente] = s
                prob += total + s >= banda.minimo, f"minblando_{banda.nutriente}"
                objetivo += _PESO_DEFICIT * s
            else:
                prob += total >= banda.minimo, f"min_{banda.nutriente}"
        if banda.maximo is not None:
            prob += total <= banda.maximo, f"max_{banda.nutriente}"

    prob += objetivo
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    estado = pulp.LpStatus[prob.status]
    if estado != "Optimal":
        return MenuOptimizado({}, 0.0, {}, False, f"sin solucion factible ({estado})")

    seleccion = {rid: int(round(v.value())) for rid, v in u.items() if v.value() and v.value() > 0.5}
    coste = sum(por_id[rid].coste_racion * num_comensales * n for rid, n in seleccion.items())
    nutricion: dict[str, float] = {}
    for rid, n in seleccion.items():
        for nut, val in por_id[rid].nutricion_racion.items():
            nutricion[nut] = nutricion.get(nut, 0.0) + val * num_comensales * n

    deficit = {
        nut: round(s.value(), 1)
        for nut, s in deficit_vars.items()
        if s.value() and s.value() > 0.5
    }
    return MenuOptimizado(
        seleccion=seleccion,
        coste_total=round(coste, 2),
        nutricion_total={k: round(v, 1) for k, v in nutricion.items()},
        factible=True,
        deficit_blando=deficit,
    )


def optimizar_comida_cena(
    recetas: list[RecetaOpt],
    bandas: list[BandaNutriente],
    dias: int,
    num_comensales: int,
    max_repeticiones: int = 3,
    peso_palatabilidad: float = 0.0,
    frac_espanola_min: float = 0.5,
    solo_batchcooking_comida: bool = False,
    dias_batchcooking: int = 0,
    peso_cena_ligera_simple: float = 3.0,
    peso_favorita: float = 4.0,
    peso_variedad: float = 3.0,
    peso_reutilizacion: float = 0.0,
    peso_salud: float = 0.0,
    peso_ultraprocesado: float = 0.0,
    peso_sobra: float = 0.0,
    productos_formato: dict[str, float] | None = None,
    max_familia_libre: int = 2,
    min_por_grupo: dict[str, int] | None = None,
    max_por_grupo: dict[str, int] | None = None,
    bandas_comida: list[BandaNutriente] | None = None,
    bandas_cena: list[BandaNutriente] | None = None,
    racion_frac_min: float = 0.75,
    racion_frac_max: float = 1.25,
    excluidas: frozenset[str] = frozenset(),
    corte: set[str] | None = None,
    min_diferencias: int = 2,
    suelos_blandos: frozenset[str] = SUELOS_BLANDOS_DEFECTO,
    presupuesto_max: float | None = None,
    tiempo_max_solver: float | None = None,
    gap_solver: float | None = None,
) -> MenuOptimizado:
    """Menu con dos franjas: COMIDA (mediodia) y CENA, `dias` de cada una.

    - Los minimos de nutrientes se cumplen sobre el TOTAL del dia (comida+cena);
      las bandas ya vienen escaladas a la fraccion que cubren estas comidas.
    - Las CENAS nunca son batchcooking y se prefieren ligeras y sencillas
      (bonus `peso_cena_ligera_simple` * aptitud_cena en el objetivo).
    - Las FAVORITAS se priorizan (bonus `peso_favorita`) sin saltarse coste ni
      bandas de nutrientes.
    - `dias_batchcooking` (0..dias) marca cuantos dias son LABORALES con cocinado
      en tanda: la COMIDA de esos dias sale solo del catalogo batchcooking (plato
      unico transportable); las de los demas dias, del catalogo completo. Las
      cenas nunca son batchcooking. `solo_batchcooking_comida=True` equivale a
      dias_batchcooking=dias (compatibilidad).
    - Las RACIONES SON FRACCIONABLES: en cada comida se sirve entre
      racion_frac_min y racion_frac_max raciones por persona (el solver elige el
      punto que cuadra la energia/nutrientes sin desperdiciar).
    - `excluidas`: ids que no pueden entrar (cambiar una receta por la siguiente
      mejor). `corte`: ids del menu anterior; se exige que al menos
      `min_diferencias` huecos usen recetas distintas (menu ALTERNATIVO).
    """
    recetas = [r for r in recetas if r.id not in excluidas]
    if not recetas:
        return MenuOptimizado({}, 0.0, {}, False, "sin recetas")

    n_bc = dias if solo_batchcooking_comida else max(0, min(int(dias_batchcooking), dias))
    pool_bc = [r for r in recetas if r.es_batchcooking]
    pool_libre = recetas
    pool_cena = recetas  # las cenas siempre del catalogo completo de principales
    if n_bc > 0 and not pool_bc:
        return MenuOptimizado({}, 0.0, {}, False, "sin recetas de comida batchcooking")

    prob = pulp.LpProblem("menu_comida_cena", pulp.LpMinimize)
    por_id = {r.id: r for r in recetas}
    # cb: comidas de dias batchcooking (solo catalogo en tanda); cl: comidas de
    # dias libres (catalogo completo); d: cenas. Para cada grupo, u = nº de
    # comidas (entero) y x = raciones por persona servidas (continuo, fraccionable),
    # ligadas por  racion_frac_min*u <= x <= racion_frac_max*u.
    cb = {r.id: pulp.LpVariable(f"cb_{i}", 0, max_repeticiones, cat="Integer") for i, r in enumerate(pool_bc)}
    cl = {r.id: pulp.LpVariable(f"cl_{i}", 0, max_repeticiones, cat="Integer") for i, r in enumerate(pool_libre)}
    d = {r.id: pulp.LpVariable(f"d_{i}", 0, max_repeticiones, cat="Integer") for i, r in enumerate(pool_cena)}
    xb = {rid: pulp.LpVariable(f"xb_{i}", lowBound=0) for i, rid in enumerate(cb)}
    xl = {rid: pulp.LpVariable(f"xl_{i}", lowBound=0) for i, rid in enumerate(cl)}
    xd = {rid: pulp.LpVariable(f"xd_{i}", lowBound=0) for i, rid in enumerate(d)}
    grupos = ((cb, xb, pool_bc), (cl, xl, pool_libre), (d, xd, pool_cena))

    for u_vars, x_vars, _pool in grupos:
        for rid in u_vars:
            prob += x_vars[rid] >= racion_frac_min * u_vars[rid]
            prob += x_vars[rid] <= racion_frac_max * u_vars[rid]

    def nut_total(nutriente: str):
        return pulp.lpSum(
            x_vars[r.id] * por_id[r.id].nutricion_racion.get(nutriente, 0.0) * num_comensales
            for _u, x_vars, pool in grupos
            for r in pool
        )

    # Objetivo: coste (por racion realmente servida, x) - palatabilidad - bonus
    # favorita (por comida, u) - bonus ligera/sencilla (solo cena). Las favoritas
    # restan coste "virtual" para entrar antes, pero siguen atadas a las bandas.
    def _bonus_comida(r: RecetaOpt) -> float:
        bonus = peso_palatabilidad * r.palatabilidad + peso_salud * r.salud
        bonus -= peso_ultraprocesado * r.procesado  # penaliza ultraprocesados (#3)
        if r.es_favorita:
            bonus += peso_favorita
        return bonus

    objetivo = (
        pulp.lpSum(
            xb[r.id] * r.coste_racion * num_comensales - cb[r.id] * _bonus_comida(r)
            for r in pool_bc
        )
        + pulp.lpSum(
            xl[r.id] * r.coste_racion * num_comensales - cl[r.id] * _bonus_comida(r)
            for r in pool_libre
        )
        + pulp.lpSum(
            xd[r.id] * r.coste_racion * num_comensales
            - d[r.id] * (_bonus_comida(r) + peso_cena_ligera_simple * r.aptitud_cena)
            for r in pool_cena
        )
    )

    prob += pulp.lpSum(cb.values()) == n_bc, "num_comidas_bc"
    prob += pulp.lpSum(cl.values()) == dias - n_bc, "num_comidas_libres"
    prob += pulp.lpSum(d.values()) == dias, "num_cenas"

    # Tope de repeticiones por receta sobre el total de la semana (todas las franjas).
    for rid in set(cb) | set(cl) | set(d):
        partes = [v[rid] for v in (cb, cl, d) if rid in v]
        if len(partes) > 1:
            prob += pulp.lpSum(partes) <= max_repeticiones, f"rep_{rid}"

    # >=50% de cocina española sobre las 2*dias comidas.
    if frac_espanola_min > 0:
        esp = pulp.lpSum(
            u_vars[r.id] for u_vars, _x, pool in grupos for r in pool if r.es_espanola
        )
        prob += esp >= frac_espanola_min * 2 * dias, "min_espanolas"

    # GRUPOS DE ALIMENTO (equilibrio AESAN/mediterraneo): min por grupo como SUELO
    # BLANDO (penaliza el deficit, no bloquea) y max por grupo como techo DURO.
    def _comidas_de_grupo(grupo: str):
        return pulp.lpSum(
            u_vars[r.id] for u_vars, _x, pool in grupos for r in pool if r.grupo == grupo
        )

    for grupo, minimo in (min_por_grupo or {}).items():
        if minimo <= 0:
            continue
        s = pulp.LpVariable(f"deficit_grupo_{grupo}", lowBound=0)
        prob += _comidas_de_grupo(grupo) + s >= minimo
        objetivo += _PESO_DEFICIT * 0.01 * s  # penalizacion moderada (grupos son flexibles)
    for grupo, maximo in (max_por_grupo or {}).items():
        prob += _comidas_de_grupo(grupo) <= maximo, f"max_grupo_{grupo}"

    # VARIEDAD: penaliza usar mas de `max_familia_libre` comidas de la misma familia
    # de plato (p.ej. 3 salmorejos distintos). No bloquea; solo lo desincentiva.
    if peso_variedad > 0 and max_familia_libre > 0:
        familias: dict[str, list] = {}
        for u_vars, _x, pool in grupos:
            for r in pool:
                if r.familia:
                    familias.setdefault(r.familia, []).append(u_vars[r.id])
        for i, (fam, uvars) in enumerate(familias.items()):
            if len(uvars) <= 1:
                continue  # una sola receta de esa familia no puede ser monotona
            exceso = pulp.LpVariable(f"exceso_fam_{i}", lowBound=0)
            prob += exceso >= pulp.lpSum(uvars) - max_familia_libre
            objetivo += peso_variedad * exceso

    # RACIONALIZAR INGREDIENTES (reducir desperdicio/sobras): penaliza el nº de
    # PRODUCTOS distintos de Alcampo que habra que comprar, para que las recetas del
    # menu compartan ingredientes (Enfoque A del estudio, ROADMAP I). Un binario
    # y_p=1 si algun plato seleccionado usa el producto p; se minimiza Sum(y_p).
    # Solo se penalizan los productos POCO frecuentes en el pool (usados por entre 2
    # y `tope_reutil` recetas): son los que de verdad discriminan (comprar un
    # producto para UN solo plato = sobras casi seguras). Los productos usados por
    # una sola receta no ofrecen nada que compartir; los muy comunes se compran pase
    # lo que pase (su y_p seria ~constante) y solo cargarian el modelo. Ademas el
    # big-M se ajusta al maximo real de usos, lo que acelera mucho el branch&bound.
    n_binarios_reutil = 0
    if peso_reutilizacion > 0:
        recetas_de: dict[str, set[str]] = {}
        uvars_de: dict[str, list] = {}
        for u_vars, _x, pool in grupos:
            for r in pool:
                for p in r.productos:
                    recetas_de.setdefault(p, set()).add(r.id)
                    uvars_de.setdefault(p, []).append(u_vars[r.id])
        n_recetas_pool = len({r.id for _u, _x, pool in grupos for r in pool})
        tope_reutil = max(6, int(0.03 * n_recetas_pool))  # producto poco comun
        idx = 0
        for p, rset in recetas_de.items():
            if len(rset) < 2 or len(rset) > tope_reutil:
                continue
            uvars = uvars_de[p]
            big_m = min(2 * dias, len(uvars) * max_repeticiones)  # cota ajustada
            y = pulp.LpVariable(f"prod_{idx}", cat="Binary")
            idx += 1
            prob += pulp.lpSum(uvars) <= big_m * y, f"reutil_{idx}"
            objetivo += peso_reutilizacion * y
        n_binarios_reutil = idx

    # SOBRA REAL (Enfoque B, #23/24): por cada producto, gramos_p = Σ raciones·gramos/
    # racion·comensales; unidades_p (entero) >= gramos_p/formato; se penaliza la sobra en
    # PAQUETES: (unidades_p·formato − gramos_p)/formato = unidades_p − gramos_p/formato.
    # Asi el solver prefiere menus que aprovechan el formato comprado (menos desperdicio).
    # Restringido a productos usados por >=2 recetas del pool (donde la eleccion importa).
    n_vars_sobra = 0
    if peso_sobra > 0 and productos_formato:
        gramos_por_prod: dict[str, list] = {}
        recetas_prod: dict[str, set[str]] = {}
        for _u, x_vars, pool in grupos:
            for r in pool:
                for p, g in (r.productos_gramos or {}).items():
                    if g > 0 and productos_formato.get(p):
                        gramos_por_prod.setdefault(p, []).append((x_vars[r.id], g))
                        recetas_prod.setdefault(p, set()).add(r.id)
        idx = 0
        for p, terms in gramos_por_prod.items():
            if len(recetas_prod[p]) < 2:
                continue  # un solo plato usa p: su sobra no depende de la combinacion
            formato = productos_formato[p]
            gramos_p = pulp.lpSum(xv * g * num_comensales for xv, g in terms)
            u = pulp.LpVariable(f"uds_{idx}", lowBound=0, cat="Integer")
            idx += 1
            prob += u * formato >= gramos_p, f"uds_{idx}"
            # sobra en paquetes: u - gramos_p/formato (>=0). Penaliza el desperdicio.
            objetivo += peso_sobra * (u - gramos_p / formato)
        n_vars_sobra = idx

    # Menu ALTERNATIVO: al menos `min_diferencias` huecos deben usar recetas que
    # NO esten en el menu anterior (`corte`).
    if corte:
        usos_previos = pulp.lpSum(
            u_vars[rid] for u_vars, _x, _pool in grupos for rid in u_vars if rid in corte
        )
        prob += usos_previos <= 2 * dias - min_diferencias, "corte_alternativa"

    # Bandas de nutrientes sobre el total del dia (comida+cena).
    deficit_vars: dict[str, pulp.LpVariable] = {}
    for banda in bandas:
        total = nut_total(banda.nutriente)
        if banda.minimo is not None:
            if banda.nutriente in suelos_blandos:
                s = pulp.LpVariable(f"deficit_{banda.nutriente}", lowBound=0)
                deficit_vars[banda.nutriente] = s
                prob += total + s >= banda.minimo, f"minblando_{banda.nutriente}"
                objetivo += _PESO_DEFICIT * s
            else:
                prob += total >= banda.minimo, f"min_{banda.nutriente}"
        if banda.maximo is not None:
            prob += total <= banda.maximo, f"max_{banda.nutriente}"

    # BANDAS POR COMIDA (macros por franja): reparto del objetivo del dia entre
    # comida (cb+cl) y cena (d). Minimo BLANDO (penaliza el deficit, no bloquea),
    # maximo DURO. Asi cada comida mantiene su parte de energia/proteina.
    def _nut_franja(grupos_franja, nutriente):
        return pulp.lpSum(
            x_vars[r.id] * por_id[r.id].nutricion_racion.get(nutriente, 0.0) * num_comensales
            for _u, x_vars, pool in grupos_franja
            for r in pool
        )

    for etiqueta, grupos_franja, bandas_franja in (
        ("comida", ((cb, xb, pool_bc), (cl, xl, pool_libre)), bandas_comida),
        ("cena", ((d, xd, pool_cena),), bandas_cena),
    ):
        for banda in bandas_franja or []:
            total = _nut_franja(grupos_franja, banda.nutriente)
            if banda.minimo is not None:
                s = pulp.LpVariable(f"def_{etiqueta}_{banda.nutriente}", lowBound=0)
                prob += total + s >= banda.minimo
                objetivo += _PESO_DEFICIT * 0.05 * s  # moderado: guia sin romper
            if banda.maximo is not None:
                prob += total <= banda.maximo, f"max_{etiqueta}_{banda.nutriente}"

    # PRESUPUESTO maximo de la semana (tope de € DURO, #25): coste real servido
    # (raciones x coste/racion x comensales). Puede hacer el problema infactible si
    # choca con los suelos de nutrientes -> se reporta como no factible.
    if presupuesto_max is not None and presupuesto_max > 0:
        coste_expr = pulp.lpSum(
            x_vars[r.id] * por_id[r.id].coste_racion * num_comensales
            for _u, x_vars, pool in grupos
            for r in pool
        )
        prob += coste_expr <= presupuesto_max, "presupuesto_max"

    prob += objetivo
    # Parametros del CBC (#36): limite de tiempo y gap relativo configurables. Con
    # racionalizacion hay muchos binarios -> un limite de tiempo evita que probar la
    # optimalidad dispare el calculo (se acepta el mejor menu encontrado).
    kw = {"msg": 0}
    if tiempo_max_solver and tiempo_max_solver > 0:
        kw["timeLimit"] = tiempo_max_solver
    elif n_binarios_reutil > 0 or n_vars_sobra > 0:
        kw["timeLimit"] = 25
    if gap_solver and gap_solver > 0:
        kw["gapRel"] = gap_solver
    prob.solve(pulp.PULP_CBC_CMD(**kw))
    estado = pulp.LpStatus[prob.status]
    # Hay solucion utilizable si las variables tienen valor asignado (incumbente
    # factible), aunque el estado no sea "Optimal" por haber agotado el tiempo.
    todas = list(cb.values()) + list(cl.values()) + list(d.values())
    tiene_valores = bool(todas) and all(v.value() is not None for v in todas)
    if estado in ("Infeasible", "Unbounded") or not tiene_valores:
        return MenuOptimizado({}, 0.0, {}, False, f"sin solucion factible ({estado})")

    def _sel(vars_: dict) -> dict[str, int]:
        return {rid: int(round(v.value())) for rid, v in vars_.items() if v.value() and v.value() > 0.5}

    sel_bc = _sel(cb)
    sel_libre = _sel(cl)
    sel_cena = _sel(d)
    sel_comida: dict[str, int] = dict(sel_bc)
    for rid, n in sel_libre.items():
        sel_comida[rid] = sel_comida.get(rid, 0) + n
    seleccion: dict[str, int] = {}
    for franja in (sel_comida, sel_cena):
        for rid, n in franja.items():
            seleccion[rid] = seleccion.get(rid, 0) + n

    # Raciones por persona realmente servidas (fraccionables) de cada receta,
    # totales y por franja (para controlar/medir los macros por comida).
    def _rac(x_vars_list) -> dict[str, float]:
        r: dict[str, float] = {}
        for x_vars in x_vars_list:
            for rid, xv in x_vars.items():
                v = xv.value() or 0.0
                if v > 1e-6:
                    r[rid] = round(r.get(rid, 0.0) + v, 3)
        return r

    rac_comida = _rac([xb, xl])
    rac_cena = _rac([xd])
    raciones: dict[str, float] = {}
    for _u, x_vars, _pool in grupos:
        for rid, xv in x_vars.items():
            v = xv.value() or 0.0
            if v > 1e-6:
                raciones[rid] = raciones.get(rid, 0.0) + v

    coste = sum(por_id[rid].coste_racion * num_comensales * x for rid, x in raciones.items())
    nutricion: dict[str, float] = {}
    for rid, x in raciones.items():
        for nut, val in por_id[rid].nutricion_racion.items():
            nutricion[nut] = nutricion.get(nut, 0.0) + val * num_comensales * x
    raciones = {rid: round(x, 2) for rid, x in raciones.items()}  # redondeo solo informativo
    deficit = {
        nut: round(s.value(), 1) for nut, s in deficit_vars.items() if s.value() and s.value() > 0.5
    }
    return MenuOptimizado(
        seleccion=seleccion,
        coste_total=round(coste, 2),
        nutricion_total={k: round(v, 1) for k, v in nutricion.items()},
        factible=True,
        deficit_blando=deficit,
        seleccion_comida=sel_comida,
        seleccion_cena=sel_cena,
        seleccion_comida_bc=sel_bc,
        raciones=raciones,
        raciones_comida=rac_comida,
        raciones_cena=rac_cena,
    )
