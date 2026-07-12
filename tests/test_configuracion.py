"""Tests de la carga de config con overlay de usuario."""

from __future__ import annotations

from menu_app.configuracion import (
    cargar_config,
    dias_batchcooking,
    guardar_overlay,
    ruta_overlay,
)


def _base(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "num_comensales: 2\nkcal_por_comensal: 2000\n"
        "batchcooking:\n  fraccion_batchcooking_espanolas_min: 0.5\n  dias: []\n",
        encoding="utf-8",
    )
    return cfg


def test_sin_overlay_devuelve_base(tmp_path):
    cfg = _base(tmp_path)
    datos = cargar_config(cfg)
    assert datos["num_comensales"] == 2
    assert dias_batchcooking(datos) == []


def test_overlay_gana_y_fusiona_subdicts(tmp_path):
    cfg = _base(tmp_path)
    guardar_overlay(cfg, {"num_comensales": 4, "batchcooking": {"dias": ["lun", "mie"]}})
    datos = cargar_config(cfg)
    assert datos["num_comensales"] == 4  # overlay gana
    assert datos["kcal_por_comensal"] == 2000  # base se conserva
    # el sub-dict se fusiona: dias del overlay + fraccion del base
    assert dias_batchcooking(datos) == ["lun", "mie"]
    assert datos["batchcooking"]["fraccion_batchcooking_espanolas_min"] == 0.5


def test_guardar_dos_veces_acumula(tmp_path):
    cfg = _base(tmp_path)
    guardar_overlay(cfg, {"num_comensales": 4})
    guardar_overlay(cfg, {"peso_favorita": 6.0})
    datos = cargar_config(cfg)
    assert datos["num_comensales"] == 4 and datos["peso_favorita"] == 6.0


def test_dias_se_ordenan_como_la_semana(tmp_path):
    cfg = _base(tmp_path)
    guardar_overlay(cfg, {"batchcooking": {"dias": ["vie", "lun"]}})
    assert dias_batchcooking(cargar_config(cfg)) == ["lun", "vie"]


def test_borrar_overlay_resetea(tmp_path):
    cfg = _base(tmp_path)
    guardar_overlay(cfg, {"num_comensales": 4})
    ruta_overlay(cfg).unlink()
    assert cargar_config(cfg)["num_comensales"] == 2
