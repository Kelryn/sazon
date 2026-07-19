"""Plantillas HTML y helpers de render de la interfaz web (Lote 9, #86: extraido
de app.py). Funciones puras: reciben los datos ya cargados y devuelven HTML/CSS
embebido (sin CDN, para empaquetar limpio a .exe). No abren conexion a la BD."""

from __future__ import annotations

import dataclasses
import html

from ..configuracion import DIAS_SEMANA
from ..optimizacion.nutrientes import objetivos_semanales
from ..optimizacion.planes import asignar_dias
from ..optimizacion.servicio import _PESOS_PCT, config_nutricion, peso_interno
from ..recetas.catalogo_ingredientes import nutrientes_receta
from ..recetas.manual import UNIDADES
from .marca import ESLOGAN, LOGO_SVG, NOMBRE, TEMA_SCRIPT, TOKENS_CSS, favicon_data_uri


def _pct(cfg: dict, clave_pct: str) -> float:
    """Valor 0-100 actual de un peso (desde la clave nueva, la antigua o el defecto)."""
    _antigua, maximo, _def = _PESOS_PCT[clave_pct]
    return round(peso_interno(cfg, clave_pct) / maximo * 100)


_NOMBRE_DIA = {
    "lun": "Lunes", "mar": "Martes", "mie": "Miércoles", "jue": "Jueves",
    "vie": "Viernes", "sab": "Sábado", "dom": "Domingo",
}

