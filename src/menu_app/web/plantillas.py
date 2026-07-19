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
.btn.rev { background: #f4f2ec; color: var(--muted); }
.btn.rev:hover { background: #ece9dd; }
:root[data-theme="dark"] .btn.rev { background: var(--neutro-bg); }
:root[data-theme="dark"] .btn.rev:hover { background: var(--neutro-bg-h); }
.btn.acc118 { width: 118px; height: 32px; padding: 0; }
/* Tabla que llega a los bordes de la tarjeta, con encabezado gris (catalogo). */
.tabla-bleed { margin: 0 -18px; }
.tabla-bleed th:first-child, .tabla-bleed td:first-child { padding-left: 18px; }
.tabla-bleed th:last-child, .tabla-bleed td:last-child { padding-right: 18px; }
table.cat-tabla th { background: var(--thead-bg); color: var(--thead-texto);
  border-bottom: 1px solid var(--thead-borde); }
table.cat-tabla td { border-bottom: none; }
table.cat-tabla tr:nth-child(odd) td { background: var(--fila-alt); }
.apto-si { color: #4d7a3a; font-weight: 700; }
/* Lista de la compra (spec Lote 11): tabla en grid con encabezado de color,
   filas del mismo alto con hover de fila entera y columna de cambio de precio. */
.lc-head, .lc-fila, .lc-total-fila { display: grid;
  grid-template-columns: 34px 1fr 56px 66px 56px 52px 56px 60px; align-items: center;
  padding: 0 18px; }
.lc-head { background: #ece7d8; }
.lc-head > div { font-size: 11px; text-transform: uppercase; letter-spacing: .3px;
  color: #1c1c18; font-weight: 700; padding: 8px 0; }
.lc-fila { height: 36px; font-size: 12px; color: var(--text);
  transition: background-color .15s; }
.lc-fila.a { background: #f7f4ea; }
.lc-fila.b { background: #f2efe3; }
.lc-fila:hover { background: #e6efdd; }
.lc-fila a { color: var(--text); text-decoration: none; }
.lc-fila .nom { white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  padding-right: 8px; }
.lc-c { text-align: center; }
.lc-sobra { color: #8f8a75; }
.lc-sube { color: var(--terracota); font-size: 11px; font-weight: 600; }
.lc-baja { color: #4d7a3a; font-size: 11px; font-weight: 600; }
.lc-sec { display: flex; align-items: center; gap: 8px; padding: 10px 18px 6px;
  font-size: 12px; font-weight: 700; color: #9b9683;
  border-bottom: 1px solid var(--border); }
.lc-total-fila { border-top: 2px solid #2b2b26; font-weight: 800; font-size: 13px;
  padding-top: 10px; padding-bottom: 10px; }
.lc-nota { background: var(--nota-bg); border-top: 1px solid var(--neutro-bg);
  padding: 10px 18px; font-size: 12px; color: var(--muted); margin: 0; }
.lc-fila.comprado > div:not(:first-child) { opacity: .45; text-decoration: line-through; }
.btn.dl { width: 122px; height: 34px; padding: 0; }
:root[data-theme="dark"] .lc-head { background: var(--thead-bg); }
:root[data-theme="dark"] .lc-head > div { color: var(--text); }
:root[data-theme="dark"] .lc-fila.a { background: var(--fila-alt); }
:root[data-theme="dark"] .lc-fila.b { background: var(--neutro-bg); }
:root[data-theme="dark"] .lc-fila:hover { background: var(--hover-fila); }
:root[data-theme="dark"] .lc-total-fila { border-top-color: var(--text); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .lc-head { background: var(--thead-bg); }
  :root:not([data-theme="light"]) .lc-head > div { color: var(--text); }
  :root:not([data-theme="light"]) .lc-fila.a { background: var(--fila-alt); }
  :root:not([data-theme="light"]) .lc-fila.b { background: var(--neutro-bg); }
  :root:not([data-theme="light"]) .lc-fila:hover { background: var(--hover-fila); }
  :root:not([data-theme="light"]) .lc-total-fila { border-top-color: var(--text); }
}
/* Editor de receta (spec Lote 11). */
.ing-fila { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
.ing-fila input[name=ing_nombre] { flex: 1; height: 38px; }
.ing-cant { width: 74px !important; text-align: center; height: 38px; flex: none; }
.ing-uni { width: 64px !important; text-align: center; height: 38px; flex: none; }
textarea.prep { display: block; width: calc(100% + 36px); margin: 4px -18px 0;
  border-radius: 0; border-left: 0; border-right: 0; border-color: var(--border);
  background: var(--surface); resize: none; overflow: hidden; padding: 10px 18px;
  transition: background-color .15s; }
textarea.prep:hover, textarea.prep:focus { background: #f7f5ee; border-color: var(--border); }
:root[data-theme="dark"] textarea.prep:hover,
:root[data-theme="dark"] textarea.prep:focus { background: var(--neutro-bg); }
.btn.w130 { width: 130px; height: 36px; padding: 0; }
.btn.rojo { background: #f6e7e3; color: var(--terracota); }
.btn.rojo:hover { background: #f0d5cf; }
:root[data-theme="dark"] .btn.rojo { background: #3a2620; }
:root[data-theme="dark"] .btn.rojo:hover { background: #472e26; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) textarea.prep:hover,
  :root:not([data-theme="light"]) textarea.prep:focus { background: var(--neutro-bg); }
  :root:not([data-theme="light"]) .btn.rojo { background: #3a2620; }
  :root:not([data-theme="light"]) .btn.rojo:hover { background: #472e26; }
}
/* Valoraciones (spec Lote 11): baremos con estrellas interactivas y selectores ±. */
.baremo-fila { display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--neutro-bg); font-size: 13px;
  color: var(--text); }
.baremo-fila:last-of-type { border-bottom: none; }
.estrellas { display: inline-flex; gap: 2px; }
.estrellas button { background: transparent; border: 0; font-size: 18px; line-height: 1;
  cursor: pointer; color: #dcd7c6; padding: 1px 2px; transition: transform .1s, color .1s; }
.estrellas button.on { color: var(--dorado); }
.estrellas button.hov { color: #e3c264; transform: scale(1.12); }
.sel-fila { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.sel-fila select { flex: 1; }
.pm-btn { width: 22px; height: 22px; border-radius: 50%; border: 0; background: #f4f2ec;
  color: #b3ae9e; cursor: pointer; display: inline-flex; align-items: center;
  justify-content: center; padding: 0; flex: none;
  transition: background-color .15s, color .15s; }
.pm-btn svg { width: 10px; height: 10px; display: block; }
.pm-btn.menos:hover { background: #f7e4e0; color: #b5482f; }
.pm-btn.mas:hover { background: #e7f0dd; color: #4d7a3a; }
.pm-btn.oculto { visibility: hidden; }
:root[data-theme="dark"] .pm-btn { background: var(--neutro-bg); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .pm-btn { background: var(--neutro-bg); }
}
/* Detalle de receta (spec Lote 11). */
.titulo-receta { font-size: 22px; font-weight: 700; color: var(--text); text-decoration: none; }
a.titulo-receta:hover { color: var(--verde); }
.chip.favorita { background: #faf1d8; color: #9d7a1b; }
:root[data-theme="dark"] .chip.favorita { background: #3a331b; color: #d9b96a; }
a.valorar-fila { display: flex; justify-content: space-between; align-items: center;
  margin: 12px -18px; padding: 10px 18px; border-top: 1px solid var(--neutro-bg);
  border-bottom: 1px solid var(--neutro-bg); color: var(--verde-osc); font-size: 13px;
  font-weight: 600; text-decoration: none; transition: background-color .15s; }
a.valorar-fila:hover { background: var(--plegar-h); }
a.valorar-fila .flechita { color: #a8a08a; }
.rac-box { display: inline-flex; align-items: center; gap: 10px; background: var(--tinte-dia);
  border-radius: 8px; padding: 6px 12px; font-size: 13px; color: var(--text); }
.rac-btn { width: 17px; height: 17px; border-radius: 50%; border: 0; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; padding: 0; flex: none;
  transition: filter .15s; }
.rac-btn svg { width: 9px; height: 9px; display: block; }
.rac-btn:hover { filter: brightness(.94); }
.rac-menos { background: #f6e7e3; color: #b5482f; }
.rac-mas { background: #e9f0e0; color: #4d7a3a; }
table.ing-tabla td { border-bottom: none; vertical-align: middle; }
table.ing-tabla tr:nth-child(odd) td { background: var(--fila-nutri); }
table.ing-tabla .c, table.ing-tabla th.c { text-align: center; }
a.prod-btn { display: inline-block; color: var(--verde-osc); border-radius: 6px;
  padding: 4px 8px; margin: -4px -8px; text-decoration: none; transition: background-color .15s; }
a.prod-btn:hover { background: var(--hover-fila); }
.celda-vacia { color: #c9c4ae; display: block; text-align: center; }
.sep-full { border: 0; border-top: 1px solid var(--border); margin: 12px -18px; }
a.afin-fila { display: flex; justify-content: space-between; align-items: center;
  margin: 0 -18px; padding: 9px 18px; text-decoration: none; color: var(--verde-osc);
  font-size: 13px; transition: background-color .15s; }
a.afin-fila:hover { background: #faf7f0; }
:root[data-theme="dark"] a.afin-fila:hover { background: var(--hover-fila); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) a.afin-fila:hover { background: var(--hover-fila); }
  :root:not([data-theme="light"]) .chip.favorita { background: #3a331b; color: #d9b96a; }
}
/* Control segmentado (p. ej. tema Claro/Oscuro/Sistema): activo verde, resto apagado. */
.seg { display: inline-flex; gap: 4px; background: var(--neutro-bg); padding: 4px; border-radius: 9px; }
.seg button { border: 0; background: transparent; color: var(--muted); font: inherit; font-size: 13px;
  font-weight: 600; padding: 7px 16px; border-radius: 7px; cursor: pointer;
  transition: background-color .15s, color .15s; }
.seg button:hover { background: var(--sec-bg); color: var(--verde-osc); }
.seg button.on, .seg button.on:hover { background: var(--verde-accion); color: #fff; }
/* Filas-enlace clicables a todo el ancho de la tarjeta (listas: recetas, buscar…). */
.filas-full { margin: 0 -18px; }
a.fila-link { display: grid; grid-template-columns: 1fr 90px; align-items: center; gap: 10px;
  padding: 9px 18px 9px 30px; text-decoration: none; font-size: 13px; color: var(--verde-osc);
  transition: background-color .15s; }
a.fila-link:hover { background: var(--hover-fila); }
a.fila-link .fl-tag { font-size: 11px; color: var(--muted); text-align: center; }
a.fila-link.flex { display: flex; justify-content: space-between; padding-left: 18px; }
a.fila-link .lado { color: var(--muted); font-size: 12px; white-space: nowrap; }
.pie-nota { color: #bdb8a8; font-size: 12px; margin: 0; }
/* Tabla con encabezado gris (historial, catalogo, copias de seguridad). */
.h-head, a.h-row { display: grid; grid-template-columns: 1fr 82px 104px 104px; gap: 8px;
  margin: 0 -18px; padding: 8px 18px; align-items: center; }
.h-head { background: var(--thead-bg); border-bottom: 1px solid var(--thead-borde); }
.h-head > div { font-size: 11px; text-transform: uppercase; letter-spacing: .3px;
  color: var(--thead-texto); font-weight: 700; }
.h-head .c, a.h-row .c { text-align: center; }
a.h-row { font-size: 13px; color: var(--verde-osc); text-decoration: none;
  transition: background-color .15s; }
a.h-row:nth-of-type(even) { background: var(--fila-alt); }
a.h-row:hover, a.h-row:nth-of-type(even):hover { background: var(--hover-fila); }
/* Zona de arrastrar y soltar (importar planes). */
.dz { display: flex; align-items: center; gap: 14px; border: 1.5px dashed #cdd8bd;
  border-radius: 12px; padding: 16px 18px; background: var(--bg); cursor: pointer;
  transition: border-color .15s, background-color .15s; }
.dz:hover, .dz.drag { border-color: var(--verde); background: var(--hover-fila); }
.dz .circ { width: 42px; height: 42px; flex: none; border-radius: 50%;
  background: var(--hover-fila); display: flex; align-items: center; justify-content: center;
  color: var(--verde); font-size: 17px; }
.dz .t1 { font-size: 13px; color: var(--verde-osc); font-weight: 600; }
.dz .t2 { font-size: 12px; color: #a8a08a; }
/* Filas de alternativa numeradas (sustituciones). */
.alt-fila { display: flex; align-items: center; gap: 10px; margin: 0 -18px; padding: 11px 18px;
  font-size: 13px; color: var(--text); cursor: pointer; transition: background-color .15s; }
.alt-fila:hover { background: var(--hover-fila); }
.alt-fila .n { width: 22px; height: 22px; flex: none; border-radius: 50%;
  background: var(--hover-fila); color: var(--verde); font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; }
.alt-fila:hover .n { background: #dbe7cf; }
/* Correcciones: tarjetitas de métricas, tarjetas colapsables y filas de trabajo. */
.stat { display: flex; gap: 18px; flex-wrap: wrap; }
.stat .b { background: #f6f5f0; border-radius: 8px; padding: 8px 12px; font-size: 12px;
  color: #5b5748; }
.stat .b b { display: block; font-size: 15px; color: var(--text); }
.stat .b.rojo b { color: var(--terracota); }
button.card-head { display: flex; width: 100%; align-items: center;
  justify-content: space-between; background: transparent; border: 0; padding: 0 0 11px;
  margin: 0 0 11px; border-bottom: 1px solid var(--border); font: inherit; font-size: 15px;
  font-weight: 700; color: var(--verde-osc); cursor: pointer; }
button.card-head .chev { color: #a8a08a; font-size: 12px; transition: transform .15s; }
button.card-head.abierto .chev { transform: rotate(90deg); }
.frow { display: flex; justify-content: space-between; align-items: center; margin: 0 -18px;
  padding: 9px 18px; border-bottom: 1px solid var(--neutro-bg); font-size: 13px;
  color: var(--text); transition: background-color .15s; }
.frow:last-child { border-bottom: none; }
.frow:hover { background: var(--fila-alt); }
a.ing-btn { display: inline-flex; align-items: center; gap: 6px; background: #f3f6ec;
  color: var(--verde-osc); border-radius: 6px; padding: 6px 11px; font-size: 13px;
  text-decoration: none; transition: background-color .15s; }
a.ing-btn:hover { background: #e2ecd4; }
a.buscar-prod { background: var(--hover-fila); color: var(--verde-osc); border: 0;
  border-radius: 6px; padding: 5px 11px; font-size: 11px; font-weight: 600; cursor: pointer;
  text-decoration: none; white-space: nowrap; transition: background-color .15s; }
a.buscar-prod:hover { background: #dbe7cf; }
button.borrar-suave { background: #f4f2ec; color: var(--muted); border: 0; border-radius: 6px;
  padding: 5px 11px; font-size: 11px; font-weight: 600; cursor: pointer;
  transition: background-color .15s, color .15s; }
button.borrar-suave:hover { background: #f7e4e0; color: var(--terracota); }
/* Modo oscuro de los elementos con color fijo de esta zona. */
:root[data-theme="dark"] .stat .b, :root[data-theme="dark"] button.borrar-suave {
  background: var(--neutro-bg); color: var(--muted); }
:root[data-theme="dark"] a.ing-btn { background: var(--chip-bg); color: var(--chip-text); }
:root[data-theme="dark"] a.ing-btn:hover, :root[data-theme="dark"] a.buscar-prod:hover,
:root[data-theme="dark"] .alt-fila:hover .n { background: var(--sec-bg); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .stat .b,
  :root:not([data-theme="light"]) button.borrar-suave {
    background: var(--neutro-bg); color: var(--muted); }
  :root:not([data-theme="light"]) a.ing-btn {
    background: var(--chip-bg); color: var(--chip-text); }
  :root:not([data-theme="light"]) a.ing-btn:hover,
  :root:not([data-theme="light"]) a.buscar-prod:hover,
  :root:not([data-theme="light"]) .alt-fila:hover .n { background: var(--sec-bg); }
}
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
        "<b>Lista de la compra.</b> Todos los productos del plan, agrupados por pasillo de "
        "Alcampo (los perecederos al final, para comprarlos lo último). Cada producto enlaza "
        "a su página en compraonline.alcampo.es; las unidades se calculan según el formato "
        "del paquete y «Sobra» es lo que te quedará sin usar. La flecha junto al precio "
        "avisa de subidas (↑ rojo) u ofertas (↓ verde). Marca la casilla para ir tachando "
        "mientras compras (se recuerda en este equipo). «Enviar a Alcampo» abre Alcampo en "
        "tu navegador, inicias sesión TÚ (la app nunca guarda tu contraseña) y añade los "
        "productos a la cesta; al terminar te deja en la cesta para elegir franja y pagar. "
        "Salta los agotados."
    ),
    "recetas": (
        "<b>Recetas.</b> Todas las recetas disponibles: las tuyas (editables) y las del "
        "catálogo (solo lectura). Crea una con «Nueva receta», importa por URL, o busca "
        "sustitutos de cocina con «Sustituciones»."
    ),
    "catalogo": (
        "<b>Catálogo.</b> Los productos de Alcampo en la base de datos. «Actualizar» "
        "refresca precios y productos de las categorías marcadas (tarda unos minutos y usa "
        "la web de Alcampo); «Revisar» lista datos anómalos detectados. Corrige un producto "
        "con «Editar», empareja ingredientes sin producto («Correcciones») o busca en todo "
        "(«Buscar»)."
    ),
    "sustituciones": (
        "<b>Sustituciones.</b> Sustituciones de cocina habituales para cuando te falta un "
        "ingrediente (p. ej. mantequilla → aceite). No son productos del catálogo: para "
        "emparejar ingredientes con productos de Alcampo ya está «Correcciones»."
    ),
    "historial": (
        "<b>Historial.</b> Todos los planes de menú generados. Pulsa uno para ver sus "
        "semanas: los planes antiguos son de solo lectura, pero «Repetir esta semana» "
        "añade esa semana al final del plan actual. Puedes exportar un plan a .json para "
        "compartirlo e importar el de otra persona arrastrándolo a la zona de "
        "«Compartir menús»."
    ),
    "buscar": (
        "<b>Buscar.</b> Búsqueda global: recetas por título y productos del catálogo por "
        "nombre. Pulsa una receta para abrir su ficha, o un producto para ver y corregir "
        "sus datos."
    ),
    "editor": (
        "<b>Editor de receta.</b> Escribe para buscar cada ingrediente en el catálogo de "
        "Alcampo; la cantidad va en números y la unidad al lado. Usa − y + para quitar o "
        "añadir líneas, y ajusta las raciones con el selector. Las casillas marcan para qué "
        "sirve la receta (batchcooking, desayuno, cena, favorita). Tras guardar, la app "
        "empareja los ingredientes con productos al regenerar (o con menu-app-emparejar)."
    ),
    "valoraciones": (
        "<b>Valoraciones.</b> En «Valorar» aparecen las recetas cocinadas esta semana o la "
        "anterior que aún no has valorado; pulsa una para puntuarla. En «Valoraciones» "
        "puedes buscar y re-valorar las ya puntuadas. Tus valoraciones alimentan la "
        "palatabilidad del optimizador: lo que te gusta vuelve más a menudo al menú."
    ),
    "matching": (
        "<b>Correcciones.</b> Ingredientes de receta sin producto de Alcampo asignado: "
        "mientras falten, esas recetas no pueden entrar en el menú. Pulsa el ingrediente "
        "para abrir (en otra ventana) una receta que lo usa, o «Buscar producto…» para "
        "asignarle un producto a mano. En «Sinónimos» enseñas al emparejador que una "
        "palabra equivale a otra (p. ej. ajoporro → puerro); se aplican al volver a "
        "emparejar."
    ),
}


def _pagina(
    titulo: str, cuerpo: str, refrescar: int | None = None, activa: str = "", ayuda: str = ""
) -> str:
    """Envuelve el cuerpo en la plantilla base (barra de herramientas + tema).

    `activa` marca la sección de la barra (menu/compra/recetas/catalogo) para
    pintar la barrita mostaza bajo el botón activo. `ayuda` elige el texto del
    modo ayuda ❓ cuando la pantalla no coincide con su sección de barra (p. ej.
    Sustituciones vive bajo Recetas pero tiene su propia ayuda).
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
    texto_ayuda = AYUDA_SECCION.get(ayuda or activa, "")
    panel_ayuda = f'<div class="ayuda">{texto_ayuda}</div>' if texto_ayuda else ""
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
    """Formulario de crear/editar receta (spec Lote 11): título + raciones −/+,
    filas de ingredientes con buscador y botones ± sutiles, preparación de borde
    a borde autoexpandible, casillas y botones Guardar/Eliminar del mismo tamaño."""
    es_edicion = datos is not None
    titulo = html.escape(datos["titulo"]) if es_edicion else ""
    raciones = datos["raciones"] if es_edicion else 4
    rid = html.escape(datos["id"]) if es_edicion else ""
    prep = html.escape(datos.get("instrucciones", "")) if es_edicion else ""
    ings = datos["ingredientes"] if es_edicion else [{"nombre": "", "cantidad": "", "unidad": "g"}]

    datalist = "".join(f"<option>{html.escape(n)}</option>" for n in catalogo)
    svg_menos = (
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" '
        'stroke-linecap="round"><line x1="4" y1="8" x2="12" y2="8"/></svg>'
    )
    svg_mas = (
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.4" '
        'stroke-linecap="round"><line x1="8" y1="4" x2="8" y2="12"/>'
        '<line x1="4" y1="8" x2="12" y2="8"/></svg>'
    )

    def _fila(ing):
        nombre = html.escape(str(ing.get("nombre", "")))
        cant = html.escape(str(ing.get("cantidad", "") or ""))
        uni = ing.get("unidad", "g")
        ops = "".join(
            f'<option value="{u}"{" selected" if u == uni else ""}>{u}</option>' for u in UNIDADES
        )
        return (
            '<div class="ing-fila">'
            f'<input name="ing_nombre" list="catalogo_ing" value="{nombre}" '
            'placeholder="Buscar ingrediente en Alcampo…">'
            f'<input name="ing_cantidad" class="ing-cant" value="{cant}" inputmode="decimal" '
            'pattern="[0-9]*[.,]?[0-9]*" placeholder="cant." '
            "oninput=\"this.value=this.value.replace(/[^0-9.,]/g,'')\">"
            f'<select name="ing_unidad" class="ing-uni">{ops}</select>'
            '<button type="button" class="pm-btn menos" aria-label="Quitar ingrediente" '
            f'onclick="quitarIng(this)">{svg_menos}</button>'
            '<button type="button" class="pm-btn mas" aria-label="Añadir ingrediente" '
            f'onclick="addFila()">{svg_mas}</button>'
            "</div>"
        )

    filas = "".join(_fila(i) for i in ings)

    def chk(k: str) -> str:
        return " checked" if es_edicion and datos.get(k) else ""

    eliminar = (
        f'<button class="btn rojo w130" formaction="/recetas/{rid}/eliminar" '
        'formmethod="post" formnovalidate>Eliminar</button>' if es_edicion else ""
    )
    return f"""
<div class="card"><div class="franja">{"Editar" if es_edicion else "Nueva"} receta</div>
<form method="post" action="/recetas/guardar">
<input type="hidden" name="receta_id" value="{rid}">
<input type="hidden" name="raciones" id="rac-input" value="{raciones}">
<datalist id="catalogo_ing">{datalist}</datalist>
<div style="display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap">
  <div style="flex:1;min-width:220px"><label>Título</label>
    <input name="titulo" required value="{titulo}" placeholder="Lentejas de la abuela"></div>
  <span class="rac-box" style="height:38px">Raciones
    <button class="rac-btn rac-menos" type="button" aria-label="Menos raciones"
      onclick="racDelta(-1)">{svg_menos}</button>
    <b id="rac-num">{raciones}</b>
    <button class="rac-btn rac-mas" type="button" aria-label="Más raciones"
      onclick="racDelta(1)">{svg_mas}</button></span>
</div>
<label>Ingredientes</label>
<div id="ings">{filas}</div>
<label>Preparación</label>
<textarea name="instrucciones" class="prep" rows="2" oninput="autoAlto(this)"
placeholder="Escribir aquí el método de preparación de esta receta si es necesario">{prep}</textarea>
<div style="margin-top:12px;display:flex;gap:18px;flex-wrap:wrap">
  <label style="display:inline-flex;align-items:center;gap:7px;margin:0;font-weight:400;font-size:13px;color:var(--text)">
    <input type="checkbox" name="plato_unico" value="1"{chk('es_plato_unico')}> Batchcooking</label>
  <label style="display:inline-flex;align-items:center;gap:7px;margin:0;font-weight:400;font-size:13px;color:var(--text)">
    <input type="checkbox" name="desayuno" value="1"{chk('es_desayuno')}> Desayuno</label>
  <label style="display:inline-flex;align-items:center;gap:7px;margin:0;font-weight:400;font-size:13px;color:var(--text)">
    <input type="checkbox" name="cena" value="1"{chk('es_cena')}> Cena</label>
  <label style="display:inline-flex;align-items:center;gap:7px;margin:0;font-weight:400;font-size:13px;color:var(--text)">
    <input type="checkbox" name="favorita" value="1"{chk('es_favorita')}> Favorita</label>
</div>
<div style="margin-top:14px;display:flex;gap:10px">
  <button class="btn w130" type="submit">Guardar</button>
  {eliminar}
</div>
</form>
</div>
<script>
function racDelta(d) {{
  var inp = document.getElementById('rac-input');
  var v = Math.max(1, (parseInt(inp.value) || 1) + d);
  inp.value = v;
  document.getElementById('rac-num').textContent = v;
}}
function refrescarMasIng() {{
  var filas = document.querySelectorAll('#ings .ing-fila');
  filas.forEach(function(f, i) {{
    f.querySelector('.mas').classList.toggle('oculto', i !== filas.length - 1);
  }});
}}
function quitarIng(btn) {{
  var filas = document.querySelectorAll('#ings .ing-fila');
  if (filas.length > 1) {{ btn.closest('.ing-fila').remove(); }}
  else {{ btn.closest('.ing-fila').querySelectorAll('input').forEach(function(i){{ i.value=''; }}); }}
  refrescarMasIng();
}}
function addFila() {{
  var cont = document.getElementById('ings');
  var f = cont.firstElementChild.cloneNode(true);
  f.querySelectorAll('input').forEach(function(i){{ i.value=''; }});
  cont.appendChild(f);
  refrescarMasIng();
}}
function autoAlto(t) {{ t.style.height = 'auto'; t.style.height = (t.scrollHeight + 2) + 'px'; }}
refrescarMasIng();
document.querySelectorAll('textarea.prep').forEach(autoAlto);
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
