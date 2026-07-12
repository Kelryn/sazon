"""Objetivos nutricionales (bandas mín/máx) por persona y semana.

Motivacion: el "problema de la dieta" clasico, si solo minimiza coste, elimina
la proteina (el macronutriente mas caro) y llena el menu de pan y azucar. Para
evitarlo, el solver (ver solver.py) obliga a que el total semanal de cada
nutriente caiga dentro de una banda razonable. La proteina y la fibra tienen
SUELO (minimo); grasa saturada, azucares y sal tienen TECHO (maximo); energia,
hidratos y grasa total tienen banda por ambos lados.

Valores de referencia para adultos (fuentes en el README de valores):
- Proteina: 0,83 g/kg peso/dia  (EFSA, Population Reference Intake)
- Hidratos: 45-60 % de la energia  (EFSA)
- Grasa total: 20-35 % de la energia  (EFSA)
- Grasa saturada: <10 % de la energia  (OMS)
- Azucares (libres): <10 % de la energia  (OMS)  [ojo: el dato de Alcampo es
  azucares totales, no solo libres -> el techo es conservador]
- Sal: <5 g/dia  (OMS)
- Fibra: >=25 g/dia  (EFSA)

NOTA sobre micronutrientes (hierro, calcio, vitaminas...): no se restringen aun
porque el catalogo de Alcampo (endpoint bop) solo trae macronutrientes. Para
micronutrientes haria falta cruzar por alimento con una base de composicion
(p.ej. BEDCA en España u Open Food Facts). Queda como extension futura; la
estructura de este modulo ya lo admite (basta añadir mas entradas).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# kcal por gramo de cada macronutriente (factores de Atwater).
KCAL_POR_G_PROTEINA = 4.0
KCAL_POR_G_HIDRATOS = 4.0
KCAL_POR_G_GRASA = 9.0


@dataclass
class ConfigNutricion:
    """Parametros para calcular los objetivos. Todo sobrescribible desde config.yaml."""

    kcal_por_comensal_dia: float = 2000.0
    peso_kg_por_comensal: float = 70.0
    dias: int = 7

    # Reparto RECOMENDADO de la energia del dia por franja (FEN/AESAN, guias de
    # alimentacion saludable): desayuno 20-25%, media manana/merienda 10-15%,
    # COMIDA 30-35%, CENA 25-30%. El menu planifica comida+cena, asi que cubre
    # pct_comida + pct_cena del dia (el resto queda fuera del menu).
    pct_comida: float = 0.35
    pct_cena: float = 0.30

    # Fraccion de la INGESTA DIARIA que cubren las comidas del menu. Si es None,
    # se deriva de pct_comida + pct_cena (0.65). Sobrescribible desde config.
    fraccion_ingesta_menu: float | None = None

    @property
    def fraccion_menu(self) -> float:
        if self.fraccion_ingesta_menu is not None:
            return self.fraccion_ingesta_menu
        return self.pct_comida + self.pct_cena

    # Proteina: suelo en g/kg/dia (EFSA 0,83; se sube un poco para no quedar al
    # limite) y techo prudente para no disparar coste sin sentido.
    proteina_g_por_kg_min: float = 0.9
    proteina_g_por_kg_max: float = 2.0

    # Rangos como fraccion de la energia.
    hidratos_frac_min: float = 0.45
    hidratos_frac_max: float = 0.60
    grasa_frac_min: float = 0.20
    grasa_frac_max: float = 0.35
    grasa_sat_frac_max: float = 0.10
    azucares_frac_max: float = 0.10

    # Absolutos por persona y dia.
    sal_g_max_dia: float = 5.0
    fibra_g_min_dia: float = 25.0

    # Tolerancia de la banda de energia (+-).
    energia_tolerancia: float = 0.10


@dataclass
class BandaNutriente:
    """Limite semanal (para el total del menu) de un nutriente. min/max None = sin limite por ese lado."""

    nutriente: str  # coincide con las claves usadas en el calculo de recetas
    minimo: float | None
    maximo: float | None
    unidad: str
    tipo: str  # 'banda' | 'min' | 'max' (informativo)


def objetivos_semanales(cfg: ConfigNutricion, num_comensales: int) -> list[BandaNutriente]:
    """Bandas para el TOTAL del menu (todas las comidas, todos los comensales, toda la semana)."""
    factor = cfg.dias * num_comensales  # de "por persona y dia" a "total del menu"
    frac = cfg.fraccion_menu  # las comidas del menu cubren solo esta parte del dia
    energia_dia = cfg.kcal_por_comensal_dia * frac

    def gramos(fraccion: float, kcal_por_g: float) -> float:
        return fraccion * energia_dia / kcal_por_g

    return [
        BandaNutriente(
            "energia_kcal",
            minimo=energia_dia * (1 - cfg.energia_tolerancia) * factor,
            maximo=energia_dia * (1 + cfg.energia_tolerancia) * factor,
            unidad="kcal",
            tipo="banda",
        ),
        BandaNutriente(
            "proteinas",
            minimo=cfg.proteina_g_por_kg_min * cfg.peso_kg_por_comensal * frac * factor,
            maximo=cfg.proteina_g_por_kg_max * cfg.peso_kg_por_comensal * frac * factor,
            unidad="g",
            tipo="min",  # lo importante es el suelo
        ),
        BandaNutriente(
            "hidratos",
            minimo=gramos(cfg.hidratos_frac_min, KCAL_POR_G_HIDRATOS) * factor,
            maximo=gramos(cfg.hidratos_frac_max, KCAL_POR_G_HIDRATOS) * factor,
            unidad="g",
            tipo="banda",
        ),
        BandaNutriente(
            "grasas",
            minimo=gramos(cfg.grasa_frac_min, KCAL_POR_G_GRASA) * factor,
            maximo=gramos(cfg.grasa_frac_max, KCAL_POR_G_GRASA) * factor,
            unidad="g",
            tipo="banda",
        ),
        BandaNutriente(
            "grasas_sat",
            minimo=None,
            maximo=gramos(cfg.grasa_sat_frac_max, KCAL_POR_G_GRASA) * factor,
            unidad="g",
            tipo="max",
        ),
        BandaNutriente(
            "azucares",
            minimo=None,
            maximo=gramos(cfg.azucares_frac_max, KCAL_POR_G_HIDRATOS) * factor,
            unidad="g",
            tipo="max",
        ),
        BandaNutriente(
            "sal", minimo=None, maximo=cfg.sal_g_max_dia * frac * factor, unidad="g", tipo="max"
        ),
        BandaNutriente(
            "fibra", minimo=cfg.fibra_g_min_dia * frac * factor, maximo=None, unidad="g", tipo="min"
        ),
    ]


# Nutrientes cuyo objetivo POR COMIDA tiene sentido controlar (energia y el
# reparto de proteina entre comidas). Base: el reparto energetico por ingesta
# (FEN/AESAN: comida ~35%, cena ~30% del dia) y la evidencia de que repartir la
# PROTEINA de forma pareja entre comidas mejora la sintesis proteica muscular
# (Mamerow et al. 2014, J Nutr; ~0,4 g/kg por comida). No se controlan por comida
# los techos de sal/azucar/grasa saturada (importan en el total del dia).
NUTRIENTES_POR_COMIDA = ("energia_kcal", "proteinas")


def escalar_bandas(
    bandas: list[BandaNutriente], factor: float, solo: tuple[str, ...] | None = None
) -> list[BandaNutriente]:
    """Devuelve las bandas con min/max multiplicados por `factor` (para repartir
    el objetivo del dia entre las franjas comida/cena). Si `solo` se indica, solo
    incluye esos nutrientes."""
    out: list[BandaNutriente] = []
    for b in bandas:
        if solo is not None and b.nutriente not in solo:
            continue
        out.append(
            BandaNutriente(
                b.nutriente,
                minimo=None if b.minimo is None else b.minimo * factor,
                maximo=None if b.maximo is None else b.maximo * factor,
                unidad=b.unidad,
                tipo=b.tipo,
            )
        )
    return out


def resumen_legible(bandas: list[BandaNutriente]) -> str:
    lineas = []
    for b in bandas:
        lo = f"{b.minimo:.0f}" if b.minimo is not None else "—"
        hi = f"{b.maximo:.0f}" if b.maximo is not None else "—"
        lineas.append(f"  {b.nutriente:14s} [{lo:>7} .. {hi:>7}] {b.unidad}  ({b.tipo})")
    return "\n".join(lineas)
