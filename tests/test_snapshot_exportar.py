"""Test de snapshot (Lote 9, #96): fija el CSV EXACTO de la lista de la compra,
byte a byte, no solo que contenga ciertas subcadenas. Cualquier cambio no
intencionado de formato (orden de columnas, separador, redondeo, encoding)
rompe este test aunque las columnas sigan "conteniendo" lo esperado.
"""

from __future__ import annotations

from menu_app.optimizacion.compra import Compra, LineaCompra
from menu_app.optimizacion.exportar import compra_a_csv

_SNAPSHOT_CSV = (
    "Pasillo,Producto,Unidades,Cantidad necesaria,€/ud,Total €,Enlace\r\n"
    "Aceites,Aceite oliva 1 l,1,400 g,3.99,3.99,http://b\r\n"
    "Legumbres,Lentejas 1 kg,1,500 g,1.20,1.20,http://a\r\n"
    "\r\n"
    ",,,,,TOTAL 5.19,\r\n"
)


def test_snapshot_compra_a_csv():
    compra = Compra(
        plan_id="plan-x", semanas=2,
        lineas=[
            LineaCompra("P1", "Lentejas 1 kg", "http://a", 500, 1000, 1, 1.2, 1.2, "Legumbres"),
            LineaCompra("P2", "Aceite oliva 1 l", "http://b", 400, 1000, 1, 3.99, 3.99, "Aceites"),
        ],
    )
    data = compra_a_csv(compra).decode("utf-8-sig")
    assert data == _SNAPSHOT_CSV
