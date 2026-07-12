from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from .models import CSV_FIELDNAMES, Product


def write_catalog_csv(products: Iterable[Product], output_path: str | Path) -> int:
    """Escribe el catalogo en UTF-8 con BOM y ';' como separador, tal como pide
    el formato de salida acordado (para que Excel en Windows lo abra bien).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, delimiter=";")
        writer.writeheader()
        for product in products:
            writer.writerow(product.to_csv_row())
            count += 1
    return count