# Nombres "bonitos" de los nutrientes, en el orden pedido por el usuario.
# 'grasas' del catalogo son grasas TOTALES: se muestran como insaturadas
# restando las saturadas.
_ORDEN_NUTRIENTES = [
    ("energia_kcal", "Energía", "Kcal"),
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
/* --- Barra de herramientas (Lote 11): fija; Menu/Compra/Recetas/Catalogo + logo + config + ayuda --- */
header { position: sticky; top: 0; z-index: 20; background: var(--barra); color: #fff;
  padding: 10px 14px; display: flex; align-items: center; gap: 8px; }
header .mainnav { display: flex; gap: 6px; }
header .mainnav a { position: relative; color: #fff; text-decoration: none; font-weight: 700;
  font-size: 13px; padding: 7px 12px; border-radius: 7px; transition: background-color .15s; }
header .mainnav a.n-menu:hover { background: #5a6e43; }
header .mainnav a.n-compra:hover { background: #6b6539; }
header .mainnav a.n-recetas:hover { background: #4f6a58; }
header .mainnav a.n-catalogo:hover { background: #5a6553; }
header .mainnav a.act::after { content: ""; position: absolute; bottom: 3px; left: 50%;
  transform: translateX(-50%); width: 20px; height: 2px; background: var(--dorado); border-radius: 1px; }
header .brand { flex: 1; display: flex; align-items: center; justify-content: center; }
header .brand svg { height: 30px; }
header .btn-tool { width: 30px; height: 30px; border-radius: 7px; border: 0; background: transparent;
  color: #eef1e6; font-size: 15px; font-weight: 700; cursor: pointer; text-decoration: none;
  display: inline-flex; align-items: center; justify-content: center; transition: background-color .15s; }
header .btn-tool:hover { background: #5c6d48; }
main { max-width: 760px; margin: 0 auto; padding: 14px; }
/* Modo ayuda (❓): paneles ocultos que el boton de la barra muestra. */
.ayuda { display: none; background: #fbf7e8; border: 1px solid #ece0b8; color: #6b6033;
  border-radius: var(--radio); padding: 14px 16px; margin-bottom: 14px; font-size: 13px; line-height: 1.55; }
body.ayuda-on .ayuda { display: block; }
:root[data-theme="dark"] .ayuda { background: #2a2716; border-color: #4a442a; color: #d8cfa6; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .ayuda {
  background: #2a2716; border-color: #4a442a; color: #d8cfa6; } }
.card { background: var(--surface); border-radius: var(--radio); padding: 16px 18px;
  margin-bottom: 14px; box-shadow: var(--shadow); border: 1px solid var(--border); }
.card.ok { border-color: var(--verde); } .card.warn { border-color: var(--terracota); }
.franja { font-weight: 700; color: var(--verde-osc); font-size: 15px; margin: 0 0 11px;
  padding-bottom: 11px; border-bottom: 1px solid var(--border); }
.fav { color: var(--dorado); font-weight: 700; }
.chip { display: inline-block; background: var(--chip-bg); color: var(--chip-text);
  border-radius: 20px; padding: 3px 11px; font-size: 11px; margin: 2px 3px 2px 0; white-space: nowrap; }
.meta { color: var(--muted); font-size: 12px; }
.note { color: var(--muted); font-size: 12px; margin: 2px 0 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px; border-bottom: 1px solid #f1eee2; vertical-align: middle; }
th { color: var(--muted); font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }
/* Tabla del menu semanal (spec Lote 11): tintes por columna, barritas cortas en la
   cabecera, SIN divisores horizontales (solo borde vertical entre columnas), hover
   que oscurece el tinte de la propia celda. */
.menu-tabla { table-layout: fixed; }
.menu-tabla th, .menu-tabla td { border-bottom: none; }
.menu-tabla th { position: relative; text-align: center; padding: 8px 8px 13px; }
.menu-tabla th::after { content: ""; position: absolute; bottom: 6px; left: 50%;
  transform: translateX(-50%); width: 20px; height: 2px; border-radius: 1px; }
.menu-tabla th.h-dia { width: 27%; background: var(--tinte-dia); }
.menu-tabla th.h-dia::after { background: var(--text); }
.menu-tabla th.h-comida { background: var(--tinte-com); }
.menu-tabla th.h-comida::after { background: var(--dorado); }
.menu-tabla th.h-cena { background: var(--tinte-cen); }
.menu-tabla th.h-cena::after { background: #8a6f9c; }
.menu-tabla td { text-align: center; vertical-align: middle; padding: 9px 8px; }
.menu-tabla td + td { border-left: 1px solid var(--border); }
.menu-tabla td.c-dia { text-align: left; background: var(--tinte-dia); padding-left: 12px; }
.menu-tabla td.c-dia .coste-dia { display: block; font-size: 10px; color: #b3ae9e; font-weight: 400; }
.menu-tabla td.c-com { background: var(--tinte-com); transition: background-color .15s; }
.menu-tabla td.c-cen { background: var(--tinte-cen); transition: background-color .15s; }
.menu-tabla td.c-com:not(.vacia):hover { background: var(--tinte-com-h); }
.menu-tabla td.c-cen:not(.vacia):hover { background: var(--tinte-cen-h); }
.menu-tabla td.vacia { color: #c9c4ae; }
.card.sin-pad { padding: 0; overflow: hidden; }
.tabla-pie { padding: 10px 18px 14px; }
/* Fila de acciones del menu: [Generar plan + regenerar] | selector de semana | Historial. */
.acc-menu { display: grid; grid-template-columns: 27fr 36.5fr 36.5fr; align-items: center;
  margin-bottom: 10px; }
.acc-menu .a-dia { display: flex; gap: 6px; padding-right: 10px; }
.acc-menu .a-dia form:first-child { flex: 1; display: flex; }
button.gp { flex: 1; background: var(--sec-bg); color: var(--verde-osc); border: 0;
  border-radius: 7px; height: 29px; padding: 0 4px; font: inherit; font-size: 12px;
  font-weight: 600; cursor: pointer; transition: background-color .15s; }
button.gp:hover { background: var(--sec-bg-h); }
button.gp-ico { width: 29px; height: 29px; flex: none; border: 0; border-radius: 7px;
  background: var(--ico-bg); color: #4a4636; font-size: 14px; display: flex;
  align-items: center; justify-content: center; cursor: pointer; padding: 0;
  transition: background-color .15s; }
button.gp-ico:hover { background: var(--sec-bg-h); }
.acc-sem { position: relative; display: flex; align-items: center; justify-content: center;
  height: 29px; font-size: 13px; font-weight: 600; color: var(--text); }
.acc-sem .fs { position: absolute; width: 28px; height: 28px; display: flex;
  align-items: center; justify-content: center; border-radius: 7px; background: transparent;
  color: #4a4636; font-size: 12px; text-decoration: none; transition: background-color .15s; }
.acc-sem a.fs:hover { background: var(--flecha-h); }
.acc-sem .fs.izq { left: 0; transform: translateX(-50%); }
.acc-sem .fs.der { right: 0; transform: translateX(50%); }
.acc-sem .fs.off { color: #c8c3b2; }
.acc-hist { display: flex; justify-content: flex-end; }
.bc-line { display: flex; align-items: center; gap: 6px; font-weight: 400; font-size: 12px;
  color: var(--muted); margin: 0 0 12px; }
/* Tarjeta plegable (nutrientes): cabecera con hover y chevron. */
button.card-plegar { display: flex; width: 100%; align-items: center;
  justify-content: space-between; background: transparent; border: 0; padding: 13px 18px;
  font: inherit; font-size: 12px; font-weight: 700; color: var(--verde-osc); cursor: pointer;
  transition: background-color .15s; border-bottom: 1px solid var(--neutro-bg); }
button.card-plegar:hover { background: var(--plegar-h); }
button.card-plegar .chev { color: #a8a08a; font-size: 11px; transition: color .15s; }
button.card-plegar:hover .chev { color: #5b5748; }
.nutri-tabla { table-layout: fixed; }
.nutri-tabla th, .nutri-tabla td { border-bottom: none; text-align: center; padding: 8px 10px; }
.nutri-tabla th:first-child, .nutri-tabla td:first-child { text-align: left;
  width: 34%; padding-left: 18px; }
.nutri-tabla th:last-child { width: 9%; }
.nutri-tabla tr:nth-child(even) td { background: var(--fila-nutri); }
.nutri-tabla .obj { color: var(--muted); }
.uni { color: #a8a08a; font-weight: 400; }
.nutri-foot { background: var(--nota-bg); border-top: 1px solid var(--neutro-bg);
  padding: 10px 18px; font-size: 11px; color: var(--muted); margin: 0; }
.ok { color: var(--verde-accion); } .warn { color: var(--terracota); font-weight: 600; }
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  background: var(--verde-accion); color: #fff; border: 0; padding: 9px 16px; border-radius: 7px;
  font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; transition: background-color .15s; }
.btn:hover { background: var(--verde-accion-h); }
.btn.sec { background: var(--sec-bg); color: var(--verde-osc); }
.btn.sec:hover { background: var(--sec-bg-h); }
.btn.neu { background: var(--neutro-bg); color: #4a4636; }
.btn.neu:hover { background: var(--neutro-bg-h); }
.btn.mini { padding: 5px 11px; font-size: 12px; }
/* Control segmentado (p. ej. tema Claro/Oscuro/Sistema): activo verde, resto apagado. */
.seg { display: inline-flex; gap: 4px; background: var(--neutro-bg); padding: 4px; border-radius: 9px; }
.seg button { border: 0; background: transparent; color: var(--muted); font: inherit; font-size: 13px;
  font-weight: 600; padding: 7px 16px; border-radius: 7px; cursor: pointer;
  transition: background-color .15s, color .15s; }
.seg button:hover { background: var(--sec-bg); color: var(--verde-osc); }
.seg button.on, .seg button.on:hover { background: var(--verde-accion); color: #fff; }
input, textarea, select { width: 100%; padding: 8px 10px; border: 1px solid var(--border);
  border-radius: 8px; font: inherit; font-size: 13px; background: var(--bg); color: var(--text); }
input:hover, input:focus, textarea:hover, textarea:focus, select:hover, select:focus {
  border-color: var(--verde); outline: none; box-shadow: none; }
input[type=range] { -webkit-appearance: none; appearance: none; width: 100%; height: 6px; padding: 0;
  border: 0; border-radius: 3px; background: #cdd8bd; cursor: pointer; }
input[type=range]:hover, input[type=range]:focus { border: 0; }
input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 12px;
  height: 12px; border-radius: 50%; background: #fff; border: 1px solid #aeb99a; cursor: pointer; }
input[type=range]::-moz-range-thumb { width: 12px; height: 12px; border-radius: 50%; background: #fff;
  border: 1px solid #aeb99a; cursor: pointer; }
/* !important: varios formularios llevan style="width:auto" inline (contra el
   input{width:100%} antiguo); sin esto el checkbox custom colapsa a una barrita. */
input[type=checkbox] { appearance: none; -webkit-appearance: none;
  width: 16px !important; height: 16px !important; padding: 0;
  border: 1px solid #cfcabb; border-radius: 4px; background: var(--surface); cursor: pointer;
  position: relative; vertical-align: -3px; flex: none; }
input[type=checkbox]:hover { border-color: #b7b09a; }
input[type=checkbox]:checked::after { content: "\\2713"; position: absolute; inset: 0; display: flex;
  align-items: center; justify-content: center; color: var(--verde); font-size: 12px; font-weight: 700; }
label { display: block; margin: 10px 0 4px; font-weight: 600; font-size: 12px; color: #5b5748; }
.row { display: flex; gap: 14px; flex-wrap: wrap; }
.row > div { flex: 1; min-width: 150px; }
.big { font-size: 22px; font-weight: 700; color: var(--text); }
/* Enlaces de receta: texto tierra oscuro, SIN subrayado; el hover cambia el FONDO
   (regla de diseño), no decora el texto. */
a.receta { color: var(--verde-osc); text-decoration: none; border-radius: 5px;
  padding: 1px 3px; transition: background-color .15s; }
a.receta:hover { color: var(--verde-osc); text-decoration: none; background: var(--hover-fila); }
/* Dentro de la tabla del menu el hover lo pinta la CELDA (tinte propio), no el enlace. */
.menu-tabla a.receta:hover { background: transparent; }
.arrows { display: inline-flex; gap: 8px; align-items: center; margin-left: 10px; }
.arrows a, .arrows span.off { padding: 3px 11px; border-radius: 7px; background: var(--neutro-bg);
  color: var(--verde-osc); text-decoration: none; font-weight: 700; }
.arrows a:hover { background: var(--neutro-bg-h); }
.arrows span.off { background: var(--neutro-bg); color: var(--muted); }
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
/* Enlace "saltar al contenido" (#70), oculto salvo con foco de teclado. */
.skip-link { position: absolute; left: -9999px; top: 0; background: var(--verde);
  color: #fff; padding: 8px 14px; border-radius: 0 0 8px 0; z-index: 100; }
.skip-link:focus { left: 0; }
/* Vista de impresion (#68): sin cabecera/nav/botones, fondo blanco, sin sombras. */
@media print {
  header, form, .btn, .arrows a[href], .off { display: none !important; }
  body { background: #fff !important; }
  .card { box-shadow: none !important; border: 1px solid #ccc !important; break-inside: avoid; }
  a[href]:after { content: "" !important; }
}
"""
)


# Textos del modo ayuda (❓), por sección de la barra. El botón ❓ de la cabecera
# los muestra/oculta (body.ayuda-on). Se pueden ampliar sin tocar el resto de la UI.
AYUDA_SECCION = {
    "menu": (
        "<b>Menú semanal.</b> «Generar plan» crea un plan nuevo de las semanas "
        "configuradas, sin repetir recetas dentro de la semana (regla configurable en "
        "Configuración). El botón «↺» genera una alternativa solo de la semana visible, "
        "y «Cambiar por otra» sustituye una receta concreta. Con «Historial» ves y "
        "repites planes anteriores. La casilla de batchcooking fuerza platos únicos "
        "transportables en todas las comidas. Pulsa una receta para ver sus "
        "ingredientes y precios de Alcampo."
    ),
    "compra": (
        "<b>Lista de la compra.</b> Reúne todos los productos del menú de la semana con sus "
        "precios de Alcampo, agrupados como un recibo. Puedes exportarla e imprimirla."
    ),
    "recetas": (
        "<b>Recetas.</b> Todas las recetas disponibles: las tuyas (editables) y las del "
        "catálogo (solo lectura). Crea una con «Nueva receta», importa por URL, o busca "
        "sustitutos de cocina con «Sustituciones»."
    ),
    "catalogo": (
        "<b>Catálogo.</b> Los productos de Alcampo en la base de datos. Actualízalo por "
        "categorías, corrige datos de un producto, empareja ingredientes sin producto "
        "(«Correcciones») o busca en todo («Buscar»)."
    ),
}


def _pagina(titulo: str, cuerpo: str, refrescar: int | None = None, activa: str = "") -> str:
    """Envuelve el cuerpo en la plantilla base (barra de herramientas + tema).

    `activa` marca la sección de la barra (menu/compra/recetas/catalogo) para
    pintar la barrita mostaza bajo el botón activo.
    """
    meta = f'<meta http-equiv="refresh" content="{refrescar}">' if refrescar else ""

    def _nav(sec: str, url: str, txt: str) -> str:
        cls = f"n-{sec}" + (" act" if activa == sec else "")
        return f'<a class="{cls}" href="{url}">{txt}</a>'

    barra = (
        "<header>"
        '<nav class="mainnav">'
        + _nav("menu", "/", "Menú")
        + _nav("compra", "/compra", "Compra")
        + _nav("recetas", "/recetas", "Recetas")
        + _nav("catalogo", "/catalogo", "Catálogo")
        + "</nav>"
        f'<a class="brand" href="/" title="{NOMBRE} — {ESLOGAN}">{LOGO_SVG}</a>'
        '<a class="btn-tool" href="/config" title="Configuración" aria-label="Configuración">⚙</a>'
        '<button class="btn-tool" type="button" title="Mostrar/ocultar ayuda" aria-label="Ayuda"'
        ' onclick="document.body.classList.toggle(\'ayuda-on\')">?</button>'
        "</header>"
    )
    ayuda = AYUDA_SECCION.get(activa, "")
    panel_ayuda = f'<div class="ayuda">{ayuda}</div>' if ayuda else ""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{meta}
<link rel="icon" href="{favicon_data_uri()}">
<title>{html.escape(titulo)} · {NOMBRE}</title><style>{_ESTILO}</style>{TEMA_SCRIPT}</head><body>
<a href="#contenido" class="skip-link">Saltar al contenido</a>
{barra}
<main id="contenido">{panel_ayuda}{cuerpo}</main></body></html>"""


# ------------------------------- render del menu -------------------------------


def _fila_nutrientes(datos: dict, cfg: dict) -> str:
    """Tabla de nutrientes POR PERSONA Y DIA (total/dia y objetivo/dia)."""
    dias = int(datos.get("dias", 7))
    tot = datos.get("nutricion_total", {}) or {}
    num_com = float(datos.get("num_comensales", 2))  # adultos-equivalentes (#108)
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
            objetivo = f"{centro - mas_menos:.0f} - {centro + mas_menos:.0f}"
            en_banda = centro - mas_menos - 0.5 <= val_dia <= centro + mas_menos + 0.5
        elif clave == "grasas_insat":
            bg, bs = bandas.get("grasas"), bandas.get("grasas_sat")
            lo = max(0.0, (bg.minimo or 0) - (bs.maximo or 0)) / div if bg else 0
            hi = (bg.maximo or 0) / div if bg else 0
            objetivo = f"{lo:.0f} - {hi:.0f}"
            en_banda = lo - 0.5 <= val_dia <= hi + 0.5
        else:
            b = bandas.get(clave)
            lo = f"{b.minimo / div:.0f}" if b and b.minimo is not None else "—"
            hi = f"{b.maximo / div:.0f}" if b and b.maximo is not None else "—"
            objetivo = f"{lo} - {hi}"
            en_banda = True
            if b and b.minimo is not None and val_dia < b.minimo / div - 0.5:
                en_banda = False
            if b and b.maximo is not None and val_dia > b.maximo / div + 0.5:
                en_banda = False
        estado = '<span class="ok">✓</span>' if en_banda else '<span class="warn">✗</span>'
        filas += (
            f'<tr><td>{nombre} <span class="uni">{unidad}</span></td><td>{val_dia:.0f}</td>'
            f'<td class="obj">{objetivo}</td><td>{estado}</td></tr>'
        )
    frac = cfg_nut.fraccion_menu
    # Tarjeta plegable (spec): cabecera con hover y chevron, tabla sin divisores con
    # filas alternas, y nota al pie sobre fondo mas oscuro.
    return (
        '<div class="card sin-pad">'
        '<button class="card-plegar" type="button" aria-expanded="true" '
        "onclick=\"var b=this.nextElementSibling;var abierto=b.style.display==='none';"
        "b.style.display=abierto?'':'none';this.setAttribute('aria-expanded',abierto);"
        "this.querySelector('.chev').textContent=abierto?'▴':'▾';\">"
        'Nutrientes por persona y día <span class="chev">▴</span></button>'
        "<div>"
        '<table class="nutri-tabla"><tr><th>Nutriente</th><th>Total/día</th>'
        "<th>Objetivo/día</th><th></th></tr>"
        f"{filas}</table>"
        f'<p class="nutri-foot">Objetivos escalados a lo que cubre el menú: el '
        f"{frac * 100:.0f}% de la energía del día (comida {cfg_nut.pct_comida * 100:.0f}% + "
        f"cena {cfg_nut.pct_cena * 100:.0f}%, reparto recomendado FEN/AESAN). Con "
        f"{cfg_nut.kcal_por_comensal_dia:.0f} kcal/día configuradas, comida+cena deben aportar "
        f"{cfg_nut.kcal_por_comensal_dia * frac:.0f} kcal.</p></div></div>"
    )


_NUTRI_COLOR = {"A": "#038141", "B": "#85bb2f", "C": "#fecb02", "D": "#ee8100", "E": "#e63e11"}


def _badge_nutri(letra: str) -> str:
    """Distintivo Nutri-Score (A verde ... E rojo)."""
    if not letra or letra not in _NUTRI_COLOR:
        return ""
    return (
        f'<span title="Nutri-Score {letra} (estimado)" style="display:inline-block;'
        f"min-width:16px;text-align:center;background:{_NUTRI_COLOR[letra]};color:#fff;"
        f'font-weight:800;border-radius:4px;padding:0 4px;font-size:11px">{letra}</span>'
    )


def _link_receta(rid: str, info: dict, raciones: float | None = None) -> str:
    fav = ' <span class="fav">★</span>' if info.get("es_favorita") else ""
    nutri = " " + _badge_nutri(info.get("nutri", "")) if info.get("nutri") else ""
    rac = f' <span class="meta">({raciones:.2g} rac/pers.)</span>' if raciones else ""
    # Explicabilidad (#35): por que entro esta receta -> tooltip al pasar el raton.
    porque = info.get("por_que", "")
    title = f' title="{html.escape(porque)}"' if porque else ""
    marca = ' <span class="meta" title="' + html.escape(porque) + '">ⓘ</span>' if porque else ""
    return (
        f'<a class="receta" href="/receta/{html.escape(rid)}"{title}>'
        f'{html.escape(info.get("titulo", rid))}</a>{fav}{nutri}{rac}{marca}'
    )


# Umbrales de alerta POR COMILA y persona (#10): OMS sal <5 g/día, azúcares libres
# <~50 g/día -> por comida (2 comidas grandes) avisamos por encima de estos.
_SAL_ALERTA_COMIDA = 2.5   # g de sal por comida y persona
_AZUCAR_ALERTA_COMIDA = 25  # g de azúcares por comida y persona


def _alerta_comida(info: dict, raciones: float) -> str:
    """Icono de aviso si una comida se pasa de sal o azúcar (por persona) (#10)."""
    sal = (info.get("sal", 0) or 0) * raciones
    azu = (info.get("azucares", 0) or 0) * raciones
    avisos = []
    if sal > _SAL_ALERTA_COMIDA:
        avisos.append(f"sal alta ({sal:.1f} g)")
    if azu > _AZUCAR_ALERTA_COMIDA:
        avisos.append(f"azúcar alto ({azu:.0f} g)")
    if not avisos:
        return ""
    return (
        f' <span title="{html.escape("; ".join(avisos))}" '
        f'style="cursor:help">⚠️</span>'
    )


def _tabla_dias(datos: dict) -> str:
    info = datos.get("recetas_info", {}) or {}
    raciones = datos.get("raciones", {}) or {}
    sel_com = datos.get("seleccion_comida", {}) or {}
    sel_cen = datos.get("seleccion_cena", {}) or {}
    num_com = float(datos.get("num_comensales", 1) or 1)

    def _celda(rid: str | None, col: str) -> tuple[str, float]:
        """Celda de comida/cena con su tinte de columna; devuelve (html, coste)."""
        if not rid:
            return f'<td class="c-{col} vacia">–</td>', 0.0
        n_usos = (sel_com.get(rid, 0) or 0) + (sel_cen.get(rid, 0) or 0)
        x = raciones.get(rid)
        por_comida = (x / n_usos) if (x and n_usos) else None
        enlace = _link_receta(rid, info.get(rid, {}), por_comida)
        aviso = _alerta_comida(info.get(rid, {}), por_comida or 1.0)
        coste = (info.get(rid, {}).get("coste_racion") or 0.0) * (por_comida or 1.0) * num_com
        return f'<td class="c-{col}">{enlace}{aviso}</td>', coste

    filas = ""
    for dia, comida, cena, es_bc in asignar_dias(datos, DIAS_SEMANA):
        etiqueta = ' <span class="meta">🍱 plato único</span>' if es_bc else ""
        td_com, c1 = _celda(comida, "com")
        td_cen, c2 = _celda(cena, "cen")
        coste_dia = (
            f'<span class="coste-dia">{c1 + c2:.2f} €</span>' if (c1 + c2) > 0 else ""
        )
        filas += (
            f'<tr><td class="c-dia"><b>{_NOMBRE_DIA.get(dia, dia)}</b>{etiqueta}{coste_dia}</td>'
            f"{td_com}{td_cen}</tr>"
        )
    tabla = (
        '<table class="menu-tabla"><tr>'
        '<th class="h-dia">Día</th><th class="h-comida">🌞 Comida</th>'
        '<th class="h-cena">🌙 Cena</th>'
        f"</tr>{filas}</table>"
    )
    return tabla + f'<div class="tabla-pie">{_resumen_grupos(datos)}</div>'


def _banner_hoy(datos: dict) -> str:
    """Recordatorio "hoy toca" (#67): busca, dentro de la semana MOSTRADA, el dia
    cuyo nombre coincide con el de hoy (lun..dom) y muestra que hay para comer.
    No conoce fechas reales del plan (las semanas son abstractas lun..dom); es un
    recordatorio por dia de la semana, no por fecha exacta."""
    import datetime

    info = datos.get("recetas_info", {}) or {}
    hoy = DIAS_SEMANA[datetime.date.today().weekday()]
    for dia, comida, cena, es_bc in asignar_dias(datos, DIAS_SEMANA):
        if dia != hoy:
            continue
        partes = []
        if comida:
            partes.append(f"comida: {html.escape(info.get(comida, {}).get('titulo', comida))}")
        if cena:
            partes.append(f"cena: {html.escape(info.get(cena, {}).get('titulo', cena))}")
        if not partes:
            return ""
        etiqueta = " 🍱 (plato único)" if es_bc else ""
        return (
            '<div class="card" style="border-left:4px solid var(--dorado)">'
            f"📅 <b>Hoy ({_NOMBRE_DIA.get(hoy, hoy)}) toca{etiqueta}:</b> "
            + " · ".join(partes) + "</div>"
        )
    return ""


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

    def chk(k: str) -> str:
        return " checked" if es_edicion and datos.get(k) else ""
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
            bg = dia.get("grasas")
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
