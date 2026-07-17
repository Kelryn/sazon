"""Tareas de fondo de la interfaz web y su estado (Lote 9, #86: extraido de app.py).

Cada tarea (actualizar catalogo, enviar al carrito, instalar Chromium, comprobar
actualizaciones) tarda demasiado para bloquear una peticion HTTP: se lanza en un
hilo daemon y su progreso/resultado se guarda en un dict de modulo que las
paginas consultan en cada recarga (no hay websockets ni sondeo con JS).
"""

from __future__ import annotations

import html
import threading
from collections import deque
from pathlib import Path

from ..actualizaciones import _es_ejecutable_congelado, hay_actualizacion, pre_descargar
from ..almacenamiento.actualizar import actualizar_catalogo, dias_desde_ultima_actualizacion
from ..almacenamiento.db import get_connection, init_db
from ..carrito import anadir_al_carrito, instalar_chromium, playwright_disponible
from ..configuracion import cargar_config
from ..optimizacion.compra import lista_compra
from ..optimizacion.economia_recetas import invalidar_cache as invalidar_cache_recetas
from ..version import __version__

# ------------------------- tarea de catalogo en 2º plano -------------------------

_CATALOGO = {"activa": False, "log": deque(maxlen=300), "resumen": ""}

# Estado del envio de la compra al carrito de Alcampo (en 2º plano).
_CARRITO = {"activa": False, "log": deque(maxlen=400), "resumen": ""}
# Instalacion bajo demanda de Chromium (#78): navegador de respaldo si no hay Chrome/Edge.
_CHROMIUM = {"instalando": False, "log": deque(maxlen=200), "resumen": ""}


def _lanzar_instalar_chromium() -> bool:
    if _CHROMIUM["instalando"]:
        return False
    _CHROMIUM["instalando"] = True
    _CHROMIUM["log"].clear()
    _CHROMIUM["resumen"] = ""

    def _correr():
        try:
            ok, msg = instalar_chromium(log=_CHROMIUM["log"].append)
            _CHROMIUM["resumen"] = msg
        except Exception as e:  # noqa: BLE001
            _CHROMIUM["resumen"] = f"Error: {e}"
        finally:
            _CHROMIUM["instalando"] = False

    threading.Thread(target=_correr, daemon=True).start()
    return True

# Estado de la comprobacion de actualizaciones (Fase 11): None = sin comprobar,
# False = comprobado y al dia, InfoActualizacion = hay version nueva.
# "descarga": ruta ya predescargada en 2º plano (#75), o None si aun no.
_ACTUALIZACION = {"estado": None, "comprobado": False, "descarga": None, "descargando": False}


def _comprobar_actualizacion(canal: str = "estable") -> None:
    """Consulta GitHub (una vez, repo fijo) y guarda el resultado en cache. Si hay
    version nueva, lanza la PRE-DESCARGA en 2º plano (#75): asi "Instalar" es
    instantaneo despues (no espera a bajar el fichero)."""
    info = hay_actualizacion(canal=canal)
    _ACTUALIZACION["estado"] = info
    _ACTUALIZACION["comprobado"] = True
    if info and info.es_instalador and _es_ejecutable_congelado():
        def _predescargar():
            _ACTUALIZACION["descargando"] = True
            try:
                _ACTUALIZACION["descarga"] = pre_descargar(info)
            except Exception:  # noqa: BLE001 - se reintenta al pulsar "Instalar"
                pass
            finally:
                _ACTUALIZACION["descargando"] = False
        threading.Thread(target=_predescargar, daemon=True).start()


def _banner_actualizacion() -> str:
    """Banner (en todas las paginas) si hay una version nueva disponible, con el
    changelog de la release visible (#76) y el estado de la pre-descarga (#75)."""
    info = _ACTUALIZACION["estado"]
    if not info:
        return ""
    estado_descarga = (
        " (descargando en 2º plano…)" if _ACTUALIZACION["descargando"]
        else " (lista para instalar)" if _ACTUALIZACION["descarga"] else ""
    )
    changelog = (
        f'<details style="margin-top:6px"><summary class="meta">Ver novedades</summary>'
        f'<pre class="log" style="white-space:pre-wrap">{html.escape(info.notas[:2000])}</pre></details>'
        if info.notas else ""
    )
    beta = ' <span class="chip">beta</span>' if info.es_beta else ""
    return (
        f'<div class="card" style="border-left:4px solid var(--dorado)">'
        f'✨ <b>Nueva versión disponible: {html.escape(info.version)}</b>{beta} '
        f'(tienes la {__version__}){estado_descarga}. '
        f'<form method="post" action="/actualizaciones/comprobar" style="display:inline">'
        f'<button class="btn mini" type="submit">Instalar</button></form>'
        f"{changelog}</div>"
    )


