"""Exporta el catalogo desde SQLite a un CSV rico (con nutricion ya enriquecida).

A diferencia del CSV de la Fase 1 (solo listado), este incluye las columnas
nutricionales restauradas -- las que SI se pueden obtener de Alcampo (endpoint
`bop`): energia, grasas, hidratos, azucares, proteinas, sal, fibra,
ingredientes y origen. EAN / Nutri-Score / NOVA / alergenos NO se incluyen aun
porque Alcampo no los da; se añadiran cuando se cruce con Open Food Facts.
"""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd
import yaml

from .db import get_connection

# Orden de columnas del CSV rico. Los booleanos y las etiquetas se formatean
# despues; los numericos van con coma decimal.
_COLUMNAS_SQL = [
    "nombre",
    "marca",
    "categoria",
    "subcategoria",
    "apto_receta",
    "precio_eur",
    "precio_por_unidad",
    "unidad_medida",
    "formato",
    "disponible",
    "energia_kcal_100g",
    "grasas_100g",
    "grasas_sat_100g",
    "hidratos_100g",
    "azucares_100g",
    "proteinas_100g",
    "sal_100g",
    "fibra_100g",
    "base_nutricional",
    "ingredientes",
    "origen",
    "ean",
    "nutri_score",
    "nova",
    "alergenos",
    "url_producto",
    "url_imagen",
    "en_oferta",
    "precio_oferta",
    "fecha_extraccion",
]


def exportar_csv(db_path: str | Path, output_path: str | Path, solo_aptos: bool = False) -> int:
    conn = get_connection(db_path)
    try:
        sql = f"SELECT {', '.join(_COLUMNAS_SQL)} FROM productos"
        if solo_aptos:
            sql += " WHERE apto_receta = 1"
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()

    # Booleanos -> si/no legibles.
    df["apto_receta"] = df["apto_receta"].map({1: "si", 0: "no"})
    df["disponible"] = df["disponible"].map({1: "disponible", 0: "no_disponible"})
    df = df.rename(columns={"disponible": "disponibilidad"})
    df["en_oferta"] = df["en_oferta"].map({1: "si", 0: "no"}).rename("oferta")
    df = df.rename(columns={"en_oferta": "oferta"})

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # decimal="," -> coma decimal en todos los numericos; utf-8-sig -> BOM.
    df.to_csv(output_path, sep=";", index=False, encoding="utf-8-sig", decimal=",")
    return len(df)


@click.command()
@click.option("--config", "config_path", default="config.yaml", type=click.Path(path_type=Path))
@click.option("--db", "db_path", default=None, type=click.Path(path_type=Path))
@click.option("--output", "output_path", default="data/catalogo_alcampo.csv", type=click.Path(path_type=Path))
@click.option("--solo-aptos", is_flag=True, help="Exporta solo productos aptos para receta.")
def main(config_path: Path, db_path: Path | None, output_path: Path, solo_aptos: bool) -> None:
    """Exporta el catalogo de SQLite a un CSV rico (con nutricion)."""
    cfg = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    db_path = db_path or Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))

    total = exportar_csv(db_path, output_path, solo_aptos=solo_aptos)
    click.echo(f"CSV exportado en {output_path} con {total} productos.")


if __name__ == "__main__":
    main()
