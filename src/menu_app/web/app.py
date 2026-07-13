"""Interfaz web local (FastAPI) del generador de menu — Fase 6.

Un servidor ligero que se abre en el navegador. Todo el HTML/CSS va embebido (sin
CDN ni recursos externos) para que funcione sin conexion y se empaquete limpio a
.exe con PyInstaller (Fase 8). Reutiliza los mismos servicios que el CLI.

Paginas:
  /               plan de menus por semanas (flechas), nutrientes por dia,
                  alternativa y cambio de recetas
  /receta/{id}    detalle de una receta: ingredientes con precio de Alcampo
  /recetas        alta de recetas manuales y gestion de favoritas
  /compra         lista de la compra del plan (estilo recibo, enlaces a Alcampo)
  /catalogo       descarga/actualizacion del catalogo de Alcampo
  /config         configuracion (guarda en config.usuario.yaml)
"""

from __future__ import annotations

import html
import threading
from collections import deque
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..actualizaciones import hay_actualizacion, instalar
from ..carrito import anadir_al_carrito, playwright_disponible
from ..almacenamiento.actualizar import actualizar_catalogo
from ..almacenamiento.db import get_connection, init_db
from ..version import __version__
from ..ingesta.categories import FOOD_CATEGORY_ROOTS
from ..configuracion import DIAS_SEMANA, cargar_config, guardar_overlay
from ..optimizacion.compra import lista_compra
from ..optimizacion.exportar import (
    compra_a_csv,
    compra_a_pdf,
    menu_a_csv,
    menu_a_pdf,
)
from ..optimizacion.economia_recetas import _FACTOR_PRECIO, _gramos_por_piezas
from ..optimizacion.nutrientes import objetivos_semanales
from ..optimizacion.planes import asignar_dias, cargar_plan, generar_plan, regenerar_semana
from ..optimizacion.servicio import _PESOS_PCT, config_nutricion, peso_interno
from ..recetas.catalogo_ingredientes import ingredientes_catalogo, nutrientes_receta
from ..recetas.manual import (
    UNIDADES,
    cargar_receta,
    eliminar_receta,
    guardar_receta,
    listar_recetas,
)
import dataclasses


def _pct(cfg: dict, clave_pct: str) -> float:
    """Valor 0-100 actual de un peso (desde la clave nueva, la antigua o el defecto)."""
    _antigua, maximo, _def = _PESOS_PCT[clave_pct]
    return round(peso_interno(cfg, clave_pct) / maximo * 100)
from ..recetas.manual import listar_favoritas, marcar_favorita
from .marca import ESLOGAN, LOGO_SVG, NOMBRE, TOKENS_CSS, favicon_data_uri

_NOMBRE_DIA = {
    "lun": "Lunes", "mar": "Martes", "mie": "Miércoles", "jue": "Jueves",
    "vie": "Viernes", "sab": "Sábado", "dom": "Domingo",
}

# Nombres "bonitos" de los nutrientes, en el orden pedido por el usuario.
# 'grasas' del catalogo son grasas TOTALES: se muestran como insaturadas
# restando las saturadas.
_ORDEN_NUTRIENTES = [
    ("energia_kcal", "Energía (Kcal)", "kcal"),
    ("proteinas", "Proteínas", "g"),
    ("hidratos", "Hidratos de Carbono", "g"),
    ("grasas_insat", "Grasas insaturadas", "g"),
    ("grasas_sat", "Grasas saturadas", "g"),
    ("azucares", "Azúcares", "g"),
    ("sal", "Sal", "g"),
    ("fibra", "Fibra", "g"),
]

_ESTILO = (
    TOKENS_CSS
    + """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
  background: var(--bg); color: var(--text); }
header { background: linear-gradient(100deg, var(--verde-osc), var(--verde)); color: #fff;
  padding: 12px 20px; display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  box-shadow: 0 2px 10px rgba(30,60,40,.15); }
header .logo { height: 34px; }
header nav { display: flex; gap: 16px; flex-wrap: wrap; }
header a { color: rgba(255,255,255,.92); text-decoration: none; font-weight: 600; font-size: 14px; }
header a:hover { color: #fff; text-decoration: underline; }
main { max-width: 980px; margin: 0 auto; padding: 22px 20px; }
.card { background: var(--surface); border-radius: var(--radio); padding: 18px 20px;
  margin-bottom: 18px; box-shadow: var(--shadow); border: 1px solid var(--border); }
.franja { font-weight: 700; color: var(--verde-osc); margin: 12px 0 6px; font-size: 15px; }
.fav { color: var(--dorado); font-weight: 700; }
.chip { display: inline-block; background: var(--chip-bg); color: var(--chip-text);
  border-radius: 20px; padding: 2px 10px; font-size: 12px; margin: 2px 2px; white-space: nowrap; }
.meta { color: var(--muted); font-size: 13px; }
.note { color: var(--muted); font-size: 12px; margin: 2px 0 8px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
.ok { color: var(--verde); } .warn { color: var(--terracota); font-weight: 600; }
.btn { display: inline-block; background: var(--verde); color: #fff; border: 0;
  padding: 9px 16px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
  text-decoration: none; transition: filter .15s; }
.btn:hover { filter: brightness(1.06); }
.btn.sec { background: #6b7169; } .btn.mini { padding: 3px 10px; font-size: 12px; font-weight: 600; }
input, textarea, select { width: 100%; padding: 9px; border: 1px solid var(--border);
  border-radius: 8px; font: inherit; background: var(--surface); color: var(--text); }
input[type=range] { padding: 0; accent-color: var(--verde); }
input[type=checkbox] { width: auto; accent-color: var(--verde); }
label { display: block; margin: 10px 0 4px; font-weight: 600; font-size: 14px; }
.row { display: flex; gap: 14px; flex-wrap: wrap; }
.row > div { flex: 1; min-width: 150px; }
.big { font-size: 22px; font-weight: 700; }
a.receta { color: inherit; text-decoration: underline; text-decoration-color: var(--verde); }
.arrows { display: inline-flex; gap: 8px; align-items: center; margin-left: 10px; }
.arrows a, .arrows span.off { padding: 2px 11px; border-radius: 7px; background: var(--verde);
  color: #fff; text-decoration: none; font-weight: 700; }
.arrows span.off { background: #b6bbb4; }
.ticket { font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
  max-width: 560px; margin: 0 auto; border: 1px dashed var(--muted); padding: 18px 16px;
  background: var(--surface); color: var(--text); }
.ticket h2 { text-align: center; margin: 0 0 2px; font-size: 16px; letter-spacing: 2px; color: var(--verde-osc); }
.ticket .cab { text-align: center; margin: 0 0 10px; }
.ticket table { font-size: 12px; } .ticket td, .ticket th { padding: 3px 4px;
  border-bottom: 1px dotted var(--border); text-transform: none; letter-spacing: 0; }
.ticket .total { font-size: 15px; font-weight: 800; text-align: right; padding-top: 8px; }
pre.log { background: #111; color: #9f9; padding: 10px; border-radius: 8px;
  font-size: 12px; max-height: 320px; overflow: auto; }
"""
)


def _pagina(titulo: str, cuerpo: str, refrescar: int | None = None) -> str:
    meta = f'<meta http-equiv="refresh" content="{refrescar}">' if refrescar else ""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{meta}