def _lanzar_actualizacion(cfg: dict, categorias: list[str] | None = None) -> bool:
    if _CATALOGO["activa"]:
        return False
    _CATALOGO["activa"] = True
    _CATALOGO["log"].clear()
    _CATALOGO["resumen"] = ""

    def _correr():
        try:
            resumen = actualizar_catalogo(
                cfg, progreso=_CATALOGO["log"].append, categorias=categorias
            )
            invalidar_cache_recetas()  # precios nuevos -> recalcular coste de recetas (#34)
            _CATALOGO["resumen"] = (
                f"Catálogo actualizado: {resumen['procesados']} productos, "
                f"{resumen['nuevos']} nuevos, {resumen['cambios_precio']} cambios de precio."
            )
        except Exception as e:  # noqa: BLE001 - se muestra al usuario
            _CATALOGO["log"].append(f"ERROR: {e}")
            _CATALOGO["resumen"] = f"Falló la actualización: {e}"
        finally:
            _CATALOGO["activa"] = False

    threading.Thread(target=_correr, daemon=True).start()
    return True


# Antigüedad del catálogo detectada al arrancar (#116): None = aun sin comprobar.
_CATALOGO_ANTIGUEDAD: dict = {"dias": None}


def comprobar_catalogo_desactualizado(cfg: dict) -> None:
    """Comprueba al arrancar cuantos dias lleva el catalogo sin actualizarse
    (#116). Si supera `catalogo_dias_alerta` (7 por defecto) y
    `catalogo_auto_actualizar` esta activado, lanza la actualizacion sola en 2º
    plano; si no, solo lo guarda para mostrar un aviso en el menu."""
    db_path = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(db_path)
    try:
        init_db(conn)
        dias = dias_desde_ultima_actualizacion(conn)
    finally:
        conn.close()
    _CATALOGO_ANTIGUEDAD["dias"] = dias
    umbral = int(cfg.get("catalogo_dias_alerta", 7) or 7)
    if dias is not None and dias >= umbral and cfg.get("catalogo_auto_actualizar", False):
        _lanzar_actualizacion(cfg)


def _lanzar_carrito(config_path, sincronizar: bool = False, vaciar_antes: bool = False) -> tuple[bool, str]:
    """Envia la compra del plan al carrito de Alcampo en 2º plano (abre el navegador)."""
    if _CARRITO["activa"]:
        return False, "Ya hay un envío en marcha."
    if not playwright_disponible():
        return False, (
            "Falta el navegador automatizado. Instálalo una vez: "
            "uv sync --extra playwright && uv run playwright install chromium"
        )
    cfg = cargar_config(config_path)
    db = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
    conn = get_connection(db)
    init_db(conn)
    compra = lista_compra(conn, despensa=cfg.get("despensa"))
    conn.close()
    if not compra.lineas:
        return False, "El plan no tiene lista de la compra (genera antes un menú)."

    _CARRITO["activa"] = True
    _CARRITO["log"].clear()
    _CARRITO["resumen"] = ""
    lineas = list(compra.lineas)

    def _correr():
        try:
            res = anadir_al_carrito(
                lineas, dry_run=False, headless=False, log=_CARRITO["log"].append,
                sincronizar=sincronizar, vaciar_antes=vaciar_antes,
            )
            _CARRITO["resumen"] = (
                f"Enviados {res.n_ok}/{len(res.lineas)} productos al carrito. "
                f"Total de la cesta: {res.total_cesta or '—'}."
            )
        except Exception as e:  # noqa: BLE001 - se muestra al usuario
            _CARRITO["log"].append(f"ERROR: {e}")
            _CARRITO["resumen"] = f"Falló el envío: {e}"
        finally:
            _CARRITO["activa"] = False

    threading.Thread(target=_correr, daemon=True).start()
    return True, "Enviando la compra a Alcampo. Inicia sesión en la ventana que se abre."
