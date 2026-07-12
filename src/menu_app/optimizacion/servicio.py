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
from .grupos_alimentos import grupo_receta
from .nutrientes import (
    NUTRIENTES_POR_COMIDA,
    BandaNutriente,
    ConfigNutricion,
    escalar_bandas,
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


def config_nutricion(cfg: dict) -> ConfigNutricion:
    n = cfg.get("nutricion", {}) or {}
    base = ConfigNutricion()
    frac = cfg.get("fraccion_ingesta_menu", n.get("fraccion_ingesta_menu"))
    return ConfigNutricion(
        kcal_por_comensal_dia=float(cfg.get("kcal_por_comensal", base.kcal_por_comensal_dia)),
        peso_kg_por_comensal=float(n.get("peso_kg_por_comensal", base.peso_kg_por_comensal)),
        dias=int(n.get("dias", base.dias)),
        # % de la energia del dia recomendado por franja (FEN/AESAN); si no se fija
        # fraccion_ingesta_menu, el menu cubre pct_comida + pct_cena del dia.
        pct_comida=float(n.get("pct_comida", base.pct_comida)),
        pct_cena=float(n.get("pct_cena", base.pct_cena)),
        fraccion_ingesta_menu=float(frac) if frac is not None else None,
        proteina_g_por_kg_min=float(n.get("proteina_g_por_kg_min", base.proteina_g_por_kg_min)),
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
    recetas: dict[str, RecetaOpt] = {}
    descartadas = 0
    descartadas_rol = 0
    for c in calculadas:
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
            grupo=grupo_receta(c.titulo, c.ingrediente_principal),
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
        max_familia_libre=int(cfg.get("max_comidas_por_familia", 2)),
        min_por_grupo=(cfg.get("grupos_alimentos", {}) or {}).get("minimo_semana"),
        max_por_grupo=(cfg.get("grupos_alimentos", {}) or {}).get("maximo_semana"),
        bandas_comida=bandas_comida,
        bandas_cena=bandas_cena,
        racion_frac_min=float(cfg.get("racion_frac_min", 0.75)),
        racion_frac_max=float(cfg.get("racion_frac_max", 1.25)),
        excluidas=excluidas,
        corte=corte,
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
    )
