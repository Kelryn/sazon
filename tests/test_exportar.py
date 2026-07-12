"""Tests de exportacion a CSV y PDF (Fase 7)."""

from __future__ import annotations

from menu_app.optimizacion.compra import Compra, LineaCompra
from menu_app.optimizacion.exportar import (
    compra_a_csv,
    compra_a_pdf,
    menu_a_csv,
    menu_a_pdf,
)


def _compra():
    return Compra(
        plan_id="plan-x", semanas=2,
        lineas=[
            LineaCompra("P1", "Lentejas 1 kg", "http://a", 500, 1000, 1, 1.2, 1.2, "Legumbres"),
            LineaCompra("P2", "Aceite oliva 1 l", "http://b", 400, 1000, 1, 3.99, 3.99, "Aceites"),
        ],
    )


def _semanas():
    return {
        1: {
            "factible": True, "dias": 3, "dias_bc": ["lun"], "coste_total": 20.0,
            "seleccion_comida": {"a": 1, "b": 2}, "seleccion_cena": {"c": 3},
            "seleccion_comida_bc": {"a": 1},
            "recetas_info": {"a": {"titulo": "Guiso"}, "b": {"titulo": "Arroz"}, "c": {"titulo": "Sopa"}},
        }
    }


def test_compra_csv_tiene_pasillos_y_total():
    data = compra_a_csv(_compra()).decode("utf-8-sig")
    assert "Legumbres" in data and "Aceites" in data
    assert "Lentejas 1 kg" in data and "TOTAL 5.19" in data


def test_menu_csv_lista_dias_y_franjas():
    data = menu_a_csv(_semanas()).decode("utf-8-sig")
    assert "Comida" in data and "Cena" in data and "Guiso" in data


def test_pdfs_son_pdf_validos():
    assert compra_a_pdf(_compra())[:5] == b"%PDF-"
    assert menu_a_pdf(_semanas())[:5] == b"%PDF-"


def test_compra_por_pasillo_agrupa():
    grupos = _compra().por_pasillo()
    assert set(grupos) == {"Legumbres", "Aceites"}
    assert grupos["Legumbres"][0].nombre == "Lentejas 1 kg"
