"""Tests de minimizar desperdicio: perecederos al final de la lista (#105)."""

from __future__ import annotations

from menu_app.optimizacion.compra import Compra, LineaCompra, es_pasillo_perecedero


def test_reconoce_pasillos_perecederos():
    assert es_pasillo_perecedero("Verduras y hortalizas") is True
    assert es_pasillo_perecedero("Carne") is True
    assert es_pasillo_perecedero("Pescados, mariscos y moluscos") is True
    assert es_pasillo_perecedero("Quesos") is True
    assert es_pasillo_perecedero("Panadería") is True


def test_no_marca_pasillos_no_perecederos():
    assert es_pasillo_perecedero("Legumbres") is False
    assert es_pasillo_perecedero("Aceites") is False
    assert es_pasillo_perecedero("Conservas") is False


def test_por_pasillo_pone_los_perecederos_al_final():
    compra = Compra(
        plan_id="p", semanas=1,
        lineas=[
            LineaCompra("P1", "Lentejas", "http://a", 500, 1000, 1, 1.0, 1.0, "Legumbres"),
            LineaCompra("P2", "Cebolla", "http://b", 500, 1000, 1, 1.0, 1.0, "Verduras y hortalizas"),
            LineaCompra("P3", "Aceite", "http://c", 500, 1000, 1, 1.0, 1.0, "Aceites"),
            LineaCompra("P4", "Pollo", "http://d", 500, 1000, 1, 1.0, 1.0, "Carne"),
        ],
    )
    orden = list(compra.por_pasillo())
    # Los perecederos (Verduras, Carne) van despues de los no perecederos
    # (Aceites, Legumbres), sea cual sea el orden alfabetico de cada grupo.
    idx_no_perecederos = [orden.index("Aceites"), orden.index("Legumbres")]
    idx_perecederos = [orden.index("Verduras y hortalizas"), orden.index("Carne")]
    assert max(idx_no_perecederos) < min(idx_perecederos)
