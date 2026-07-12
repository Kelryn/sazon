from __future__ import annotations

import sqlite3

import pandas as pd


def resumen_por_categoria(conn: sqlite3.Connection) -> pd.DataFrame:
    """Tabla resumen por categoria raiz: nº productos, % apto para receta,
    precio medio y cuantos en oferta. Pensado para revisar de un vistazo la
    carga y el efecto del filtro de aptitud para receta.
    """
    df = pd.read_sql_query(
        "SELECT categoria, apto_receta, en_oferta, precio_eur FROM productos", conn
    )
    if df.empty:
        return df

    resumen = (
        df.groupby("categoria")
        .agg(
            productos=("categoria", "size"),
            aptos_receta=("apto_receta", "sum"),
            en_oferta=("en_oferta", "sum"),
            precio_medio=("precio_eur", "mean"),
        )
        .reset_index()
    )
    resumen["pct_aptos"] = (100 * resumen["aptos_receta"] / resumen["productos"]).round(0)
    resumen["precio_medio"] = resumen["precio_medio"].round(2)
    return resumen.sort_values("productos", ascending=False)
