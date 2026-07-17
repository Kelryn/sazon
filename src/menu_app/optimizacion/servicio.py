"""Servicio de generacion de menu, compartido por el CLI y la UI web.

Reune la logica que antes vivia en el CLI: leer config, escalar los objetivos a la
fraccion de ingesta del dia, construir el pool de recetas utilizables (con coste y
nutricion reales) y llamar al solver comida+cena.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..configuracion import DIAS_SEMANA as _DIAS_SEMANA
from ..configuracion import dias_batchcooking as _dias_bc_cfg
from .economia_recetas import calcular_todas
from .estacionalidad import puntua_estacionalidad
from .grupos_alimentos import grupo_receta
from .nutrientes import (
    NUTRIENTES_POR_COMIDA,
    BandaNutriente,
    ConfigNutricion,
    escalar_bandas,
    nutri_score,
    objetivos_semanales,
)
from .palatabilidad import palatabilidad_bayesiana
from .solver import MenuOptimizado, RecetaOpt, optimizar_comida_cena

# Cobertura minima de ingredientes para fiarnos del coste/nutricion de una receta
# (sobrescribible con cobertura_minima en config.yaml).
COBERTURA_MINIMA = 0.7

# Pesos del objetivo expresados como PORCENTAJE 0-100 en la config/UI. Cada clave
# nueva (pct) se mapea a su peso interno: interno = pct/100 * maximo. Se aceptan
# tambien las claves antiguas (valor interno directo) por compatibilidad.
_PESOS_PCT = {
    # clave_pct: (clave_antigua, maximo_interno, pct_por_defecto)
    "sabor_pct": ("peso_palatabilidad", 10.0, 50),
    "cena_ligera_pct": ("peso_cena_ligera_simple", 6.0, 50),
    "favoritas_pct": ("peso_favorita", 8.0, 50),
    # Racionalizar la compra (que las recetas compartan productos): 0 = desactivado.
    "reutilizacion_pct": ("peso_reutilizacion", 1.5, 0),
    # Priorizar SALUD (grupos sanos, menos grasa sat/azucar/sal): 0 = desactivado (#26).
    "salud_pct": ("peso_salud", 8.0, 0),
    # Reducir SOBRAS reales (aprovechar el formato comprado): 0 = desactivado (#23/24).
    "sobra_pct": ("peso_sobra", 3.0, 0),
    # Evitar ULTRAPROCESADOS (NOVA 4): 0 = desactivado (#3).
    "evitar_procesados_pct": ("peso_ultraprocesado", 8.0, 0),
    # Preferir productos de TEMPORADA (frutas/verduras del mes): 0 = desactivado (#11).
    "estacionalidad_pct": ("peso_estacionalidad", 6.0, 0),
}


def peso_interno(cfg: dict, clave_pct: str) -> float:
    antigua, maximo, defecto = _PESOS_PCT[clave_pct]
    if clave_pct in cfg:
        return max(0.0, min(100.0, float(cfg[clave_pct]))) / 100.0 * maximo
    if antigua in cfg:
        return float(cfg[antigua])
    return defecto / 100.0 * maximo

# Dominios de recetas en español (para el minimo de cocina local del menu).
DOMINIOS_ESPANOLES = {"recetas.elperiodico.com", "recetasgratis.net"}


def es_espanola(fuente: str | None) -> bool:
    return bool(fuente) and (fuente in DOMINIOS_ESPANOLES or fuente.endswith(".es"))


def aptitud_cena(kcal_racion: float | None, n_ingredientes: int) -> float:
    """0..1: cuanto de ligera (pocas kcal) y sencilla (pocos ingredientes) es una receta."""
    kcal = kcal_racion or 0.0
    ligereza = max(0.0, min(1.0, (750.0 - kcal) / 750.0)) if kcal else 0.5
    sencillez = max(0.0, min(1.0, (16.0 - n_ingredientes) / 16.0))
    return 0.5 * ligereza + 0.5 * sencillez


# Palabras iniciales que no identifican el TIPO de plato (para calcular la familia).
_FAMILIA_IGNORA = {
    "receta", "de", "del", "la", "el", "los", "las", "con", "sin", "y", "o", "al",
    "a", "en", "un", "una", "mi", "su", "lo", "mini", "rico", "rica", "facil",
    "rapido", "rapida", "casero", "casera", "autentico", "autentica", "mejor",
}


def familia_receta(titulo: str) -> str:
    """Tipo de plato = primera palabra significativa del titulo (para la variedad):
    'Receta de Salmorejo de naranja' -> 'salmorejo'; agrupa las variantes."""
    from ..matching.normalizar import quitar_acentos

    for token in quitar_acentos(titulo or "").replace(",", " ").split():
        if token.isalpha() and token not in _FAMILIA_IGNORA and len(token) > 2:
            return token
    return ""


# Grupos de alimento "sanos" (mediterraneo/AESAN) que suman a la puntuacion de salud.
_GRUPOS_SANOS = frozenset({"verdura", "legumbre", "pescado", "fruta"})


def salud_receta(grupo: str, nutricion_racion: dict[str, float]) -> float:
    """Puntuacion de salud -1..1 (determinista): premia grupos sanos y penaliza la
    densidad de grasa saturada, azucares y sal por racion. Usada por el eje de salud
    del optimizador (#26)."""
    s = 0.0
    if grupo in _GRUPOS_SANOS:
        s += 0.6
    elif grupo == "carne_roja":
        s -= 0.3
    kcal = max(1.0, nutricion_racion.get("energia_kcal", 0.0))
    # Penaliza por cada 100 kcal: grasa sat (>4g malo), azucares (>10g), sal (>0.5g).
    sat = nutricion_racion.get("grasas_sat", 0.0) / kcal * 100
    azu = nutricion_racion.get("azucares", 0.0) / kcal * 100
    sal = nutricion_racion.get("sal", 0.0) / kcal * 100
    s -= min(0.4, max(0.0, (sat - 4.0) / 10.0))
    s -= min(0.3, max(0.0, (azu - 10.0) / 20.0))
    s -= min(0.3, max(0.0, (sal - 0.5) / 1.5))
    return max(-1.0, min(1.0, s))


def por_que_receta(r: RecetaOpt) -> str:
    """Explica en una linea por que entro una receta en el menu (#35): coste, sabor,
    salud, grupo, favorita, tiempo. Determinista, a partir de los datos de RecetaOpt."""
    razones: list[str] = [f"{r.coste_racion:.2f} €/ración"]
    if r.es_favorita:
        razones.append("favorita ★")
    if r.palatabilidad >= 0.7:
        razones.append("bien valorada")
    if r.salud >= 0.4:
        razones.append("opción sana")
    elif r.salud <= -0.2:
        razones.append("capricho")
    if r.grupo and r.grupo != "otro":
        razones.append(r.grupo.replace("_", " "))
    if r.es_batchcooking:
        razones.append("batchcooking")
    if r.tiempo_min:
        razones.append(f"{r.tiempo_min} min")
    return " · ".join(razones)


# Factores de actividad (TDEE = BMR x factor) y de objetivo (ajuste calorico).
_FACTOR_ACTIVIDAD = {
    "sedentario": 1.2, "ligero": 1.375, "moderado": 1.55, "activo": 1.725, "muy_activo": 1.9,
}
_FACTOR_OBJETIVO = {"perder": 0.80, "mantener": 1.0, "ganar": 1.10}


def kcal_desde_perfil(perfil: dict) -> float | None:
    """kcal/dia objetivo desde peso/altura/edad/sexo/actividad/objetivo (#4/#5).

    BMR por Mifflin-St Jeor; TDEE = BMR x factor de actividad; ajuste por objetivo
    (perder -20% / mantener / ganar +10%). Devuelve None si faltan datos clave."""
    try:
        peso = float(perfil.get("peso_kg") or 0)
        altura = float(perfil.get("altura_cm") or 0)
        edad = float(perfil.get("edad") or 0)
    except (TypeError, ValueError):
        return None
    if peso <= 0 or altura <= 0 or edad <= 0:
        return None
    sexo = str(perfil.get("sexo", "h")).lower()[:1]
    bmr = 10 * peso + 6.25 * altura - 5 * edad + (5 if sexo == "h" else -161)
    tdee = bmr * _FACTOR_ACTIVIDAD.get(str(perfil.get("actividad", "moderado")), 1.55)
    return round(tdee * _FACTOR_OBJETIVO.get(str(perfil.get("objetivo", "mantener")), 1.0))


def config_nutricion(cfg: dict) -> ConfigNutricion:
    n = cfg.get("nutricion", {}) or {}
    base = ConfigNutricion()
    frac = cfg.get("fraccion_ingesta_menu", n.get("fraccion_ingesta_menu"))
    # kcal automaticas desde el perfil corporal si esta activado (#4/#5); si no, manual.
    perfil = cfg.get("perfil", {}) or {}
    kcal_manual = float(cfg.get("kcal_por_comensal", base.kcal_por_comensal_dia))
    kcal = kcal_manual
    prot_min = float(n.get("proteina_g_por_kg_min", base.proteina_g_por_kg_min))
    if perfil.get("calcular_kcal_auto"):
        auto = kcal_desde_perfil(perfil)
        if auto:
            kcal = auto
        # Perder/ganar peso -> mas proteina para preservar/ganar musculo (#5).
        objetivo = str(perfil.get("objetivo", "mantener"))
        if objetivo == "perder":
            prot_min = max(prot_min, 1.6)
        elif objetivo == "ganar":
            prot_min = max(prot_min, 1.8)
    return ConfigNutricion(
        kcal_por_comensal_dia=kcal,
        peso_kg_por_comensal=float(n.get("peso_kg_por_comensal", base.peso_kg_por_comensal)),
        dias=int(n.get("dias", base.dias)),
        # % de la energia del dia recomendado por franja (FEN/AESAN); si no se fija
        # fraccion_ingesta_menu, el menu cubre pct_comida + pct_cena del dia.
        pct_comida=float(n.get("pct_comida", base.pct_comida)),
        pct_cena=float(n.get("pct_cena", base.pct_cena)),
        fraccion_ingesta_menu=float(frac) if frac is not None else None,
        proteina_g_por_kg_min=prot_min,
        sal_g_max_dia=float(n.get("sal_g_max_dia", base.sal_g_max_dia)),
        fibra_g_min_dia=float(n.get("fibra_g_min_dia", base.fibra_g_min_dia)),
        energia_tolerancia=float(n.get("energia_tolerancia", base.energia_tolerancia)),
    )


@dataclass
class ResultadoMenu:
    menu: MenuOptimizado
    recetas: dict[str, RecetaOpt]  # por id, para pintar la seleccion
    bandas: list[BandaNutriente]
    num_comensales: int
    dias: int
    fraccion_ingesta: float
    n_utilizables: int
    descartadas_cobertura: int
    descartadas_rol: int
    dias_bc: list[str] = field(default_factory=list)  # dias marcados batchcooking (lun..dom)
    meta: dict = field(default_factory=dict)


def _max_repeticiones_semana(cfg: dict) -> int:
    """Repeticiones maximas de una receta EN LA MISMA SEMANA, derivadas de
    `dias_repeticion` (cada cuantos dias puede volver a comerse una receta).
    dias_repeticion>=7 -> 1 vez/semana (sin repetir entre semana)."""
    dias_rep = int(cfg.get("dias_repeticion", 7))
    if dias_rep <= 0:
        return int(cfg.get("repeticiones_comida_semana", 3))
    return max(1, round(7 / dias_rep))


def semanas_exclusion(cfg: dict) -> int:
    """Cuantas semanas ANTERIORES vetan una receta (dias_repeticion > 7)."""
    dias_rep = int(cfg.get("dias_repeticion", 7))
    return max(0, -(-dias_rep // 7) - 1)  # ceil(d/7) - 1


def generar_menu(
    conn: sqlite3.Connection,
    cfg: dict,
    batchcooking: bool = False,
    incluir_todo: bool = False,
    excluidas: frozenset[str] = frozenset(),
    corte: set[str] | None = None,
) -> ResultadoMenu:
    num_comensales = int(cfg.get("num_comensales", 2))
    cfg_nut = config_nutricion(cfg)
    dias = cfg_nut.dias
    max_rep = _max_repeticiones_semana(cfg)

    calculadas = calcular_todas(conn)
    palat = palatabilidad_bayesiana(conn)

    cobertura_min = float(cfg.get("cobertura_minima", COBERTURA_MINIMA))
    exigir_todos = bool(cfg.get("exigir_todos_ingredientes", True))
    # Lista negra de ingredientes que NO se quieren en el menu (#31): se excluye la
    # receta si alguno de sus ingredientes contiene uno de estos terminos.
    excluidos_ing = [
        e.strip().lower() for e in (cfg.get("ingredientes_excluidos") or []) if str(e).strip()
    ]
    # Alergenos del usuario (#17): se EXCLUYE la receta si alguno de sus productos
    # contiene ese alergeno (segun datos disponibles; no garantiza ausencia total).
    alergenos_usuario = [
        a.strip().lower() for a in (cfg.get("alergenos") or []) if str(a).strip()
    ]
    # Tiempo maximo de preparacion (#30): descarta recetas que tarden mas (0 = sin tope).
    tiempo_max = int(cfg.get("tiempo_max_receta_min", 0) or 0)
    peso_salud = peso_interno(cfg, "salud_pct")
    peso_sobra = peso_interno(cfg, "sobra_pct")
    # Mes para la estacionalidad (#11): override en config o el mes actual.
    from datetime import date

    mes_temporada = int(cfg.get("mes_temporada") or 0) or date.today().month
    # Formatos de producto (g/ml por paquete) para penalizar la sobra real (#23/24).
    productos_formato: dict[str, float] = {}
    if peso_sobra > 0:
        productos_formato = {
            r["retailer_product_id"]: r["cantidad_base_g_ml"]
            for r in conn.execute(
                "SELECT retailer_product_id, cantidad_base_g_ml FROM productos "
                "WHERE cantidad_base_g_ml IS NOT NULL AND cantidad_base_g_ml > 0"
            ).fetchall()
        }
    recetas: dict[str, RecetaOpt] = {}
    descartadas = 0
    descartadas_rol = 0
    descartadas_excluidas = 0
    descartadas_tiempo = 0
    descartadas_alergeno = 0
    for c in calculadas:
        if excluidos_ing and any(
            term in ing for ing in c.ingredientes_norm for term in excluidos_ing
        ):
            descartadas_excluidas += 1
            continue
        if tiempo_max and c.tiempo_total_min and c.tiempo_total_min > tiempo_max:
            descartadas_tiempo += 1
            continue
        if alergenos_usuario and any(
            term in al for al in c.alergenos for term in alergenos_usuario
        ):
            descartadas_alergeno += 1
            continue
        # Fuera si falta cobertura, si el ingrediente PRINCIPAL no se puede comprar,
        # o (exigir_todos_ingredientes) si falta CUALQUIER ingrediente no opcional:
        # no tiene sentido planificar una receta que no se puede cocinar completa.
        if (
            not c.raciones
            or c.coste_racion is None
            or c.cobertura < cobertura_min
            or c.principal_sin_producto
            or (exigir_todos and c.falta_no_opcional)
        ):
            descartadas += 1
            continue
        if not incluir_todo and c.rol != "principal":
            descartadas_rol += 1
            continue
        recetas[c.receta_id] = RecetaOpt(
            id=c.receta_id,
            titulo=c.titulo,
            coste_racion=c.coste_racion,
            nutricion_racion=c.nutricion_racion(),
            palatabilidad=palat.get(c.receta_id, 0.5),
            es_espanola=es_espanola(c.fuente),
            # 'plato unico' del editor tambien vale para los dias batchcooking.
            es_batchcooking=c.es_batchcooking or c.es_plato_unico,
            aptitud_cena=(
                1.0 if c.es_cena
                else aptitud_cena(c.nutricion_racion().get("energia_kcal"), c.n_ingredientes)
            ),
            es_favorita=c.es_favorita,
            familia=familia_receta(c.titulo),
            grupo=(_g := grupo_receta(c.titulo, c.ingrediente_principal)),
            productos=frozenset(c.productos),
            salud=salud_receta(_g, c.nutricion_racion()),
            tiempo_min=c.tiempo_total_min,
            productos_gramos=(
                {p: g / c.raciones for p, g in c.productos_gramos.items()}
                if c.raciones else {}
            ),
            nutri=(lambda p: nutri_score(p, _g)[1] if p else "")(c.nutricion_por_100g()),
            procesado=c.procesado,
            estacionalidad=puntua_estacionalidad(c.ingredientes_norm, mes_temporada),
        )

    # Dias batchcooking: si viene el flag global, TODOS; si no, los marcados en config.
    dias_bc = _dias_bc_cfg(cfg)
    n_dias_bc = dias if batchcooking else min(len(dias_bc), dias)

    bandas = objetivos_semanales(cfg_nut, num_comensales)
    # Macros POR COMIDA: reparte el objetivo del dia entre comida y cena segun su
    # % de energia (FEN/AESAN), controlando energia y proteina en cada franja.
    bandas_comida = bandas_cena = None
    if cfg.get("nutrientes_por_comida", True):
        frac = cfg_nut.fraccion_menu or 1.0
        bandas_comida = escalar_bandas(
            bandas, cfg_nut.pct_comida / frac, solo=NUTRIENTES_POR_COMIDA
        )
        bandas_cena = escalar_bandas(
            bandas, cfg_nut.pct_cena / frac, solo=NUTRIENTES_POR_COMIDA
        )
    menu = optimizar_comida_cena(
        list(recetas.values()), bandas, dias=dias, num_comensales=num_comensales,
        max_repeticiones=max_rep, peso_palatabilidad=peso_interno(cfg, "sabor_pct"),
        frac_espanola_min=float(cfg.get("fraccion_recetas_espanolas_min", 0.5)),
        dias_batchcooking=n_dias_bc,
        peso_cena_ligera_simple=peso_interno(cfg, "cena_ligera_pct"),
        peso_favorita=peso_interno(cfg, "favoritas_pct"),
        peso_variedad=float(cfg.get("peso_variedad", 3.0)),
        peso_reutilizacion=peso_interno(cfg, "reutilizacion_pct"),
        peso_salud=peso_salud,
        peso_ultraprocesado=peso_interno(cfg, "evitar_procesados_pct"),
        peso_estacionalidad=peso_interno(cfg, "estacionalidad_pct"),
        peso_sobra=peso_sobra,
        productos_formato=productos_formato,
        max_familia_libre=int(cfg.get("max_comidas_por_familia", 2)),
        min_por_grupo=(cfg.get("grupos_alimentos", {}) or {}).get("minimo_semana"),
        max_por_grupo=(cfg.get("grupos_alimentos", {}) or {}).get("maximo_semana"),
        bandas_comida=bandas_comida,
        bandas_cena=bandas_cena,
        racion_frac_min=float(cfg.get("racion_frac_min", 0.75)),
        racion_frac_max=float(cfg.get("racion_frac_max", 1.25)),
        excluidas=excluidas,
        corte=corte,
        presupuesto_max=float(cfg.get("presupuesto_max_semana", 0) or 0) or None,
        tiempo_max_solver=float(cfg.get("tiempo_max_solver", 0) or 0) or None,
        gap_solver=float(cfg.get("gap_solver", 0) or 0) or None,
    )
    return ResultadoMenu(
        menu=menu,
        recetas=recetas,
        bandas=bandas,
        num_comensales=num_comensales,
        dias=dias,
        fraccion_ingesta=cfg_nut.fraccion_menu,
        n_utilizables=len(recetas),
        descartadas_cobertura=descartadas,
        descartadas_rol=descartadas_rol,
        dias_bc=dias_bc if not batchcooking else list(_DIAS_SEMANA[:dias]),
        meta={
            "descartadas_excluidas": descartadas_excluidas,
            "descartadas_tiempo": descartadas_tiempo,
            "descartadas_alergeno": descartadas_alergeno,
        },
    )
