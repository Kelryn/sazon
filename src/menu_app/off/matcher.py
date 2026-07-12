"""Empareja un producto de Alcampo con el mejor candidato de Open Food Facts.

Sin EAN, el match es por similitud de texto (nombre + marca) con RapidFuzz.
Solo se acepta si supera un umbral, para no meter datos nutricionales de un
producto que en realidad es otro. El umbral es conservador a proposito: es
mejor quedarse sin dato que con un dato equivocado.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz

from .modelos import DatosOFF

UMBRAL_MATCH = 82.0

# Palabras de formato/relleno que no ayudan a distinguir el producto.
_RUIDO = re.compile(
    r"\b(\d+[.,]?\d*\s*(g|gr|kg|ml|l|cl|ud|uds|unidades|piezas|x))\b|\bpack\b|\blata\b|\bbrick\b|\bbotella\b|\benvase\b",
    re.IGNORECASE,
)


def _normalizar(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    sin = _RUIDO.sub(" ", sin.lower())
    return re.sub(r"\s+", " ", sin).strip()


def texto_busqueda(nombre: str, marca: str | None) -> str:
    """Texto que se manda a OFF: marca + nombre, sin ruido de formato ni palabras
    repetidas (la marca suele venir ya dentro del nombre, p.ej. "POLO Fartons")."""
    partes = [p for p in [marca, nombre] if p]
    palabras = _normalizar(" ".join(partes)).split()
    return " ".join(dict.fromkeys(palabras))


def _similitud(consulta: str, candidato: dict[str, Any]) -> float:
    objetivo = _normalizar(f"{candidato.get('brands', '')} {candidato.get('product_name', '')}")
    if not objetivo:
        return 0.0
    # token_set_ratio tolera orden y palabras de mas (marca repetida, formato...).
    return fuzz.token_set_ratio(consulta, objetivo)


def _limpiar_alergenos(tags: list[str] | None) -> str | None:
    if not tags:
        return None
    # ["en:milk", "es:leche"] -> "milk, leche" (quita el prefijo de idioma).
    vals = [t.split(":", 1)[-1].replace("-", " ") for t in tags]
    return ", ".join(dict.fromkeys(vals)) or None


def _valor_o_none(v: Any) -> Any:
    if v in (None, "", "unknown", "not-applicable", "undefined"):
        return None
    return v


def mejor_match(
    nombre: str, marca: str | None, candidatos: list[dict[str, Any]], umbral: float = UMBRAL_MATCH
) -> DatosOFF | None:
    """Devuelve los DatosOFF del mejor candidato si supera el umbral, o None."""
    consulta = texto_busqueda(nombre, marca)
    if not consulta or not candidatos:
        return None

    mejor = None
    mejor_score = 0.0
    for c in candidatos:
        score = _similitud(consulta, c)
        if score > mejor_score:
            mejor_score = score
            mejor = c

    if mejor is None or mejor_score < umbral:
        return None

    nova = _valor_o_none(mejor.get("nova_group"))
    return DatosOFF(
        ean=_valor_o_none(mejor.get("code")),
        nutri_score=_valor_o_none(mejor.get("nutriscore_grade")),
        nova=int(nova) if nova is not None else None,
        alergenos=_limpiar_alergenos(mejor.get("allergens_tags")),
        off_product_name=mejor.get("product_name"),
        match_score=round(mejor_score, 1),
    )