<link rel="icon" href="{favicon_data_uri()}">
<title>{html.escape(titulo)} · {NOMBRE}</title><style>{_ESTILO}</style></head><body>
<header><a href="/" title="{NOMBRE} — {ESLOGAN}">{LOGO_SVG.replace('<svg', '<svg class="logo"', 1)}</a>
<nav><a href="/">Menú</a><a href="/compra">Lista de la compra</a>
<a href="/recetas">Recetas</a><a href="/catalogo">Catálogo</a>
<a href="/config">Configuración</a></nav></header>
<main>{cuerpo}</main></body></html>"""


# ------------------------- tarea de catalogo en 2º plano -------------------------

_CATALOGO = {"activa": False, "log": deque(maxlen=300), "resumen": ""}

# Estado del envio de la compra al carrito de Alcampo (en 2º plano).
_CARRITO = {"activa": False, "log": deque(maxlen=400), "resumen": ""}

# Estado de la comprobacion de actualizaciones (Fase 11): None = sin comprobar,
# False = comprobado y al dia, InfoActualizacion = hay version nueva.
_ACTUALIZACION = {"estado": None, "comprobado": False}


def _comprobar_actualizacion() -> None:
    """Consulta GitHub (una vez, repo fijo) y guarda el resultado en cache."""
    _ACTUALIZACION["estado"] = hay_actualizacion()
    _ACTUALIZACION["comprobado"] = True


def _banner_actualizacion() -> str:
    """Banner (en todas las paginas) si hay una version nueva disponible."""
    info = _ACTUALIZACION["estado"]
    if not info:
        return ""
    return (
        f'<div class="card" style="border-left:4px solid var(--dorado)">'
        f'✨ <b>Nueva versión disponible: {html.escape(info.version)}</b> '
        f'(tienes la {__version__}). '
        f'<form method="post" action="/actualizaciones/comprobar" style="display:inline">'
        f'<button class="btn mini" type="submit">Instalar</button></form> '
        f'<a class="meta" href="{html.escape(info.url_pagina)}" target="_blank">ver novedades</a></div>'
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


def _lanzar_carrito(config_path) -> tuple[bool, str]:
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
            res = anadir_al_carrito(lineas, dry_run=False, headless=False, log=_CARRITO["log"].append)
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


# ------------------------------- render del menu -------------------------------


def _fila_nutrientes(datos: dict, cfg: dict) -> str:
    """Tabla de nutrientes POR PERSONA Y DIA (total/dia y objetivo/dia)."""
    dias = int(datos.get("dias", 7))
    tot = datos.get("nutricion_total", {}) or {}
    num_com = int(datos.get("num_comensales", 2))
    cfg_nut = config_nutricion(cfg)
    bandas = {b.nutriente: b for b in objetivos_semanales(cfg_nut, num_com)}
    div = dias * num_com  # de total del menu a "por persona y dia"

    valores = dict(tot)
    valores["grasas_insat"] = max(0.0, tot.get("grasas", 0.0) - tot.get("grasas_sat", 0.0))

    filas = ""
    for clave, nombre, unidad in _ORDEN_NUTRIENTES:
        val_dia = valores.get(clave, 0.0) / div
        if clave == "energia_kcal":
            # Objetivo directamente desde la config del usuario: sus kcal diarias por
            # la fraccion del dia que cubre el menu, ± la tolerancia.
            centro = cfg_nut.kcal_por_comensal_dia * cfg_nut.fraccion_menu
            mas_menos = centro * cfg_nut.energia_tolerancia
            objetivo = f"{centro:.0f} ± {mas_menos:.0f}"
            en_banda = centro - mas_menos - 0.5 <= val_dia <= centro + mas_menos + 0.5
        elif clave == "grasas_insat":
            bg, bs = bandas.get("grasas"), bandas.get("grasas_sat")
            lo = max(0.0, (bg.minimo or 0) - (bs.maximo or 0)) / div if bg else 0
            hi = (bg.maximo or 0) / div if bg else 0
            objetivo = f"{lo:.0f}..{hi:.0f}"
            en_banda = lo - 0.5 <= val_dia <= hi + 0.5
        else:
            b = bandas.get(clave)
            lo = f"{b.minimo / div:.0f}" if b and b.minimo is not None else "—"
            hi = f"{b.maximo / div:.0f}" if b and b.maximo is not None else "—"
            objetivo = f"{lo}..{hi}"
            en_banda = True
            if b and b.minimo is not None and val_dia < b.minimo / div - 0.5:
                en_banda = False
            if b and b.maximo is not None and val_dia > b.maximo / div + 0.5:
                en_banda = False
        estado = '<span class="ok">✓</span>' if en_banda else '<span class="warn">✗</span>'
        filas += (
            f"<tr><td>{nombre}</td><td>{val_dia:.0f} {unidad}</td>"
            f"<td class='meta'>{objetivo} {unidad}</td><td>{estado}</td></tr>"
        )
    frac = cfg_nut.fraccion_menu
    return (
        f'<div class="card"><div class="franja">Nutrientes por persona y día '
        f"(comida + cena)</div>"
        f"<table><tr><th>Nutriente</th><th>Total/día</th><th>Objetivo/día</th><th></th></tr>"
        f"{filas}</table>"
        f'<p class="meta">Objetivos escalados a lo que cubre el menú: el {frac * 100:.0f}% de '
        f"la energía del día (comida {cfg_nut.pct_comida * 100:.0f}% + cena "
        f"{cfg_nut.pct_cena * 100:.0f}%, reparto recomendado FEN/AESAN). Con "
        f"{cfg_nut.kcal_por_comensal_dia:.0f} kcal/día configuradas, comida+cena deben aportar "
        f"{cfg_nut.kcal_por_comensal_dia * frac:.0f} kcal.</p></div>"
    )


def _link_receta(rid: str, info: dict, raciones: float | None = None) -> str:
    fav = ' <span class="fav">★</span>' if info.get("es_favorita") else ""
    rac = f' <span class="meta">({raciones:.2g} rac/pers.)</span>' if raciones else ""
    return (
        f'<a class="receta" href="/receta/{html.escape(rid)}">'
        f'{html.escape(info.get("titulo", rid))}</a>{fav}{rac}'
    )


def _tabla_dias(datos: dict) -> str:
    info = datos.get("recetas_info", {}) or {}
    raciones = datos.get("raciones", {}) or {}
    sel_com = datos.get("seleccion_comida", {}) or {}
    sel_cen = datos.get("seleccion_cena", {}) or {}

    def _t(rid):
        if not rid:
            return "—"
        n_usos = (sel_com.get(rid, 0) or 0) + (sel_cen.get(rid, 0) or 0)
        x = raciones.get(rid)
        por_comida = (x / n_usos) if (x and n_usos) else None
        return _link_receta(rid, info.get(rid, {}), por_comida)

    filas = ""
    for dia, comida, cena, es_bc in asignar_dias(datos, DIAS_SEMANA):
        etiqueta = ' <span class="meta">🍱 plato único</span>' if es_bc else ""
        filas += (
            f"<tr><td><b>{_NOMBRE_DIA.get(dia, dia)}</b>{etiqueta}</td>"
            f"<td>{_t(comida)}</td><td>{_t(cena)}</td></tr>"
        )
    tabla = f"<table><tr><th>Día</th><th>🌞 Comida</th><th>🌙 Cena</th></tr>{filas}</table>"
    return tabla + _resumen_grupos(datos)


_NOMBRE_GRUPO = {
    "verdura": "🥦 Verdura", "legumbre": "🫘 Legumbre", "pescado": "🐟 Pescado",
    "carne_roja": "🥩 Carne roja", "carne_blanca": "🍗 Carne blanca", "cereal": "🌾 Cereal",
    "huevo": "🥚 Huevo", "fruta": "🍎 Fruta", "lacteo": "🧀 Lácteo", "otro": "· Otro",
}


def _resumen_grupos(datos: dict) -> str:
    """Cuenta las comidas de la semana por grupo de alimento (equilibrio AESAN)."""
    info = datos.get("recetas_info", {}) or {}
    sel_com = datos.get("seleccion_comida", {}) or {}
    sel_cen = datos.get("seleccion_cena", {}) or {}
    cuenta: dict[str, int] = {}
    for sel in (sel_com, sel_cen):
        for rid, n in sel.items():
            g = info.get(rid, {}).get("grupo", "otro")
            cuenta[g] = cuenta.get(g, 0) + int(n)
    if not cuenta:
        return ""
    chips = " ".join(
        f'<span class="chip">{_NOMBRE_GRUPO.get(g, g)}: {n}</span>'
        for g, n in sorted(cuenta.items(), key=lambda x: -x[1])
    )
    return f'<p class="meta" style="margin-top:8px">Equilibrio semanal: {chips}</p>'


def _editor_html(datos: dict | None, catalogo: list[str]) -> str:
    """Formulario de crear/editar receta con filas de ingredientes dinamicas."""
    es_edicion = datos is not None
    titulo = html.escape(datos["titulo"]) if es_edicion else ""
    raciones = datos["raciones"] if es_edicion else 4
    rid = html.escape(datos["id"]) if es_edicion else ""
    ings = datos["ingredientes"] if es_edicion else [{"nombre": "", "cantidad": "", "unidad": "g"}]

    opciones_unidad = "".join(f'<option value="{u}">{u}</option>' for u in UNIDADES)
    datalist = "".join(f"<option>{html.escape(n)}</option>" for n in catalogo)

    def _fila(ing):
        nombre = html.escape(str(ing.get("nombre", "")))
        cant = html.escape(str(ing.get("cantidad", "") or ""))
        uni = ing.get("unidad", "g")
        ops = "".join(
            f'<option value="{u}"{" selected" if u == uni else ""}>{u}</option>' for u in UNIDADES
        )
        return (
            '<div class="ing-fila" style="display:flex;gap:6px;margin-bottom:6px;align-items:center">'
            f'<input name="ing_nombre" list="catalogo_ing" value="{nombre}" '
            'placeholder="Ingrediente del catálogo…" style="flex:3">'
            f'<input name="ing_cantidad" value="{cant}" inputmode="decimal" '
            'pattern="[0-9]*[.,]?[0-9]*" placeholder="cant." style="flex:1" '
            "oninput=\"this.value=this.value.replace(/[^0-9.,]/g,'')\">"
            f'<select name="ing_unidad" style="flex:1">{ops}</select>'
            '<button type="button" class="btn mini sec" onclick="this.parentElement.remove()">−</button>'
            "</div>"
        )

    filas = "".join(_fila(i) for i in ings)
    chk = lambda k: " checked" if es_edicion and datos.get(k) else ""
    return f"""
