"""Tests de copias de seguridad (#80): crear, listar, purgar, restaurar."""

from __future__ import annotations

from menu_app.backups import crear_backup, listar_backups, restaurar_backup


def test_crear_backup_sin_bd_devuelve_none(tmp_path):
    assert crear_backup(tmp_path / "no-existe.db") is None


def test_crear_y_listar_backup(tmp_path):
    db = tmp_path / "menu.db"
    db.write_bytes(b"contenido de la base de datos")
    ruta = crear_backup(db)
    assert ruta is not None
    assert ruta.exists()
    backups = listar_backups(db)
    assert len(backups) == 1
    assert backups[0].ruta == ruta


def test_incluye_config_usuario_si_existe(tmp_path):
    db = tmp_path / "menu.db"
    db.write_bytes(b"datos")
    cfg_usuario = tmp_path / "config.usuario.yaml"
    cfg_usuario.write_text("sabor_pct: 80\n", encoding="utf-8")
    ruta = crear_backup(db, cfg_usuario)
    import zipfile
    with zipfile.ZipFile(ruta) as z:
        assert set(z.namelist()) == {"menu.db", "config.usuario.yaml"}


def test_purga_backups_antiguos(tmp_path):
    db = tmp_path / "menu.db"
    db.write_bytes(b"v1")
    for _ in range(5):
        crear_backup(db, max_backups=3)
        db.write_bytes(db.read_bytes() + b"x")  # cambia el contenido para variar
    backups = listar_backups(db)
    assert len(backups) == 3  # se purgan los mas antiguos


def test_restaurar_backup_recupera_contenido(tmp_path):
    db = tmp_path / "menu.db"
    db.write_bytes(b"contenido ORIGINAL")
    ruta = crear_backup(db)
    db.write_bytes(b"contenido CORRUPTO")  # simula un desastre
    restaurar_backup(ruta, db)
    assert db.read_bytes() == b"contenido ORIGINAL"


def test_restaurar_hace_backup_de_seguridad_antes(tmp_path):
    db = tmp_path / "menu.db"
    db.write_bytes(b"v1")
    ruta1 = crear_backup(db)
    db.write_bytes(b"v2 (mal estado)")
    restaurar_backup(ruta1, db)
    # Debe existir un backup adicional del estado "v2" tomado justo antes de restaurar.
    backups = listar_backups(db)
    assert len(backups) >= 2
