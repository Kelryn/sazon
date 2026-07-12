"""Requerimientos nutricionales semanales por persona, con bandas min/max.

Motivo (decision del usuario): si el optimizador solo minimiza coste, elimina
los alimentos caros -- tipicamente los proteicos -- y "cuadra" la semana con
hidratos baratos. Para evitarlo, cada nutriente tiene una BANDA SEMANAL
(minimo y/o maximo) por persona que el solver MILP debe respetar como
restriccion dura. La proteina, en particular, tiene un suelo que no se puede
recortar por precio.

Valores de referencia (fuentes oficiales, verificadas):
- Proteina: EFSA PRI 0,83 g/kg de peso corporal/dia (media poblacional AR 0,66);
  tope prudente 2,0 g/kg/dia (ingestas de hasta 2x PRI se consideran seguras).
- Hidratos de carbono: EFSA RI 45-60 % de la energia (4 kcal/g).
- Grasas totales: EFSA RI 20-35 % de la energia (9 kcal/g).
- Grasas saturadas: OMS/AESAN <10 % de la energia ("lo mas bajas posible" segun EFSA).
- Azucares: OMS <10 % E para azucares LIBRES. Nuestros datos de producto traen
  azucares TOTALES (incluyen los intrinsecos de fruta y lacteos), asi que el
  tope por defecto se fija en 15 % E para no penalizar fruta/leche; es
  configurable.
- Fibra: EFSA AI 25 g/dia en adultos.
- Sal: OMS <5 g/dia.
- Energia: la fija el usuario (kcal/dia por comensal) con una tolerancia +-.

Micronutrientes (vitaminas y minerales): el catalogo de Alcampo NO publica
esos datos por producto, asi que no se pueden restringir numericamente. Se
cubren de forma indirecta -- el metodo estandar en dietetica -- con las
raciones de grupos de alimentos de AESAN que el MILP impone aparte
(>=3 hortalizas/dia, 2-3 frutas/dia, >=4 legumbres/semana, <=3 carne/semana...),
que son las que garantizan la suficiencia de micronutrientes en la practica.
"""

from __future__ import annotations

from dataclasses import dataclass

DIAS_SEMANA = 7
KCAL_POR_G_GRASA = 9.0
KCAL_POR_G_HIDRATO = 4.0


@dataclass(frozen=True)
class PerfilNutricional:
    """Parametros de una persona; todo lo demas se deriva de aqui."""

    peso_kg: float = 70.0
    kcal_dia: float = 2200.0
    tolerancia_energia_pct: float = 10.0  # banda +- sobre las kcal semanales
    proteina_min_g_kg_dia: float = 0.83   # EFSA PRI
    proteina_max_g_kg_dia: float = 2.0    # tope prudente
    grasas_min_pct_e: float = 20.0        # EFSA
    grasas_max_pct_e: float = 35.0
    grasas_sat_max_pct_e: float = 10.0    # OMS/AESAN
    hidratos_min_pct_e: float = 45.0      # EFSA
    hidratos_max_pct_e: float = 60.0
    azucares_max_pct_e: float = 15.0      # sobre azucares TOTALES (ver docstring)
    fibra_min_g_dia: float = 25.0         # EFSA AI
    sal_max_g_dia: float = 5.0            # OMS


@dataclass(frozen=True)
class BandaNutriente:
    """Restriccion semanal por persona: minimo y/o maximo (None = sin limite)."""

    minimo: float | None
    maximo: float | None

    def cumple(self, valor: float) -> bool:
        if self.minimo is not None and valor < self.minimo:
            return False
        if self.maximo is not None and valor > self.maximo:
            return False
        return True


def bandas_semanales(perfil: PerfilNutricional) -> dict[str, BandaNutriente]:
    """Bandas semanales POR PERSONA para cada nutriente que si podemos medir.

    Las claves coinciden con las columnas nutricionales de la BD (por 100 g),
    agregadas a nivel de receta/semana: energia_kcal, proteinas_g, grasas_g,
    grasas_sat_g, hidratos_g, azucares_g, fibra_g, sal_g.
    """
    kcal_sem = perfil.kcal_dia * DIAS_SEMANA
    tol = perfil.tolerancia_energia_pct / 100.0

    return {
        "energia_kcal": BandaNutriente(kcal_sem * (1 - tol), kcal_sem * (1 + tol)),
        "proteinas_g": BandaNutriente(
            perfil.proteina_min_g_kg_dia * perfil.peso_kg * DIAS_SEMANA,
            perfil.proteina_max_g_kg_dia * perfil.peso_kg * DIAS_SEMANA,
        ),
        "grasas_g": BandaNutriente(
            kcal_sem * perfil.grasas_min_pct_e / 100.0 / KCAL_POR_G_GRASA,
            kcal_sem * perfil.grasas_max_pct_e / 100.0 / KCAL_POR_G_GRASA,
        ),
        "grasas_sat_g": BandaNutriente(
            None, kcal_sem * perfil.grasas_sat_max_pct_e / 100.0 / KCAL_POR_G_GRASA
        ),
        "hidratos_g": BandaNutriente(
            kcal_sem * perfil.hidratos_min_pct_e / 100.0 / KCAL_POR_G_HIDRATO,
            kcal_sem * perfil.hidratos_max_pct_e / 100.0 / KCAL_POR_G_HIDRATO,
        ),
        "azucares_g": BandaNutriente(
            None, kcal_sem * perfil.azucares_max_pct_e / 100.0 / KCAL_POR_G_HIDRATO
        ),
        "fibra_g": BandaNutriente(perfil.fibra_min_g_dia * DIAS_SEMANA, None),
        "sal_g": BandaNutriente(None, perfil.sal_max_g_dia * DIAS_SEMANA),
    }


def perfil_desde_config(cfg: dict) -> PerfilNutricional:
    """Construye el perfil desde la seccion `nutricion` de config.yaml."""
    nutricion = (cfg.get("nutricion") or {}) if cfg else {}
    campos = {f: nutricion[f] for f in PerfilNutricional.__dataclass_fields__ if f in nutricion}
    return PerfilNutricional(**campos)