<div class="card"><div class="franja">{"Editar" if es_edicion else "Nueva"} receta</div>
<form method="post" action="/recetas/guardar">
<input type="hidden" name="receta_id" value="{rid}">
<datalist id="catalogo_ing">{datalist}</datalist>
<div class="row">
  <div style="flex:3"><label>Título</label>
    <input name="titulo" required value="{titulo}" placeholder="Lentejas de la abuela"></div>
  <div><label>Raciones</label>
    <input name="raciones" type="number" min="1" value="{raciones}" required></div>
</div>
<label>Ingredientes</label>
<div id="ings">{filas}</div>
<button type="button" class="btn mini" onclick="addFila()">+ Añadir ingrediente</button>
<div style="margin-top:12px">
  <label><input type="checkbox" name="plato_unico" value="1"{chk('es_plato_unico')} style="width:auto"> Óptima para batchcooking / plato único</label>
  <label><input type="checkbox" name="cena" value="1"{chk('es_cena')} style="width:auto"> Buena como cena (ligera y sencilla)</label>
  <label><input type="checkbox" name="favorita" value="1"{chk('es_favorita')} style="width:auto"> Favorita ★</label>
</div>
<div style="margin-top:12px">
  <button class="btn" type="submit">Guardar receta</button>
  {"" if not es_edicion else f'<button class="btn sec" formaction="/recetas/{rid}/eliminar" formmethod="post" formnovalidate>Eliminar</button>'}
