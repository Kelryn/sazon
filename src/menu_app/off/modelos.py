from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DatosOFF:
    """Datos traidos de Open Food Facts para un producto de Alcampo.

    Son justo los campos que Alcampo NO da y que se cruzan por nombre+marca
    (no hay EAN en Alcampo): codigo de barras, Nutri-Score, grupo NOVA y
    alergenos. `match_score` es la similitud (0-100) del match, para poder
    filtrar/auditar la calidad del cruce.
    """

    ean: str | None
    nutri_score: str | None  # 'a'..'e'
    nova: int | None  # 1..4
    alergenos: str | None
    off_product_name: str | None
    match_score: float
