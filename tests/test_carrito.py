"""Tests de la logica pura del prototipo de carrito (sin navegador real)."""

from __future__ import annotations

from menu_app.carrito.alcampo import (
    BASE_URL,
    _SEL_DECREMENTO,
    _SEL_INCREMENTO,
    ResultadoCarrito,
    ResultadoLinea,
    _normalizar_lineas,
    _url_producto,
    anadir_al_carrito,
)
from menu_app.optimizacion.compra import LineaCompra


def test_url_producto_fallback_y_dada():
    assert _url_producto("511281", None) == f"{BASE_URL}/products/producto/511281"
    assert _url_producto("50043", "https://x/50043") == "https://x/50043"


def test_normalizar_desde_lineacompra():
    l = LineaCompra(
        producto_id="511281",
        nombre="GOYA Aji amarillo",
        url=None,
        gramos_necesarios=500,
        formato_g_ml=500,
        unidades=2,
        precio_unidad=3.5,
        total=7.0,
    )
    out = _normalizar_lineas([l])
    assert len(out) == 1
    assert out[0].producto_id == "511281"
    assert out[0].unidades == 2


def test_normalizar_desde_dict_y_minimo_una_unidad():
    out = _normalizar_lineas(
        [
            {"producto_id": "50043", "nombre": "X", "unidades": 0},  # se sube a 1
            {"retailer_product_id": "60000", "unidades": 3},  # nombre alterno
            {"nombre": "sin id"},  # se descarta (sin producto_id)
        ]
    )
    assert [(x.producto_id, x.unidades) for x in out] == [("50043", 1), ("60000", 3)]


def test_resultado_carrito_ok_y_conteo():
    r = ResultadoCarrito(
        dry_run=True,
        lineas=[
            ResultadoLinea("1", "a", 1, True, "ok"),
            ResultadoLinea("2", "b", 2, False, "sin boton"),
        ],
    )
    assert r.n_ok == 1
    assert r.ok is False
    assert ResultadoCarrito(dry_run=True).ok is False  # sin lineas no es "ok"


def test_selector_decremento_es_espejo_del_incremento():
    # Ambos confirmados en vivo: "Aumentar/Reducir la cantidad de {producto}...".
    assert _SEL_INCREMENTO.startswith('button[aria-label^="Aumentar la cantidad"')
    assert _SEL_DECREMENTO.startswith('button[aria-label^="Reducir la cantidad"')


def test_anadir_al_carrito_acepta_sincronizar_y_vaciar_antes_sin_navegador():
    # Ruta rapida (sin items): no debe intentar abrir el navegador ni fallar por
    # los parametros nuevos (#54/#55), solo por la lista vacia.
    res = anadir_al_carrito([], sincronizar=True, vaciar_antes=True)
    assert res.lineas == []