</div>
</form>
<p class="meta">Elige el ingrediente escribiendo (se busca en el catálogo de Alcampo), la unidad,
y la cantidad (solo números). Usa + y − para añadir o quitar líneas. Tras guardar, ejecuta
<code>menu-app-emparejar</code> para casar los ingredientes con productos.</p>
</div>
<script>
function addFila() {{
  var cont = document.getElementById('ings');
  var f = cont.firstElementChild.cloneNode(true);
  f.querySelectorAll('input').forEach(function(i){{ i.value=''; }});
  cont.appendChild(f);
}}
</script>
"""


def _barras_nutrientes(conn, cfg, ingredientes: list[dict], raciones: int) -> str:
    """Barras: nutrientes por ración de la receta frente al objetivo del día."""
    por_racion = nutrientes_receta(conn, ingredientes, raciones)
    cfg_nut = dataclasses.replace(config_nutricion(cfg), fraccion_ingesta_menu=1.0)
    dia = {b.nutriente: b for b in objetivos_semanales(cfg_nut, 1)}
    dias = cfg_nut.dias

    valores = dict(por_racion)
    valores["grasas_insat"] = max(0.0, por_racion.get("grasas", 0.0) - por_racion.get("grasas_sat", 0.0))

    filas = ""
    for clave, nombre, unidad in _ORDEN_NUTRIENTES:
        val = valores.get(clave, 0.0)
        if clave == "energia_kcal":
            objetivo_dia = cfg_nut.kcal_por_comensal_dia
        elif clave == "grasas_insat":
            bg, bs = dia.get("grasas"), dia.get("grasas_sat")
            objetivo_dia = ((bg.maximo or 0) / dias) if bg else 0
        else:
            b = dia.get(clave)
            objetivo_dia = ((b.maximo or b.minimo or 0) / dias) if b else 0
        pct = min(100, 100 * val / objetivo_dia) if objetivo_dia else 0
        filas += (
            f'<tr><td style="width:150px">{nombre}</td>'
            f'<td style="width:55px;text-align:right">{val:.0f} {unidad}</td>'
            f'<td><div style="background:#ddd;border-radius:5px;height:14px;overflow:hidden">'
            f'<div style="background:#2e7d32;height:100%;width:{pct:.0f}%"></div></div></td>'
            f'<td class="meta" style="width:110px">de {objetivo_dia:.0f} {unidad}/día</td></tr>'
        )
    return (
        '<div class="card"><div class="franja">Nutrientes de una ración vs. el total del día'
        "</div><table>" + filas + "</table>"
        '<p class="meta">La barra indica qué parte de la necesidad diaria (por persona) cubre '
        "una ración de esta receta.</p></div>"
    )


def crear_app(config_path: str | Path = "config.yaml") -> FastAPI:
    config_path = Path(config_path)
    app = FastAPI(title=NOMBRE)

    def _conn():
        cfg = cargar_config(config_path)
        ruta = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        conn = get_connection(ruta)
        init_db(conn)
        return conn, cfg

    # Comprobacion de actualizaciones al arrancar (en segundo plano, no bloquea).
    _cfg_inicial = cargar_config(config_path)
    if (_cfg_inicial.get("actualizaciones", {}) or {}).get("comprobar_al_arrancar", True):
        threading.Thread(target=_comprobar_actualizacion, daemon=True).start()

    # ---------------------------------- menu ----------------------------------

    @app.get("/", response_class=HTMLResponse)
    def home(semana: int = 1, msg: str = ""):
        conn, cfg = _conn()
        try:
            plan_id, semanas = cargar_plan(conn)
        finally:
            conn.close()
        aviso = _banner_actualizacion()
        aviso += f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""

        n_plan = int(cfg.get("semanas_plan", 1))
        form_generar = (
            f'<div class="card"><form method="post" action="/generar">'
            f'<label><input type="checkbox" name="batchcooking" value="1" style="width:auto"> '
            f"Forzar batchcooking en TODAS las comidas</label>"
            f'<div style="margin-top:10px"><button class="btn" type="submit">'
            f"Generar plan nuevo ({n_plan} semana{'s' if n_plan != 1 else ''})</button></div>"
            f'<p class="meta">Se planifican {n_plan} semanas sin repetir recetas dentro de la '
            f"semana (regla configurable en Configuración).</p></form></div>"
        )

        if not semanas:
            return _pagina(
                "Menú semanal",
                aviso + '<div class="card">Todavía no hay ningún plan generado.</div>' + form_generar,
            )

        n_sem = max(semanas)
        semana = max(1, min(int(semana), n_sem))
        datos = semanas[semana]

        ant = (
            f'<a href="/?semana={semana - 1}">◀</a>' if semana > 1 else '<span class="off">◀</span>'
        )
        sig = (
            f'<a href="/?semana={semana + 1}">▶</a>' if semana < n_sem else '<span class="off">▶</span>'
        )
        flechas = f'<span class="arrows">{ant} Semana {semana}/{n_sem} {sig}</span>'

        if not datos.get("factible"):
            cuerpo = aviso + form_generar + (
                f'<div class="card"><div class="franja">Plan por día {flechas}</div>'
                f'<p class="warn">Sin menú factible esta semana: '
                f'{html.escape(datos.get("motivo", ""))}. Amplía el corpus de recetas o relaja '
                f"la regla de repetición.</p></div>"
            )
            return _pagina("Menú semanal", cuerpo)

        botones_semana = (
            f'<form method="post" action="/alternativa" style="display:inline">'
            f'<input type="hidden" name="semana" value="{semana}">'
            f'<button class="btn sec" type="submit">Generar alternativa</button></form>'
        )
        plan_card = (
            f'<div class="card"><div class="franja">Plan por día {flechas} '
            f'<span style="float:right">{botones_semana}</span></div>'
            + _tabla_dias(datos)
            + f'<p class="meta">Coste de la semana: <b>{datos.get("coste_total", 0):.2f} €</b>. '
            f"Los días 🍱 la comida es un plato único batchcooking (transportable, sin postre). "
            f"Pulsa una receta para ver sus ingredientes y precios.</p></div>"
        )

        info = datos.get("recetas_info", {}) or {}
        usadas = sorted(
            set(datos.get("seleccion_comida", {}) or {}) | set(datos.get("seleccion_cena", {}) or {}),
            key=lambda rid: info.get(rid, {}).get("titulo", rid),
        )
        filas_cambio = "".join(
            f"<tr><td>{_link_receta(rid, info.get(rid, {}))}</td>"
            f'<td style="text-align:right"><form method="post" action="/cambiar" style="margin:0">'
            f'<input type="hidden" name="semana" value="{semana}">'
            f'<input type="hidden" name="receta_id" value="{html.escape(rid)}">'
            f'<button class="btn mini sec" type="submit">Cambiar por otra</button></form></td></tr>'
            for rid in usadas
        )
        cambio_card = (
            f'<div class="card"><div class="franja">Cambiar una receta concreta</div>'
            f"<table>{filas_cambio}</table>"
            f'<p class="meta">Sustituye esa receta por la siguiente mejor opción manteniendo '
            f"nutrientes y coste.</p></div>"
        )

        cuerpo = aviso + form_generar + plan_card + _fila_nutrientes(datos, cfg) + cambio_card
        return _pagina("Menú semanal", cuerpo)

    @app.post("/generar")
    def generar(batchcooking: int = Form(0)):
        conn, cfg = _conn()
        try:
            generar_plan(conn, cfg, batchcooking=bool(batchcooking))
        finally:
            conn.close()
        return RedirectResponse("/?semana=1&msg=Plan generado.", status_code=303)

    @app.post("/alternativa")
    def alternativa(semana: int = Form(...)):
        conn, cfg = _conn()
        try:
            plan_id, semanas = cargar_plan(conn)
            if plan_id and semana in semanas:
                datos = semanas[semana]
                corte = set(datos.get("seleccion_comida", {}) or {}) | set(
                    datos.get("seleccion_cena", {}) or {}
                )
                regenerar_semana(
                    conn, cfg, plan_id, semana, corte=corte,
                    batchcooking=bool(datos.get("batchcooking_forzado")),
                )
        finally:
            conn.close()
        return RedirectResponse(f"/?semana={semana}&msg=Menú alternativo generado.", status_code=303)

    @app.post("/cambiar")
    def cambiar(semana: int = Form(...), receta_id: str = Form(...)):
        conn, cfg = _conn()
        try:
            plan_id, semanas = cargar_plan(conn)
            if plan_id and semana in semanas:
                datos = semanas[semana]
                regenerar_semana(
                    conn, cfg, plan_id, semana, excluir=receta_id,
                    batchcooking=bool(datos.get("batchcooking_forzado")),
                )
        finally:
            conn.close()
        return RedirectResponse(f"/?semana={semana}&msg=Receta sustituida.", status_code=303)

    # ----------------------------- detalle de receta -----------------------------

    @app.get("/receta/{receta_id}", response_class=HTMLResponse)
    def receta_detalle(receta_id: str):
        conn, _cfg = _conn()
        try:
            cab = conn.execute(
                "SELECT titulo, raciones, fuente, url, es_favorita FROM recetas WHERE id = ?",
                (receta_id,),
            ).fetchone()
            if cab is None:
                return _pagina("Receta", '<div class="card warn">Receta no encontrada.</div>')
            ingredientes = conn.execute(
                "SELECT texto_original, nombre_normalizado, cantidad, unidad, cantidad_metrica, "
                "unidad_metrica FROM receta_ingredientes WHERE receta_id = ? ORDER BY orden",
                (receta_id,),
            ).fetchall()
            mapeo = {
                f["ingrediente_norm"]: f["retailer_product_id"]
                for f in conn.execute(
                    "SELECT ingrediente_norm, retailer_product_id FROM mapeo_ingr_producto "
                    "WHERE retailer_product_id IS NOT NULL"
                ).fetchall()
            }
            filas = ""
            total = 0.0
            for ing in ingredientes:
                gramos = ing["cantidad_metrica"]
                estimado = ""
                # Unidad correcta: ml para liquidos (unidad_metrica='ml'), g para el resto.
                um = ing["unidad_metrica"] or "g"
                if gramos is None:
                    gramos = _gramos_por_piezas(
                        ing["nombre_normalizado"], ing["unidad"], ing["cantidad"]
                    )
                    if gramos is not None:
                        estimado = ' <span class="meta">(≈ estimado)</span>'
                        um = "g"
                cant = f"{gramos:.0f} {um}{estimado}" if gramos is not None else "—"

                rid = mapeo.get(ing["nombre_normalizado"])
                prod_html, precio_html = '<span class="meta">sin producto</span>', "—"
                if rid:
                    p = conn.execute(
                        "SELECT nombre, url_producto, precio_eur, precio_por_unidad, unidad_medida "
                        "FROM productos WHERE retailer_product_id = ?",
                        (rid,),
                    ).fetchone()
                    if p is not None:
                        enlace = (
                            f'<a class="receta" href="{html.escape(p["url_producto"] or "#")}" '
                            f'target="_blank">{html.escape(p["nombre"][:60])}</a>'
                        )
                        paquete = (
                            f' <span class="meta">({p["precio_eur"]:.2f} €/ud)</span>'
                            if p["precio_eur"] is not None else ""
                        )
                        prod_html = enlace + paquete
                        factor = _FACTOR_PRECIO.get(p["unidad_medida"])
                        if gramos is not None and factor and p["precio_por_unidad"] is not None:
                            coste_ing = gramos * factor * p["precio_por_unidad"]
                            total += coste_ing
                            precio_html = f"{coste_ing:.2f} €"
                filas += (
                    f"<tr><td>{html.escape(ing['texto_original'][:70])}</td><td>{cant}</td>"
                    f"<td>{prod_html}</td><td>{precio_html}</td></tr>"
                )
            raciones = cab["raciones"] or 1
            fav = ' <span class="fav">★ favorita</span>' if cab["es_favorita"] else ""
            fuente = (
                f'<a class="receta" href="{html.escape(cab["url"])}" target="_blank">'
                f'{html.escape(cab["fuente"] or "fuente")}</a>'
                if cab["url"] and not cab["url"].startswith("manual://")
                else html.escape(cab["fuente"] or "manual")
            )
            cuerpo = (
                f'<div class="card"><div class="big">{html.escape(cab["titulo"])}{fav}</div>'
                f'<p class="meta">{raciones} raciones · fuente: {fuente}</p>'
                f'<table><tr><th>Ingrediente</th><th>Cantidad</th>'
                f"<th>Producto Alcampo</th><th>Coste usado</th></tr>{filas}</table>"
                f'<p class="franja">Coste de la receta completa: {total:.2f} € '
                f'<span class="meta">({total / raciones:.2f} €/ración)</span></p>'
                f'<p class="meta">El "coste usado" es la parte proporcional del producto que '
                f"consume la receta (no el precio del paquete entero).</p></div>"
            )
            return _pagina(cab["titulo"], cuerpo)
        finally:
            conn.close()

    # ------------------------------ lista de la compra ------------------------------

    @app.get("/compra", response_class=HTMLResponse)
    def compra_page(msg: str = ""):
        conn, cfg = _conn()
        try:
            compra = lista_compra(conn, despensa=cfg.get('despensa'))
        finally:
            conn.close()
        if compra.semanas == 0:
            return _pagina(
                "Lista de la compra",
                '<div class="card">No hay plan generado: genera primero el menú.</div>',
            )
        filas = ""
        for pasillo, lineas in compra.por_pasillo().items():
            subtotal = sum(l.total for l in lineas if l.total is not None)
            filas += (
                f'<tr><td colspan="4" style="padding-top:10px"><b>🛒 {html.escape(pasillo)}</b> '
                f'<span class="meta">({subtotal:.2f} €)</span></td></tr>'
            )
            for l in lineas:
                enlace = (
                    f'<a class="receta" href="{html.escape(l.url)}" target="_blank">'
                    f"{html.escape(l.nombre[:46])}</a>"
                    if l.url else html.escape(l.nombre[:46])
                )
                precio = f"{l.precio_unidad:.2f}" if l.precio_unidad is not None else "—"
                tot = f"{l.total:.2f}" if l.total is not None else "—"
                filas += (
                    f"<tr><td>{l.unidades}×</td><td>{enlace}"
                    f'<br><span class="meta">necesitas {l.cantidad_legible}</span></td>'
                    f'<td style="text-align:right">{precio}</td>'
                    f'<td style="text-align:right"><b>{tot}</b></td></tr>'
                )
        sin = ""
        if compra.sin_producto:
            lista = ", ".join(html.escape(s) for s in compra.sin_producto[:20])
            sin = (
                f'<p class="meta">Sin producto asignado (cómpralos a tu criterio): {lista}'
                + ("…" if len(compra.sin_producto) > 20 else "") + "</p>"
            )
        ticket = (
            f'<div class="ticket"><h2>ALCAMPO</h2>'
            f'<p class="cab">Lista de la compra · {compra.semanas} semana'
            f"{'s' if compra.semanas != 1 else ''} de menús<br>"
            f'<span class="meta">{html.escape(compra.plan_id or "")}</span></p>'
            f"<table><tr><th>Uds</th><th>Producto</th>"
            f'<th style="text-align:right">€/ud</th><th style="text-align:right">Total</th></tr>'
            f"{filas}</table>"
            f'<div class="total">TOTAL: {compra.total:.2f} €</div></div>'
        )
        descargas = (
            '<div class="card"><div class="franja">Descargar</div>'
            '<a class="btn" href="/compra.pdf">📄 Lista de compra (PDF)</a> '
            '<a class="btn sec" href="/compra.csv">📊 Lista de compra (CSV)</a> '
            '<a class="btn sec" href="/menu.pdf">📄 Menú (PDF)</a> '
            '<a class="btn sec" href="/menu.csv">📊 Menú (CSV)</a></div>'
        )
        # --- Enviar al carrito de Alcampo (en 2º plano) ---
        activa = _CARRITO["activa"]
        if activa:
            accion = '<p class="ok">⏳ Envío en marcha… inicia sesión en la ventana de Alcampo.</p>'
        else:
            accion = (
                '<form method="post" action="/carrito/enviar">'
                '<button class="btn" type="submit">🛒 Enviar la compra al carrito de Alcampo</button>'
                "</form>"
            )
        if _CARRITO["resumen"]:
            accion += f'<p class="ok">{html.escape(_CARRITO["resumen"])}</p>'
        log_txt = "\n".join(list(_CARRITO["log"])[-40:])
        log_html = f'<pre class="log">{html.escape(log_txt)}</pre>' if log_txt else ""
        carrito_card = (
            '<div class="card"><div class="franja">🛒 Enviar al carrito de Alcampo</div>'
            + accion
            + log_html
            + '<p class="note">Abre Alcampo en tu navegador, inicias sesión TÚ (la app nunca '
            "guarda tu contraseña) y añade automáticamente todos los productos a tu cesta, en "
            "paralelo. Al terminar te deja en la cesta para elegir franja y pagar. Salta los "
            "productos agotados.</p></div>"
        )
        aviso = f'<div class="card"><p class="ok">{html.escape(msg)}</p></div>' if msg else ""
        cuerpo = (
            aviso
            + descargas
            + carrito_card
            + f'<div class="card">{ticket}{sin}'
            f'<p class="meta">Agrupada por pasillo. Cada producto enlaza a su página en '
            f"compraonline.alcampo.es para añadirlo al carrito. Las unidades se calculan según "
            f"el formato del paquete.</p></div>"
        )
        return _pagina("Lista de la compra", cuerpo, refrescar=5 if activa else None)

    @app.post("/carrito/enviar")
    def carrito_enviar():
        _ok, msg = _lanzar_carrito(config_path)
        return RedirectResponse(f"/compra?msg={quote(msg)}", status_code=303)

    @app.get("/compra.csv")
    def compra_csv():
        conn, cfg = _conn()
        try:
            data = compra_a_csv(lista_compra(conn, despensa=cfg.get('despensa')))
        finally:
            conn.close()
        return Response(
            data, media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=lista_compra.csv"},
        )

    @app.get("/compra.pdf")
    def compra_pdf():
        conn, cfg = _conn()
        try:
            data = compra_a_pdf(lista_compra(conn, despensa=cfg.get('despensa')))
        finally:
            conn.close()
        return Response(
            data, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=lista_compra.pdf"},
        )

    @app.get("/menu.csv")
    def menu_csv():
        conn, _ = _conn()
        try:
            _pid, semanas = cargar_plan(conn)
            data = menu_a_csv(semanas)
        finally:
            conn.close()
        return Response(
            data, media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=menu.csv"},
        )

    @app.get("/menu.pdf")
    def menu_pdf():
        conn, _ = _conn()
        try:
            _pid, semanas = cargar_plan(conn)
            data = menu_a_pdf(semanas)
        finally:
            conn.close()
        return Response(
            data, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=menu.pdf"},
        )

    # ------------------------------- catalogo -------------------------------

    @app.get("/catalogo", response_class=HTMLResponse)
    def catalogo_page(msg: str = "", q: str = "", pagina: int = 1, solo_aptos: int = 0):
        conn, cfg = _conn()
        try:
            fila = conn.execute(
                "SELECT COUNT(*) AS n, MAX(fecha_actualizacion) AS f FROM productos"
            ).fetchone()
            por_pagina = 30
            where, params = [], []
            if q.strip():
                where.append("lower(nombre) LIKE ?")
                params.append(f"%{q.strip().lower()}%")
            if solo_aptos:
                where.append("apto_receta = 1")
            wsql = (" WHERE " + " AND ".join(where)) if where else ""
            total = conn.execute(f"SELECT COUNT(*) FROM productos{wsql}", params).fetchone()[0]
            pagina = max(1, int(pagina))
            prods = conn.execute(
                f"SELECT retailer_product_id, nombre, precio_eur, apto_receta, energia_kcal_100g "
                f"FROM productos{wsql} ORDER BY nombre LIMIT ? OFFSET ?",
                params + [por_pagina, (pagina - 1) * por_pagina],
            ).fetchall()
        finally:
            conn.close()

        activa = _CATALOGO["activa"]
        log = "\n".join(list(_CATALOGO["log"])[-40:])
        estado = ""
        if activa:
            estado = (
                '<p class="warn">Actualización en curso… (esta página se refresca sola)</p>'
                f'<pre class="log">{html.escape(log)}</pre>'
            )
        elif _CATALOGO["resumen"]:
            estado = f'<p class="ok">{html.escape(_CATALOGO["resumen"])}</p>'

        seleccionadas = set(
            (cfg.get("ingesta", {}) or {}).get("category_roots") or FOOD_CATEGORY_ROOTS.keys()
        )
        cats = "".join(
            f'<label style="display:inline-flex;gap:5px;margin:0 12px 6px 0">'
            f'<input type="checkbox" name="categorias" value="{cid}" style="width:auto" '
            f'{"checked" if cid in seleccionadas else ""}> {html.escape(nombre)}</label>'
            for cid, nombre in FOOD_CATEGORY_ROOTS.items()
        )
        actualizar_card = (
            f'<div class="card"><div class="franja">Descargar / actualizar catálogo</div>'
            f'<p>Productos en la base de datos: <b>{fila["n"]}</b> · '
            f'<span class="meta">Última actualización: {html.escape(str(fila["f"] or "nunca"))}</span></p>'
            + (
                ""
                if activa
                else f'<form method="post" action="/catalogo-actualizar">'
                f"<label>Categorías a descargar/actualizar:</label>"
                f'<div style="margin:6px 0">{cats}</div>'
                f'<button class="btn" type="submit">Actualizar seleccionadas</button></form>'
            )
            + estado
            + '<p class="meta">Refresca precios, ofertas y productos nuevos de las categorías '
            "marcadas. Va a ritmo lento para no saturar la web; puedes seguir usando la app.</p></div>"
        )

        # Visor/editor del catalogo.
        filas = ""
        for p in prods:
            apto = "✓" if p["apto_receta"] else "—"
            precio = f'{p["precio_eur"]:.2f} €' if p["precio_eur"] is not None else "—"
            nut = "sí" if p["energia_kcal_100g"] is not None else "no"
            filas += (
                f'<tr><td>{html.escape(p["nombre"][:55])}</td><td>{precio}</td>'
                f'<td style="text-align:center">{apto}</td><td style="text-align:center">{nut}</td>'
                f'<td><a class="btn mini sec" href="/catalogo/{html.escape(p["retailer_product_id"])}">'
                f"Editar</a></td></tr>"
            )
        n_pags = max(1, -(-total // por_pagina))
        base = f"/catalogo?q={html.escape(q)}&solo_aptos={solo_aptos}"
        nav = (
            (f'<a class="btn mini" href="{base}&pagina={pagina-1}">◀</a> ' if pagina > 1 else "")
            + f'<span class="meta">Página {pagina}/{n_pags} ({total} productos)</span>'
            + (f' <a class="btn mini" href="{base}&pagina={pagina+1}">▶</a>' if pagina < n_pags else "")
        )
        visor = (
            f'<div class="card"><div class="franja">Ver y corregir el catálogo</div>'
            f'<form method="get" action="/catalogo" style="margin-bottom:8px">'
            f'<input name="q" value="{html.escape(q)}" placeholder="Buscar producto…" '
            f'style="max-width:60%;display:inline-block;width:auto">'
            f'<label style="display:inline-flex;gap:5px;margin-left:10px">'
            f'<input type="checkbox" name="solo_aptos" value="1" style="width:auto" '
            f'{"checked" if solo_aptos else ""}> solo aptos</label></form>'
            f"<table><tr><th>Producto</th><th>Precio</th><th>Apto</th><th>Nutric.</th><th></th></tr>"
            f"{filas}</table><div style='margin-top:8px'>{nav}</div></div>"
        )
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        return _pagina(
            "Catálogo", aviso + actualizar_card + visor, refrescar=4 if activa else None
        )

    @app.get("/catalogo/{producto_id}", response_class=HTMLResponse)
    def producto_editar(producto_id: str, msg: str = ""):
        conn, _ = _conn()
        try:
            p = conn.execute(
                "SELECT * FROM productos WHERE retailer_product_id = ?", (producto_id,)
            ).fetchone()
        finally:
            conn.close()
        if p is None:
            return RedirectResponse("/catalogo?msg=Producto no encontrado.", status_code=303)

        def _campo(nombre, etiqueta, paso="0.01"):
            v = p[nombre]
            v = "" if v is None else v
            return (
                f'<div><label>{etiqueta}</label>'
                f'<input name="{nombre}" type="number" step="{paso}" value="{v}"></div>'
            )

        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        cuerpo = (
            aviso
            + f'<div class="card"><div class="franja">Editar producto</div>'
            f'<p><b>{html.escape(p["nombre"])}</b></p>'
            f'<form method="post" action="/catalogo/{html.escape(producto_id)}">'
            f'<div class="row">{_campo("precio_eur", "Precio (€)")}'
            f'{_campo("precio_por_unidad", "Precio por unidad")}'
            f'<div><label>Apto para receta</label>'
            f'<select name="apto_receta"><option value="1"{" selected" if p["apto_receta"] else ""}>Sí'
            f'</option><option value="0"{" selected" if not p["apto_receta"] else ""}>No</option>'
            f"</select></div></div>"
            f'<div class="franja">Nutrición por 100 g/ml</div><div class="row">'
            f'{_campo("energia_kcal_100g", "Energía (kcal)", "1")}{_campo("proteinas_100g", "Proteínas")}'
            f'{_campo("hidratos_100g", "Hidratos")}{_campo("grasas_100g", "Grasas")}</div><div class="row">'
            f'{_campo("grasas_sat_100g", "Grasas sat.")}{_campo("azucares_100g", "Azúcares")}'
            f'{_campo("sal_100g", "Sal")}{_campo("fibra_100g", "Fibra")}</div>'
            f'<div style="margin-top:12px"><button class="btn" type="submit">Guardar</button> '
            f'<a class="btn sec" href="/catalogo">Volver</a></div></form>'
            f'<p class="meta">Corrige aquí errores puntuales del catálogo (precio o nutrición). '
            f"Se aplican de inmediato al generar el menú.</p></div>"
        )
        return _pagina("Editar producto", cuerpo)

    @app.post("/catalogo/{producto_id}")
    async def producto_guardar(producto_id: str, request: Request):
        form = await request.form()
        campos = [
            "precio_eur", "precio_por_unidad", "energia_kcal_100g", "proteinas_100g",
            "hidratos_100g", "grasas_100g", "grasas_sat_100g", "azucares_100g",
            "sal_100g", "fibra_100g",
        ]
        sets, params = [], []
        for c in campos:
            v = form.get(c, "")
            sets.append(f"{c} = ?")
            params.append(float(v) if str(v).strip() != "" else None)
        sets.append("apto_receta = ?")
        params.append(1 if form.get("apto_receta") == "1" else 0)
        params.append(producto_id)
        conn, _ = _conn()
        try:
            conn.execute(
                f"UPDATE productos SET {', '.join(sets)} WHERE retailer_product_id = ?", params
            )
            conn.commit()
        finally:
            conn.close()
        return RedirectResponse(f"/catalogo/{producto_id}?msg=Producto actualizado.", status_code=303)

    # NOTA: la ruta NO puede ser "/catalogo/actualizar": chocaria con
    # "/catalogo/{producto_id}" (se interpretaria 'actualizar' como un id de
    # producto). Por eso va con guion.
    @app.post("/catalogo-actualizar")
    async def catalogo_actualizar(request: Request):
        form = await request.form()
        cats = [str(c) for c in form.getlist("categorias")] or None
        _conn_, cfg = _conn()
        _conn_.close()
        _lanzar_actualizacion(cfg, categorias=cats)
        return RedirectResponse("/catalogo", status_code=303)

    # ----------------------------- editor de recetas -----------------------------

    @app.get("/recetas", response_class=HTMLResponse)
    def recetas_page(msg: str = "", q: str = ""):
        conn, _ = _conn()
        try:
            recetas = listar_recetas(conn, busqueda=q)
        finally:
            conn.close()
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        filas = ""
        for r in recetas:
            fav = ' <span class="fav">★</span>' if r["es_favorita"] else ""
            etiqueta = "✏️ propia" if r["editable"] else "catálogo"
            acciones = (
                f'<a class="btn mini" href="/recetas/{html.escape(r["id"])}/editar">Editar</a> '
                if r["editable"]
                else '<a class="btn mini sec" href="/receta/{}">Ver</a> '.format(html.escape(r["id"]))
            )
            filas += (
                f'<tr><td><a class="receta" href="/receta/{html.escape(r["id"])}">'
                f'{html.escape(r["titulo"])}</a>{fav} <span class="meta">[{etiqueta}]</span></td>'
                f'<td style="text-align:right;white-space:nowrap">{acciones}</td></tr>'
            )
        cuerpo = (
            aviso
            + '<div class="card"><div class="franja">Recetas '
            f'<a class="btn" style="float:right" href="/recetas/nueva">+ Nueva receta</a></div>'
            '<form method="get" action="/recetas" style="margin-bottom:10px">'
            f'<input name="q" value="{html.escape(q)}" placeholder="Buscar receta por nombre…">'
            "</form>"
            f"<table>{filas or '<tr><td class=meta>Sin resultados.</td></tr>'}</table>"
            f'<p class="meta">Mostrando {len(recetas)} recetas (las tuyas primero). Las del '
            "catálogo (scrapeadas) solo se pueden ver; las tuyas se pueden editar.</p></div>"
        )
        return _pagina("Recetas", cuerpo)

    @app.get("/recetas/nueva", response_class=HTMLResponse)
    def receta_nueva():
        conn, _ = _conn()
        try:
            catalogo = ingredientes_catalogo(conn)
        finally:
            conn.close()
        return _pagina("Nueva receta", _editor_html(None, catalogo))

    @app.get("/recetas/{receta_id}/editar", response_class=HTMLResponse)
    def receta_editar(receta_id: str):
        conn, cfg = _conn()
        try:
            datos = cargar_receta(conn, receta_id)
            if datos is None or not datos["editable"]:
                return RedirectResponse("/recetas?msg=Esa receta no es editable.", status_code=303)
            catalogo = ingredientes_catalogo(conn)
            barras = _barras_nutrientes(conn, cfg, datos["ingredientes"], datos["raciones"])
        finally:
            conn.close()
        return _pagina("Editar receta", _editor_html(datos, catalogo) + barras)

    @app.post("/recetas/guardar")
    async def receta_guardar(request: Request):
        form = await request.form()
        nombres = form.getlist("ing_nombre")
        cantidades = form.getlist("ing_cantidad")
        unidades = form.getlist("ing_unidad")
        ingredientes = [
            {"nombre": n, "cantidad": c, "unidad": u}
            for n, c, u in zip(nombres, cantidades, unidades)
            if (n or "").strip()
        ]
        conn, _ = _conn()
        try:
            rid = guardar_receta(
                conn,
                titulo=str(form.get("titulo", "")),
                raciones=int(form.get("raciones", 1) or 1),
                ingredientes=ingredientes,
                es_favorita=bool(form.get("favorita")),
                es_plato_unico=bool(form.get("plato_unico")),
                es_cena=bool(form.get("cena")),
                receta_id=form.get("receta_id") or None,
            )
            destino = f"/recetas/{rid}/editar?msg=Receta guardada. Ejecuta menu-app-emparejar."
        except ValueError as e:
            conn.close()
            return RedirectResponse(f"/recetas?msg=Error: {e}", status_code=303)
        conn.close()
        return RedirectResponse(destino, status_code=303)

    @app.post("/recetas/{receta_id}/eliminar")
    def receta_eliminar(receta_id: str):
        conn, _ = _conn()
        try:
            eliminar_receta(conn, receta_id)
        finally:
            conn.close()
        return RedirectResponse("/recetas?msg=Receta eliminada.", status_code=303)

    @app.post("/favorita")
    def toggle_fav(receta_id: str = Form(...), quitar: int = Form(0)):
        conn, _ = _conn()
        try:
            marcar_favorita(conn, receta_id, favorita=not bool(quitar))
        finally:
            conn.close()
        return RedirectResponse("/recetas?msg=Favorita actualizada.", status_code=303)

    # -------------------------------- configuracion --------------------------------

    @app.get("/config", response_class=HTMLResponse)
    def config_page(msg: str = ""):
        cfg = cargar_config(config_path)
        bc = cfg.get("batchcooking", {}) or {}
        dias_marcados = set(bc.get("dias", []) or [])
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""

        def _num(nombre, etiqueta, valor, nota, paso="1", mini="0"):
            return (
                f'<div><label>{etiqueta}</label>'
                f'<input name="{nombre}" type="number" step="{paso}" min="{mini}" '
                f'value="{valor}"><p class="note">{nota}</p></div>'
            )

        def _slider(nombre, etiqueta, valor_pct, nota):
            return (
                f'<div><label>{etiqueta}: <span id="v_{nombre}">{valor_pct:.0f}</span>%</label>'
                f'<input type="range" name="{nombre}" min="0" max="100" step="1" '
                f'value="{valor_pct:.0f}" oninput="document.getElementById(\'v_{nombre}\')'
                f".textContent=this.value\" style=\"width:100%\">"
                f'<p class="note">{nota}</p></div>'
            )

        casillas = "".join(
            f'<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px">'
            f'<input type="checkbox" name="dias_bc" value="{d}" style="width:auto" '
            f'{"checked" if d in dias_marcados else ""}> {_NOMBRE_DIA[d]}</label>'
            for d in DIAS_SEMANA
        )
        cuerpo = (
            aviso
            + '<div class="card"><div class="franja">Configuración del menú</div>'
            '<form method="post" action="/config">'
            '<div class="row">'
            + _num("num_comensales", "Comensales", int(cfg.get("num_comensales", 2)),
                   "Cuántas personas comen de cada receta.", "1", "1")
            + _num("kcal_por_comensal", "kcal por persona y día",
                   int(cfg.get("kcal_por_comensal", 2000)),
                   "Energía diaria objetivo. El menú cubre la parte de comida y cena.", "50", "1000")
            + _num("semanas_plan", "Semanas a planificar", int(cfg.get("semanas_plan", 1)),
                   "Cuántas semanas de menú se generan de una vez.", "1", "1")
            + "</div><div class='row'>"
            + _num("dias_repeticion", "Días entre repeticiones",
                   int(cfg.get("dias_repeticion", 7)),
                   "Cada cuántos días puede volver a comerse la misma receta "
                   "(7 = no se repite en la semana; 14 = tampoco a la siguiente).", "1", "1")
            + _num("racion_frac_min", "Ración mínima (%)",
                   round(float(cfg.get("racion_frac_min", 0.75)) * 100),
                   "Porción más pequeña que aceptas en una comida, en % de una ración "
                   "(75 = tres cuartos de ración).", "5", "10")
            + _num("racion_frac_max", "Ración máxima (%)",
                   round(float(cfg.get("racion_frac_max", 1.25)) * 100),
                   "Porción más grande, en % de una ración (125 = ración y cuarto). "
                   "Puede ser mayor de 100.", "5", "50")
            + "</div><div class='row'>"
            + _slider("sabor_pct", "Peso del sabor", _pct(cfg, "sabor_pct"),
                      "0 % = solo importa el precio; 100 % = manda el sabor (recetas mejor "
                      "valoradas) frente a que sean baratas.")
            + _slider("cena_ligera_pct", "Peso cena ligera", _pct(cfg, "cena_ligera_pct"),
                      "Cuánto se premia que la cena sea ligera (pocas calorías) y sencilla "
                      "(pocos ingredientes).")
            + _slider("favoritas_pct", "Peso favoritas", _pct(cfg, "favoritas_pct"),
                      "Ventaja de tus recetas favoritas ★ para entrar en el menú. Nunca les "
                      "permite saltarse los nutrientes.")
            + _slider("reutilizacion_pct", "Racionalizar la compra",
                      _pct(cfg, "reutilizacion_pct"),
                      "Premia que las recetas compartan productos (menos productos distintos "
                      "= menos sobras). 0 % = desactivado. Sube el tiempo de cálculo (hasta "
                      "~25 s con valores altos); ~40 % da buen equilibrio.")
            + "</div>"
            "<label>Días batchcooking (laborales: plato único en tanda para llevar)</label>"
            f'<div style="margin:6px 0 4px">{casillas}</div>'
            '<p class="note">Esos días la comida sale solo de recetas que aguantan bien '
            "cocinadas en tanda y transportadas (guisos, arroces, ensaladas con aliño aparte…), "
            "y es un plato único sin postre.</p>"
            '<div style="margin-top:14px"><button class="btn" type="submit">Guardar</button></div>'
            "</form>"
            '<p class="meta">Los cambios se guardan en <code>config.usuario.yaml</code> '
            "(no tocan config.yaml); borra ese fichero para volver a los valores base.</p></div>"
        )
        # --- Actualizaciones (Fase 11): un solo boton, repo fijo, instala solo ---
        info = _ACTUALIZACION["estado"]
        if info:
            estado_upd = (
                f'<p class="ok">✨ Nueva versión <b>{html.escape(info.version)}</b> disponible.</p>'
            )
        elif _ACTUALIZACION["comprobado"]:
            estado_upd = f'<p class="meta">Estás en la última versión (v{__version__}).</p>'
        else:
            estado_upd = '<p class="meta">Pulsa el botón para comprobar si hay una versión nueva.</p>'
        cuerpo += (
            '<div class="card"><div class="franja">Actualizaciones de la aplicación</div>'
            f'<p class="meta">Versión instalada: <b>{__version__}</b></p>'
            '<form method="post" action="/actualizaciones/comprobar">'
            '<button class="btn" type="submit">Buscar actualización</button></form>'
            f"{estado_upd}"
            '<p class="note">Comprueba GitHub: si hay una versión nueva, la descarga e inicia el '
            "instalador automáticamente; si ya estás al día, te lo indica.</p></div>"
        )
        return _pagina("Configuración", cuerpo)

    @app.post("/actualizaciones/comprobar")
    def actualizaciones_comprobar():
        """Comprueba GitHub y, si hay version nueva, la descarga e instala."""
        info = hay_actualizacion()
        _ACTUALIZACION["estado"] = info
        _ACTUALIZACION["comprobado"] = True
        if info is None:
            msg = f"Ya tienes la última versión de Sazón (v{__version__})."
        else:
            _ok, msg = instalar(info)
        return RedirectResponse(f"/config?msg={quote(msg)}", status_code=303)

    @app.post("/config")
    async def config_save(request: Request):
        form = await request.form()
        try:
            cambios = {
                "num_comensales": int(form.get("num_comensales", 2)),
                "kcal_por_comensal": float(form.get("kcal_por_comensal", 2000)),
                "semanas_plan": int(form.get("semanas_plan", 1)),
                "dias_repeticion": int(form.get("dias_repeticion", 7)),
                # Raciones en % -> fraccion. La maxima puede pasar de 100%.
                "racion_frac_min": max(0.1, float(form.get("racion_frac_min", 75)) / 100),
                "racion_frac_max": max(0.5, float(form.get("racion_frac_max", 125)) / 100),
                # Pesos como % 0-100 (claves nuevas *_pct).
                "sabor_pct": float(form.get("sabor_pct", 50)),
                "cena_ligera_pct": float(form.get("cena_ligera_pct", 50)),
                "favoritas_pct": float(form.get("favoritas_pct", 50)),
                "reutilizacion_pct": float(form.get("reutilizacion_pct", 0)),
                "batchcooking": {"dias": [str(d) for d in form.getlist("dias_bc")]},
            }
            # Retira las claves antiguas del overlay para que manden los %.
            cambios.update(
                {
                    "peso_palatabilidad": None,
                    "peso_cena_ligera_simple": None,
                    "peso_favorita": None,
                    "peso_reutilizacion": None,
                }
            )
        except (TypeError, ValueError):
            return RedirectResponse("/config?msg=Error: valores no válidos.", status_code=303)
        guardar_overlay(config_path, cambios)
        return RedirectResponse("/config?msg=Configuración guardada.", status_code=303)

    return app


app = crear_app()
