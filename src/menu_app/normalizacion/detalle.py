"""Parsea el JSON de detalle de producto (endpoint `bop`) a campos limpios.

El detalle trae, para productos envasados, tablas HTML con la informacion
nutricional (por 100 g o 100 ml), los ingredientes y una tabla de
caracteristicas de la que sacamos el origen. Los productos frescos a granel
(fruta/verdura suelta) normalmente no traen estas tablas: en ese caso los
campos quedan a None y ya se completaran, si acaso, con Open Food Facts.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass
class DetalleProducto:
    energia_kcal_100g: float | None = None
    grasas_100g: float | None = None
    grasas_sat_100g: float | None = None
    hidratos_100g: float | None = None
    azucares_100g: float | None = None
    proteinas_100g: float | None = None
    sal_100g: float | None = None
    fibra_100g: float | None = None
    ingredientes: str | None = None
    origen: str | None = None
    base_nutricional: str | None = None  # "100g" | "100ml" | None

    def tiene_nutricion(self) -> bool:
        return any(
            v is not None
            for v in (
                self.energia_kcal_100g,
                self.grasas_100g,
                self.hidratos_100g,
                self.proteinas_100g,
            )
        )


def _norm(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin.lower().strip()


def _num(texto: str) -> float | None:
    m = _NUM.search(texto.replace(",", "."))
    return float(m.group()) if m else None


def _campo(bop_data: dict[str, Any], titulo: str) -> str | None:
    for f in bop_data.get("fields", []):
        if f.get("title") == titulo:
            return f.get("content")
    return None


def parsear_detalle(bop_json: dict[str, Any]) -> DetalleProducto:
    detalle = DetalleProducto()
    bop_data = bop_json.get("bopData") or {}

    _parsear_nutricion(_campo(bop_data, "nutritionalData"), detalle)
    detalle.ingredientes = _parsear_ingredientes(_campo(bop_data, "ingredients"))
    detalle.origen = _parsear_origen(_campo(bop_data, "features"))
    return detalle


def _parsear_nutricion(html: str | None, detalle: DetalleProducto) -> None:
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")

    # La base ("100g"/"100ml") esta en la cabecera "Valores medios por: 100g".
    cabecera = " ".join(th.get_text(" ", strip=True) for th in soup.find_all("th"))
    if "100ml" in cabecera.replace(" ", "").lower():
        detalle.base_nutricional = "100ml"
    elif "100g" in cabecera.replace(" ", "").lower():
        detalle.base_nutricional = "100g"

    for fila in soup.find_all("tr"):
        celdas = fila.find_all(["td", "th"])
        if len(celdas) < 2:
            continue
        etiqueta = _norm(celdas[0].get_text(" ", strip=True))
        valor_txt = celdas[1].get_text(" ", strip=True)
        if not etiqueta or not valor_txt:
            continue

        if "kcal" in etiqueta:
            detalle.energia_kcal_100g = _num(valor_txt)
        elif "satur" in etiqueta:
            detalle.grasas_sat_100g = _num(valor_txt)
        elif "grasa" in etiqueta:
            detalle.grasas_100g = _num(valor_txt)
        elif "azucar" in etiqueta:
            detalle.azucares_100g = _num(valor_txt)
        elif "hidrato" in etiqueta:
            detalle.hidratos_100g = _num(valor_txt)
        elif "fibra" in etiqueta:
            detalle.fibra_100g = _num(valor_txt)
        elif "proteina" in etiqueta:
            detalle.proteinas_100g = _num(valor_txt)
        elif etiqueta == "sal" or etiqueta.startswith("sal "):
            detalle.sal_100g = _num(valor_txt)


def _parsear_ingredientes(html: str | None) -> str | None:
    if not html:
        return None
    texto = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    texto = re.sub(r"^\s*ingredientes\s*:?\s*", "", texto, flags=re.IGNORECASE)
    return texto.strip() or None


def _parsear_origen(html: str | None) -> str | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    pais = None
    denominacion = None
    for fila in soup.find_all("tr"):
        celdas = fila.find_all(["td", "th"])
        if len(celdas) < 2:
            continue
        clave = _norm(celdas[0].get_text(" ", strip=True))
        valor = celdas[1].get_text(" ", strip=True)
        if not valor:
            continue
        if "pais de origen" in clave:
            pais = valor
        elif "denominacion de origen" in clave:
            denominacion = valor
    return pais or denominacion
