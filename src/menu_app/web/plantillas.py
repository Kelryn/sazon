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
/* Enlace "saltar al contenido" (#70), oculto salvo con foco de teclado. */
.skip-link { position: absolute; left: -9999px; top: 0; background: var(--verde);
  color: #fff; padding: 8px 14px; border-radius: 0 0 8px 0; z-index: 100; }
.skip-link:focus { left: 0; }
/* Vista de impresion (#68): sin cabecera/nav/botones, fondo blanco, sin sombras. */
@media print {
  header nav, form, .btn, .arrows a[href], .off { display: none !important; }
  body { background: #fff !important; }
  .card { box-shadow: none !important; border: 1px solid #ccc !important; break-inside: avoid; }
  a[href]:after { content: "" !important; }
}
"""
)


def _pagina(titulo: str, cuerpo: str, refrescar: int | None = None) -> str:
    meta = f'<meta http-equiv="refresh" content="{refrescar}">' if refrescar else ""
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{meta}
<link rel="icon" href="{favicon_data_uri()}">
<title>{html.escape(titulo)} · {NOMBRE}</title><style>{_ESTILO}</style>{TEMA_SCRIPT}</head><body>
<a href="#contenido" class="skip-link">Saltar al contenido</a>
<header><a href="/" title="{NOMBRE} — {ESLOGAN}">{LOGO_SVG.replace('<svg', '<svg class="logo"', 1)}</a>
<nav><a href="/">Menú</a><a href="/compra">Lista de la compra</a>
<a href="/recetas">Recetas</a><a href="/catalogo">Catálogo</a>
<a href="/buscar">Buscar</a><a href="/matching">Correcciones</a>
<a href="/dashboard">Dashboard</a><a href="/config">Configuración</a>
<button class="btn mini sec" type="button" onclick="alternarTema()" title="Cambiar tema claro/oscuro" aria-label="Cambiar entre tema claro y oscuro" style="margin-left:6px">🌓</button>
</nav></header>
<main id="contenido">{cuerpo}</main></body></html>"""


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

    def _t(rid):
        if not rid:
            return "—"
        n_usos = (sel_com.get(rid, 0) or 0) + (sel_cen.get(rid, 0) or 0)
        x = raciones.get(rid)
        por_comida = (x / n_usos) if (x and n_usos) else None
        enlace = _link_receta(rid, info.get(rid, {}), por_comida)
        return enlace + _alerta_comida(info.get(rid, {}), por_comida or 1.0)

    filas = ""
    for dia, comida, cena, es_bc in asignar_dias(datos, DIAS_SEMANA):
        etiqueta = ' <span class="meta">🍱 plato único</span>' if es_bc else ""
        filas += (
            f"<tr><td><b>{_NOMBRE_DIA.get(dia, dia)}</b>{etiqueta}</td>"
            f"<td>{_t(comida)}</td><td>{_t(cena)}</td></tr>"
        )
    tabla = f"<table><tr><th>Día</th><th>🌞 Comida</th><th>🌙 Cena</th></tr>{filas}</table>"
    return tabla + _resumen_grupos(datos)


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
