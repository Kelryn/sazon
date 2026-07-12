from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.almacenamiento.modelos import ProductoNormalizado
from menu_app.almacenamiento.repositorio import ProductoRepository


def _norm(rpid: str, precio: float | None, apto: bool = True) -> ProductoNormalizado:
    return ProductoNormalizado(
        retailer_product_id=rpid,
        nombre=f"Producto {rpid}",
        marca="MARCA",
        categoria="Frescos",
        subcategoria="Frutas",
        precio_eur=precio,
        precio_por_unidad=precio,
        unidad_medida="kg",
        formato="1 kg",
        cantidad_formato=1.0,
        unidad_formato="kg",
        cantidad_base_g_ml=1000.0,
        tipo_medida="peso",
        disponible=True,
        en_oferta=False,
        precio_oferta=None,
        url_producto=f"https://x/{rpid}",
        url_imagen=None,
        apto_receta=apto,
        fecha_extraccion="2026-07-09",
    )


@pytest.fixture
def repo(tmp_path: Path) -> ProductoRepository:
    conn = get_connection(tmp_path / "test.db")
    init_db(conn)
    return ProductoRepository(conn)


def test_upsert_inserta_nuevos(repo):
    resumen = repo.upsert_muchos(
        [_norm("1", 1.0), _norm("2", 2.0)], fecha_actualizacion="2026-07-09T10:00:00"
    )
    assert resumen == {"procesados": 2, "nuevos": 2, "cambios_precio": 0}
    assert repo.contar() == 2


def test_upsert_es_idempotente_por_id(repo):
    repo.upsert_muchos([_norm("1", 1.0)], "2026-07-09T10:00:00")
    resumen = repo.upsert_muchos([_norm("1", 1.0)], "2026-07-09T11:00:00")

    assert repo.contar() == 1  # no se duplica
    assert resumen["nuevos"] == 0
    assert resumen["cambios_precio"] == 0


def test_upsert_detecta_cambio_de_precio_y_lo_historifica(repo):
    repo.upsert_muchos([_norm("1", 1.0)], "2026-07-09T10:00:00")
    resumen = repo.upsert_muchos([_norm("1", 1.5)], "2026-07-10T10:00:00")

    assert resumen["cambios_precio"] == 1
    historico = repo.conn.execute(
        "SELECT fecha, precio_eur FROM precios_historico WHERE retailer_product_id = '1' "
        "ORDER BY fecha"
    ).fetchall()
    assert [(r["precio_eur"]) for r in historico] == [1.0, 1.5]


def test_contar_por_apto(repo):
    repo.upsert_muchos(
        [_norm("1", 1.0, apto=True), _norm("2", 2.0, apto=False), _norm("3", 3.0, apto=True)],
        "2026-07-09T10:00:00",
    )
    por_apto = repo.contar_por_apto()
    assert por_apto[True] == 2
    assert por_apto[False] == 1
    assert repo.contar(solo_aptos=True) == 2
