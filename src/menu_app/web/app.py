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
import json
import threading
from datetime import UTC
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..actualizaciones import hay_actualizacion, instalar
from ..almacenamiento.alertas_precio import subidas_de_precio
from ..almacenamiento.db import get_connection, init_db
from ..almacenamiento.validacion_datos import validar_datos
from ..backups import crear_backup, listar_backups, restaurar_backup
from ..carrito import chromium_instalado, playwright_disponible
from ..configuracion import DIAS_SEMANA, cargar_config, guardar_overlay, ruta_overlay
from ..ingesta.categories import FOOD_CATEGORY_ROOTS
from ..matching.descatalogados import productos_descatalogados, rematch_descatalogados
from ..matching.repositorio import MatchingRepository
from ..optimizacion.compra import es_pasillo_perecedero, lista_compra
from ..optimizacion.desayunos import sugerir_desayunos
from ..optimizacion.economia_recetas import _FACTOR_PRECIO, _gramos_por_piezas
from ..optimizacion.economia_recetas import invalidar_cache as invalidar_cache_recetas
from ..optimizacion.exportar import (
    compra_a_csv,
    compra_a_pdf,
    menu_a_csv,
    menu_a_pdf,
)
from ..optimizacion.planes import (
    cargar_plan,
    exportar_plan_json,
    generar_plan,
    importar_plan_json,
    listar_planes,
    regenerar_semana,
    repetir_semana,
)
from ..recetas.catalogo_ingredientes import ingredientes_catalogo
from ..recetas.manual import (
    cargar_receta,
    eliminar_receta,
    guardar_receta,
    listar_recetas,
    marcar_favorita,
)
from ..recetas.sustituciones import buscar_sustitutos
from ..recetas.tags import generar_tags
from ..recetas.utensilios import detectar_utensilios
from ..recetas.valoraciones import (
    BAREMOS,
    detalle_de,
    guardar_valoracion,
    listar_recetas_valoradas,
    recetas_afines,
    recetas_para_valorar,
    valoraciones_de,
)
from ..telemetria import leer_ultimos_errores, limpiar_log, registrar_error
from ..version import __version__
from .marca import NOMBRE
from .plantillas import (
    _NOMBRE_DIA,
    _banner_hoy,
    _barras_nutrientes,
    _editor_html,
    _fila_nutrientes,
    _link_receta,
    _pagina,
    _pct,
    _tabla_dias,
)
from .tareas import (
    _ACTUALIZACION,
    _CARRITO,
    _CATALOGO,
    _CATALOGO_ANTIGUEDAD,
    _CHROMIUM,
    _banner_actualizacion,
    _comprobar_actualizacion,
    _lanzar_actualizacion,
    _lanzar_carrito,
    _lanzar_instalar_chromium,
    comprobar_catalogo_desactualizado,
)


def crear_app(config_path: str | Path = "config.yaml") -> FastAPI:
    config_path = Path(config_path)
    app = FastAPI(title=NOMBRE)

    # Diagnostico de errores LOCAL, opt-in (#81): NO se envia nada por red (no hay
    # servidor propio); solo se anota en un log local si el usuario lo activa.
    @app.exception_handler(Exception)
    async def _capturar_error(request: Request, exc: Exception):
        activo = bool(cargar_config(config_path).get("telemetria_local", False))
        registrar_error(request.url.path, exc, activo)
        raise exc  # deja que FastAPI/uvicorn lo trate igual que sin este handler

    def _conn():
        cfg = cargar_config(config_path)
        ruta = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        conn = get_connection(ruta)
        init_db(conn)
        return conn, cfg

    # Comprobacion de actualizaciones al arrancar (en segundo plano, no bloquea).
    _cfg_inicial = cargar_config(config_path)
    _cfg_upd = _cfg_inicial.get("actualizaciones", {}) or {}
    if _cfg_upd.get("comprobar_al_arrancar", True):
        threading.Thread(
            target=_comprobar_actualizacion,
            args=(str(_cfg_upd.get("canal", "estable")),),
            daemon=True,
        ).start()

    # Copia de seguridad automatica al arrancar (#80): BD + config.usuario.yaml.
    if _cfg_inicial.get("backups_automaticos", True):
        _db_inicial = Path((_cfg_inicial.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        threading.Thread(
            target=lambda: crear_backup(_db_inicial, ruta_overlay(config_path)),
            daemon=True,
        ).start()

    # Catálogo programado (#116): comprueba su antigüedad al arrancar y, si el
    # usuario activó el auto-refresco, lo lanza solo cuando lleva demasiado sin tocarse.
    threading.Thread(
        target=comprobar_catalogo_desactualizado, args=(_cfg_inicial,), daemon=True,
    ).start()

    # ---------------------------------- menu ----------------------------------

    @app.get("/", response_class=HTMLResponse)
    def home(semana: int = 1, msg: str = ""):
        conn, cfg = _conn()
        try:
            plan_id, semanas = cargar_plan(conn)
            n_productos = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
            n_recetas = conn.execute("SELECT COUNT(*) FROM recetas").fetchone()[0]
        finally:
            conn.close()
        aviso = _banner_actualizacion()
        aviso += f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        # Catálogo programado (#116): avisa si lleva demasiado sin actualizarse.
        _dias_cat = _CATALOGO_ANTIGUEDAD["dias"]
        _umbral_cat = int(cfg.get("catalogo_dias_alerta", 7) or 7)
        if n_productos and _dias_cat is not None and _dias_cat >= _umbral_cat and not _CATALOGO["activa"]:
            aviso += (
                f'<div class="card"><p class="warn">📅 El catálogo lleva <b>{_dias_cat} días</b> '
                'sin actualizarse. <a href="/catalogo">Actualízalo</a> para tener precios y '
                "ofertas al día.</p></div>"
            )
        # Onboarding (#69): checklist de primeros pasos si aun no hay nada configurado.
        if n_productos == 0 or n_recetas == 0 or not semanas:
            pasos = [
                (n_productos > 0, "Actualizar el catálogo de Alcampo",
                 "/catalogo", "descarga los productos y precios"),
                (n_recetas > 0, "Tener recetas en el corpus",
                 "/recetas", "importa o añade recetas"),
                (bool(semanas), "Generar tu primer menú",
                 None, "usa el botón de abajo"),
            ]
            filas_pasos = "".join(
                f'<li style="margin-bottom:6px">{"✅" if hecho else "⬜"} '
                + (f'<a href="{url}">{titulo}</a>' if url and not hecho else titulo)
                + f' <span class="meta">— {nota}</span></li>'
                for hecho, titulo, url, nota in pasos
            )
            aviso += (
                '<div class="card"><div class="franja">👋 Primeros pasos</div>'
                f"<ol style='padding-left:20px'>{filas_pasos}</ol></div>"
            )

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
                activa="menu",
            )

        n_sem = max(semanas)
        semana = max(1, min(int(semana), n_sem))
        datos = semanas[semana]

        ant = (
            f'<a href="/?semana={semana - 1}" aria-label="Semana anterior">◀</a>'
            if semana > 1 else '<span class="off" aria-hidden="true">◀</span>'
        )
        sig = (
            f'<a href="/?semana={semana + 1}" aria-label="Semana siguiente">▶</a>'
            if semana < n_sem else '<span class="off" aria-hidden="true">▶</span>'
        )
        flechas = f'<span class="arrows">{ant} Semana {semana}/{n_sem} {sig}</span>'

        if not datos.get("factible"):
            cuerpo = aviso + form_generar + (
                f'<div class="card"><div class="franja">Plan por día {flechas}</div>'
                f'<p class="warn">Sin menú factible esta semana: '
                f'{html.escape(datos.get("motivo", ""))}. Amplía el corpus de recetas o relaja '
                f"la regla de repetición.</p></div>"
            )
            return _pagina("Menú semanal", cuerpo, activa="menu")

        botones_semana = (
            '<a class="btn neu mini" href="/historial" style="margin-right:6px" '
            'title="Ver planes anteriores">Historial</a>'
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

        # Sugerencia de desayunos/meriendas (#50): opcional, orientativa (no forma
        # parte del coste/nutricion optimizado de comida+cena).
        desayunos_card = ""
        if cfg.get("incluir_desayunos"):
            conn2, _ = _conn()
            try:
                sugeridos = sugerir_desayunos(conn2, dias=int(datos.get("dias", 7)))
            finally:
                conn2.close()
            if sugeridos:
                filas_des = "".join(
                    f'<tr><td>{html.escape(s.titulo)}</td>'
                    f'<td style="text-align:right">{s.coste_racion:.2f} €/ración</td></tr>'
                    for s in sugeridos
                )
                desayunos_card = (
                    '<div class="card"><div class="franja">🥣 Desayunos/meriendas (sugerencia)</div>'
                    f"<table>{filas_des}</table>"
                    '<p class="meta">Orientativo: no está optimizado junto con comida y cena '
                    "(actívalo/desactívalo en Configuración).</p></div>"
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

        cuerpo = (
            aviso + _banner_hoy(datos) + form_generar + plan_card + desayunos_card
            + _fila_nutrientes(datos, cfg) + cambio_card
        )
        return _pagina("Menú semanal", cuerpo, activa="menu")

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
    def receta_detalle(receta_id: str, msg: str = ""):
        conn, _cfg = _conn()
        try:
            cab = conn.execute(
                "SELECT titulo, raciones, fuente, url, es_favorita, imagen, instrucciones, "
                "tiempo_total_min, es_batchcooking, es_plato_unico FROM recetas WHERE id = ?",
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
                cant_html = (
                    f'<span class="cant-val" data-base="{gramos}">{gramos:.0f}</span> {um}{estimado}'
                    if gramos is not None else "—"
                )

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
                            precio_html = f'<span class="coste-val" data-base="{coste_ing}">{coste_ing:.2f}</span> €'
                filas += (
                    f"<tr><td>{html.escape(ing['texto_original'][:70])}</td><td>{cant_html}</td>"
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
            tiempo = (
                f' · ⏱ {cab["tiempo_total_min"]} min' if cab["tiempo_total_min"] else ""
            )
            # Etiquetas deterministas (#46).
            ings_norm = {i["nombre_normalizado"] for i in ingredientes if i["nombre_normalizado"]}
            tags = generar_tags(
                tiempo_total_min=cab["tiempo_total_min"], ingredientes_norm=ings_norm,
                es_batchcooking=bool(cab["es_batchcooking"]), es_plato_unico=bool(cab["es_plato_unico"]),
            )
            utensilios = sorted(detectar_utensilios(cab["titulo"], cab["instrucciones"]))  # #47
            chips_tags = "".join(
                f'<span class="chip">{html.escape(t)}</span>' for t in tags + utensilios
            )
            # Imagen (#40) y pasos de elaboración (#39), cuando la fuente los trae.
            media = ""
            if cab["imagen"]:
                media += (
                    f'<img src="{html.escape(cab["imagen"])}" alt="{html.escape(cab["titulo"])}" '
                    'style="max-width:100%;border-radius:10px;margin-bottom:12px">'
                )
            if cab["instrucciones"]:
                pasos = [p.strip() for p in cab["instrucciones"].split("\n") if p.strip()]
                lis = "".join(f"<li>{html.escape(p)}</li>" for p in pasos)
                media += (
                    '<div class="franja">Elaboración</div>'
                    f'<ol style="padding-left:20px;line-height:1.6">{lis}</ol>'
                )
            elaboracion = f'<div class="card">{media}</div>' if media else ""
            # Recomendador por afinidad (#99/Lote 12): recetas parecidas por ingredientes,
            # con las bien valoradas personalmente por delante.
            afines = recetas_afines(conn, receta_id)
            afines_html = ""
            if afines:
                filas_afines = "".join(
                    f'<li><a class="receta" href="/receta/{html.escape(a["receta_id"])}">'
                    f'{html.escape(a["titulo"])}</a> '
                    f'<span class="meta">({a["similitud"] * 100:.0f}% ingredientes en común)</span></li>'
                    for a in afines
                )
                afines_html = (
                    '<div class="card"><div class="franja">Recetas afines</div>'
                    f"<ul style='padding-left:20px'>{filas_afines}</ul></div>"
                )
            # Escalado dinamico de raciones (#41): recalcula cantidades y coste sin
            # recargar la pagina (JS multiplica por el factor deseadas/base).
            aviso = f'<div class="card"><p class="ok">{html.escape(msg)}</p></div>' if msg else ""
            cuerpo = (
                aviso
                + f'<div class="card"><div class="big">{html.escape(cab["titulo"])}{fav}</div>'
                f'<p class="meta">fuente: {fuente}{tiempo}</p>'
                + (f'<p>{chips_tags}</p>' if chips_tags else "")
                + f'<p><a class="receta" href="/valoraciones/{html.escape(receta_id)}">'
                "⭐ Valorar esta receta</a></p>"
                + '<p><label>Raciones: <input type="number" id="raciones-input" '
                f'value="{raciones}" min="1" step="1" style="width:70px" '
                'oninput="reescalarReceta()"></label></p>'
                f'<table><tr><th>Ingrediente</th><th>Cantidad</th>'
                f"<th>Producto Alcampo</th><th>Coste usado</th></tr>{filas}</table>"
                f'<p class="franja">Coste de la receta (<span id="raciones-mostradas">{raciones}</span> '
                f'raciones): <span id="coste-total">{total:.2f}</span> € '
                f'<span class="meta">(<span id="coste-racion">{total / raciones:.2f}</span> €/ración)</span></p>'
                f'<p class="meta">El "coste usado" es la parte proporcional del producto que '
                f"consume la receta (no el precio del paquete entero).</p></div>"
                + elaboracion
                + afines_html
                + f"""<script>
function reescalarReceta() {{
  const base = {raciones};
  const deseadas = Math.max(1, parseFloat(document.getElementById('raciones-input').value) || base);
  const factor = deseadas / base;
  let totalCoste = 0;
  document.querySelectorAll('.cant-val').forEach(el => {{
    const b = parseFloat(el.dataset.base);
    el.textContent = (b * factor).toFixed(0);
  }});
  document.querySelectorAll('.coste-val').forEach(el => {{
    const b = parseFloat(el.dataset.base);
    const v = b * factor;
    totalCoste += v;
    el.textContent = v.toFixed(2);
  }});
  document.getElementById('coste-total').textContent = totalCoste.toFixed(2);
  document.getElementById('coste-racion').textContent = (totalCoste / deseadas).toFixed(2);
  document.getElementById('raciones-mostradas').textContent = deseadas;
}}
</script>"""
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
            subidas = subidas_de_precio(conn, rids=[linea.producto_id for linea in compra.lineas])
        finally:
            conn.close()
        if compra.semanas == 0:
            return _pagina(
                "Lista de la compra",
                '<div class="card">No hay plan generado: genera primero el menú.</div>',
            )
        filas = ""
        for pasillo, lineas in compra.por_pasillo().items():
            subtotal = sum(linea.total for linea in lineas if linea.total is not None)
            perecedero = (
                ' <span class="chip" title="Cómpralo lo último para minimizar desperdicio (#105)">'
                "🧊 perecedero</span>"
                if es_pasillo_perecedero(pasillo) else ""
            )
            filas += (
                f'<tr><td colspan="5" style="padding-top:10px"><b>🛒 {html.escape(pasillo)}</b>'
                f'{perecedero} <span class="meta">({subtotal:.2f} €)</span></td></tr>'
            )
            for linea in lineas:
                enlace = (
                    f'<a class="receta" href="{html.escape(linea.url)}" target="_blank">'
                    f"{html.escape(linea.nombre[:46])}</a>"
                    if linea.url else html.escape(linea.nombre[:46])
                )
                # Marcas de sustitucion por agotado (#53) y oferta (#57).
                notas = ""
                if linea.sustituido:
                    notas += (
                        '<br><span class="meta" title="Agotado: '
                        f'{html.escape(linea.nombre_original or "")}">'
                        "🔄 sustituido (agotado)</span>"
                    )
                if linea.en_oferta:
                    notas += f'<br><span class="chip">🏷️ oferta · ahorras {linea.ahorro:.2f} €</span>'
                precio = f"{linea.precio_unidad:.2f}" if linea.precio_unidad is not None else "—"
                tot = f"{linea.total:.2f}" if linea.total is not None else "—"
                # Lista MARCABLE (#66): checkbox persistida en localStorage (por plan +
                # producto), para ir tachando mientras compras sin recargar la pagina.
                item_id = html.escape(f"{compra.plan_id or ''}:{linea.producto_id}")
                filas += (
                    f'<tr class="fila-compra" data-item="{item_id}">'
                    f'<td><input type="checkbox" class="chk-comprado" '
                    f'onchange="marcarComprado(this)" style="width:auto"></td>'
                    f"<td>{linea.unidades}×</td><td>{enlace}"
                    f'<br><span class="meta">necesitas {linea.cantidad_legible}</span>{notas}</td>'
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
        if compra.agotados_sin_sustituto:
            lista_ag = ", ".join(html.escape(s) for s in compra.agotados_sin_sustituto[:20])
            sin += (
                f'<p class="warn">⊘ Agotados sin alternativa en su categoría (cómpralos a tu '
                f"criterio o cambia de producto): {lista_ag}</p>"
            )
        if subidas:
            lista_subidas = ", ".join(
                f'{html.escape(a["nombre"])} ({a["precio_anterior"]:.2f}→{a["precio_actual"]:.2f} €, '
                f'+{a["subida_pct"]:.0f}%)'
                for a in subidas[:10]
            )
            sin += (
                f'<p class="warn">📈 Subidas de precio recientes (#118): {lista_subidas}</p>'
            )
        ahorro_html = (
            f' <span class="chip">🏷️ ahorras {compra.ahorro_total:.2f} € en ofertas</span>'
            if compra.ahorro_total > 0 else ""
        )
        ticket = (
            f'<div class="ticket"><h2>ALCAMPO</h2>'
            f'<p class="cab">Lista de la compra · {compra.semanas} semana'
            f"{'s' if compra.semanas != 1 else ''} de menús<br>"
            f'<span class="meta">{html.escape(compra.plan_id or "")}</span></p>'
            f"<table><tr><th></th><th>Uds</th><th>Producto</th>"
            f'<th style="text-align:right">€/ud</th><th style="text-align:right">Total</th></tr>'
            f"{filas}</table>"
            f'<div class="total">TOTAL: {compra.total:.2f} €{ahorro_html}</div></div>'
            + """<style>
.fila-compra.comprado > td:not(:first-child) { opacity: .45; text-decoration: line-through; }
</style>
<script>
(function(){
  var clave = 'sazon-compra-marcada';
  var estado = JSON.parse(localStorage.getItem(clave) || '{}');
  document.querySelectorAll('.fila-compra').forEach(function(tr){
    var id = tr.dataset.item;
    var chk = tr.querySelector('.chk-comprado');
    if (estado[id]) { chk.checked = true; tr.classList.add('comprado'); }
  });
  window.marcarComprado = function(chk){
    var tr = chk.closest('.fila-compra');
    var id = tr.dataset.item;
    var estado = JSON.parse(localStorage.getItem(clave) || '{}');
    if (chk.checked) { estado[id] = true; tr.classList.add('comprado'); }
    else { delete estado[id]; tr.classList.remove('comprado'); }
    localStorage.setItem(clave, JSON.stringify(estado));
  };
})();
</script>"""
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
                '<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px">'
                '<input type="checkbox" name="sincronizar" value="1" style="width:auto"> '
                "Ajustar a la cantidad exacta si ya está en la cesta</label>"
                '<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px">'
                '<input type="checkbox" name="vaciar_antes" value="1" style="width:auto"> '
                "Vaciar la cesta antes de empezar</label><br>"
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
        # Chromium bajo demanda (#78): solo se ofrece si Playwright esta pero el
        # navegador de respaldo NO (el flujo normal usa tu Chrome/Edge; esto es solo
        # una red de seguridad si Playwright no los encuentra).
        chromium_card = ""
        if playwright_disponible() and not chromium_instalado():
            if _CHROMIUM["instalando"]:
                cuerpo_chr = '<p class="ok">⏳ Instalando Chromium…</p>'
            else:
                cuerpo_chr = (
                    '<form method="post" action="/carrito/instalar-navegador">'
                    '<button class="btn sec" type="submit">Instalar navegador de respaldo (Chromium)</button>'
                    "</form>"
                )
            if _CHROMIUM["resumen"]:
                cuerpo_chr += f'<p class="ok">{html.escape(_CHROMIUM["resumen"])}</p>'
            log_chr = "\n".join(list(_CHROMIUM["log"])[-20:])
            if log_chr:
                cuerpo_chr += f'<pre class="log">{html.escape(log_chr)}</pre>'
            chromium_card = (
                '<div class="card"><div class="franja">🧩 Navegador de respaldo</div>'
                + cuerpo_chr
                + '<p class="note">El carrito usa tu Chrome o Edge. Si no los encuentra, '
                "puedes instalar aquí un Chromium propio (~150 MB) como respaldo — solo se "
                "descarga si lo pides.</p></div>"
            )

        aviso = f'<div class="card"><p class="ok">{html.escape(msg)}</p></div>' if msg else ""
        cuerpo = (
            aviso
            + chromium_card
            + descargas
            + carrito_card
            + f'<div class="card">{ticket}{sin}'
            f'<p class="meta">Agrupada por pasillo. Cada producto enlaza a su página en '
            f"compraonline.alcampo.es para añadirlo al carrito. Las unidades se calculan según "
            f"el formato del paquete.</p></div>"
        )
        return _pagina("Lista de la compra", cuerpo, refrescar=5 if activa else None,
                       activa="compra")

    # --- Historial de planes y "repetir semana pasada" (#109) ---
    @app.get("/historial", response_class=HTMLResponse)
    def historial_page(msg: str = ""):
        conn, _ = _conn()
        try:
            planes = listar_planes(conn)
        finally:
            conn.close()
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        if not planes:
            return _pagina("Historial de menús", aviso + '<div class="card">Todavía no hay planes generados.</div>')
        filas = "".join(
            f'<tr><td>{html.escape(p["creado"])}</td>'
            f'<td>{p["n_semanas"]}</td><td>{p["coste_total"]:.2f} €</td>'
            f'<td><a class="receta" href="/historial/{html.escape(p["plan_id"])}">Ver semanas</a></td></tr>'
            for p in planes
        )
        importar = (
            '<div class="card"><div class="franja">Compartir menús (#114)</div>'
            '<form method="post" action="/historial/importar" enctype="multipart/form-data">'
            '<label>Importar un plan (.json exportado desde "Ver semanas")</label>'
            '<input type="file" name="fichero" accept="application/json" required>'
            '<div style="margin-top:10px"><button class="btn" type="submit">Importar</button></div>'
            "</form></div>"
        )
        cuerpo = aviso + (
            '<div class="card"><div class="franja">Planes generados</div>'
            "<table><tr><th>Fecha</th><th>Semanas</th><th>Coste total</th><th></th></tr>"
            f"{filas}</table></div>"
        ) + importar
        return _pagina("Historial de menús", cuerpo)

    @app.get("/historial/{plan_id}", response_class=HTMLResponse)
    def historial_plan_page(plan_id: str, msg: str = ""):
        conn, _ = _conn()
        try:
            _pid, semanas = cargar_plan(conn, plan_id)
            plan_actual_id, _ = cargar_plan(conn)
        finally:
            conn.close()
        if not semanas:
            return _pagina("Historial de menús", '<div class="card">Ese plan no existe.</div>')
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        es_actual = plan_id == plan_actual_id
        filas = ""
        for semana, datos in sorted(semanas.items()):
            repetir = "" if es_actual else (
                f'<form method="post" action="/repetir-semana" style="display:inline">'
                f'<input type="hidden" name="origen_plan_id" value="{html.escape(plan_id)}">'
                f'<input type="hidden" name="origen_semana" value="{semana}">'
                f'<button class="btn mini" type="submit">Repetir esta semana</button></form>'
            )
            tabla = _tabla_dias(datos) if datos.get("factible") else '<p class="meta">Sin menú factible.</p>'
            filas += (
                f'<div class="card"><div class="franja">Semana {semana} '
                f'<span style="float:right">{repetir}</span></div>{tabla}'
                f'<p class="meta">Coste: {datos.get("coste_total", 0):.2f} €</p></div>'
            )
        nota = (
            '<p class="note">Este es el plan actual.</p>' if es_actual else
            '<p class="note">Plan anterior (solo lectura). "Repetir esta semana" la añade '
            "como una semana nueva al final del plan actual.</p>"
        )
        exportar = (
            f'<p><a class="receta" href="/historial/{html.escape(plan_id)}/exportar.json">'
            "⬇️ Exportar este plan (.json, para compartirlo)</a></p>"
        )
        return _pagina(f"Plan {plan_id}", aviso + nota + exportar + filas)

    @app.get("/historial/{plan_id}/exportar.json")
    def historial_exportar(plan_id: str):
        conn, _ = _conn()
        try:
            data = exportar_plan_json(conn, plan_id)
        finally:
            conn.close()
        if data is None:
            return RedirectResponse(
                "/historial?msg=" + quote("Ese plan no existe."), status_code=303,
            )
        return Response(
            data, media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={plan_id}.json"},
        )

    @app.post("/historial/importar")
    async def historial_importar(request: Request):
        form = await request.form()
        fichero = form.get("fichero")
        contenido = await fichero.read() if fichero else b""
        conn, _ = _conn()
        try:
            nuevo_id = importar_plan_json(conn, contenido)
        finally:
            conn.close()
        if nuevo_id is None:
            return RedirectResponse(
                "/historial?msg=" + quote("El fichero no es un plan exportado válido."),
                status_code=303,
            )
        return RedirectResponse(
            f"/historial/{quote(nuevo_id)}?msg=" + quote("Plan importado."), status_code=303,
        )

    @app.post("/repetir-semana")
    def repetir_semana_ruta(origen_plan_id: str = Form(...), origen_semana: int = Form(...)):
        conn, _ = _conn()
        try:
            destino_plan_id, semanas_actual = cargar_plan(conn)
            if destino_plan_id is None:
                return RedirectResponse(
                    "/historial?msg=" + quote("No hay un plan actual al que añadir la semana."),
                    status_code=303,
                )
            destino_semana = max(semanas_actual) + 1 if semanas_actual else 1
            ok = repetir_semana(conn, origen_plan_id, origen_semana, destino_plan_id, destino_semana)
        finally:
            conn.close()
        if not ok:
            return RedirectResponse(
                "/historial?msg=" + quote("No se encontró esa semana."), status_code=303,
            )
        return RedirectResponse(f"/?semana={destino_semana}", status_code=303)

    # --- Dashboard (#65): gasto historico y top recetas, SVG inline (sin CDN) ---
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard_page():
        conn, _ = _conn()
        try:
            filas = conn.execute(
                "SELECT plan_id, semana, creado, datos FROM planes ORDER BY creado"
            ).fetchall()
            n_recetas_total = conn.execute("SELECT COUNT(*) FROM recetas").fetchone()[0]
        finally:
            conn.close()

        if not filas:
            return _pagina(
                "Dashboard",
                '<div class="card">Aún no hay planes generados: genera un menú para ver '
                "estadísticas aquí.</div>",
            )

        puntos: list[tuple[str, float]] = []  # (fecha, coste_semana)
        conteo_recetas: dict[str, int] = {}
        titulos: dict[str, str] = {}
        for f in filas:
            datos = json.loads(f["datos"])
            puntos.append((f["creado"][:10], float(datos.get("coste_total", 0) or 0)))
            info = datos.get("recetas_info", {}) or {}
            for rid in set(datos.get("seleccion_comida", {}) or {}) | set(datos.get("seleccion_cena", {}) or {}):
                conteo_recetas[rid] = conteo_recetas.get(rid, 0) + 1
                titulos[rid] = info.get(rid, {}).get("titulo", rid)

        # Sparkline SVG determinista (sin libreria de graficos, sin CDN).
        w, h, pad = 560, 120, 20
        costes = [c for _, c in puntos]
        c_min, c_max = min(costes), max(costes) or 1
        rango = (c_max - c_min) or 1
        n = len(puntos)
        xs = [pad + i * (w - 2 * pad) / max(1, n - 1) for i in range(n)]
        ys = [h - pad - (c - c_min) / rango * (h - 2 * pad) for c in costes]
        linea = " ".join(f"{x:.0f},{y:.0f}" for x, y in zip(xs, ys, strict=True))
        puntos_svg = "".join(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="var(--verde)">'
            f"<title>{html.escape(f)}: {c:.2f} €</title></circle>"
            for (f, c), x, y in zip(puntos, xs, ys, strict=True)
        )
        sparkline = (
            f'<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:{w}px;height:auto">'
            f'<polyline points="{linea}" fill="none" stroke="var(--verde)" stroke-width="2"/>'
            f"{puntos_svg}</svg>"
        )

        top = sorted(conteo_recetas.items(), key=lambda kv: -kv[1])[:10]
        filas_top = "".join(
            f"<tr><td>{html.escape(titulos.get(rid, rid))}</td>"
            f'<td style="text-align:right">{n_}×</td></tr>'
            for rid, n_ in top
        ) or '<tr><td colspan="2" class="meta">Sin datos.</td></tr>'

        cuerpo = (
            '<div class="card"><div class="franja">📈 Gasto por semana generada</div>'
            + sparkline
            + f'<p class="meta">{len(puntos)} semanas registradas · '
            f"último coste: {costes[-1]:.2f} € · media: {sum(costes) / len(costes):.2f} €</p></div>"
            '<div class="card"><div class="franja">⭐ Recetas más usadas</div>'
            f"<table>{filas_top}</table></div>"
            f'<div class="card"><p class="meta">Recetas en el corpus: <b>{n_recetas_total}</b></p></div>'
        )
        return _pagina("Dashboard", cuerpo)

    # --- Buscador global (#64): recetas + productos del catalogo en una sola caja ---
    @app.get("/buscar", response_class=HTMLResponse)
    def buscar_page(q: str = ""):
        q = q.strip()
        if not q:
            return _pagina(
                "Buscar",
                '<div class="card"><form method="get" action="/buscar">'
                '<input name="q" placeholder="Buscar recetas o productos…" autofocus '
                'style="width:100%;max-width:420px">'
                ' <button class="btn" type="submit">Buscar</button></form></div>',
            )
        conn, _ = _conn()
        try:
            like = f"%{q.lower()}%"
            recetas = conn.execute(
                "SELECT id, titulo, fuente FROM recetas WHERE lower(titulo) LIKE ? "
                "ORDER BY titulo LIMIT 30", (like,),
            ).fetchall()
            productos = conn.execute(
                "SELECT retailer_product_id, nombre, precio_eur FROM productos "
                "WHERE lower(nombre) LIKE ? ORDER BY nombre LIMIT 30", (like,),
            ).fetchall()
        finally:
            conn.close()
        filas_r = "".join(
            f'<tr><td><a class="receta" href="/receta/{html.escape(r["id"])}">'
            f'{html.escape(r["titulo"])}</a></td><td class="meta">{html.escape(r["fuente"] or "")}</td></tr>'
            for r in recetas
        ) or '<tr><td colspan="2" class="meta">Sin recetas.</td></tr>'
        def _fila_producto(p):
            precio = f'{p["precio_eur"]:.2f} €' if p["precio_eur"] is not None else "—"
            return (
                f'<tr><td>{html.escape(p["nombre"])}</td>'
                f'<td style="text-align:right">{precio}</td></tr>'
            )

        filas_p = "".join(_fila_producto(p) for p in productos) or (
            '<tr><td colspan="2" class="meta">Sin productos.</td></tr>'
        )
        cuerpo = (
            '<div class="card"><form method="get" action="/buscar">'
            f'<input name="q" value="{html.escape(q)}" style="width:100%;max-width:420px">'
            ' <button class="btn" type="submit">Buscar</button></form></div>'
            f'<div class="card"><div class="franja">Recetas ({len(recetas)})</div>'
            f"<table>{filas_r}</table></div>"
            f'<div class="card"><div class="franja">Productos del catálogo ({len(productos)})</div>'
            f"<table>{filas_p}</table></div>"
        )
        return _pagina(f"Buscar «{q}»", cuerpo)

    # --- Asistente de sustituciones de cocina (#100) ---
    @app.get("/sustituciones", response_class=HTMLResponse)
    def sustituciones_page(q: str = ""):
        q = q.strip()
        form = (
            '<div class="card"><form method="get" action="/sustituciones">'
            f'<input name="q" value="{html.escape(q)}" autofocus placeholder='
            '"¿Qué ingrediente te falta? (p.ej. nata, huevo, mantequilla)" '
            'style="width:100%;max-width:420px">'
            ' <button class="btn" type="submit">Buscar</button></form>'
            '<p class="note">Sustituciones de cocina habituales, no productos del catálogo: '
            "para eso ya está el matching de recetas.</p></div>"
        )
        if not q:
            return _pagina("Sustituciones", form)
        resultado = buscar_sustitutos(q)
        if not resultado:
            cuerpo = form + (
                f'<div class="card"><p class="meta">No tengo sustituciones para «{html.escape(q)}» '
                "todavía.</p></div>"
            )
            return _pagina(f"Sustituciones para «{q}»", cuerpo)
        clave, alternativas = resultado
        filas = "".join(f"<li>{html.escape(a)}</li>" for a in alternativas)
        cuerpo = form + (
            f'<div class="card"><div class="franja">En vez de «{html.escape(clave)}», prueba:</div>'
            f"<ul>{filas}</ul></div>"
        )
        return _pagina(f"Sustituciones para «{q}»", cuerpo)

    # --- Cola de correcciones de matching (#13/#14): asignar producto a mano ---
    @app.get("/matching", response_class=HTMLResponse)
    def matching_page(ing: str = "", q: str = "", msg: str = ""):
        conn, _ = _conn()
        try:
            repo = MatchingRepository(conn)
            total, con = repo.contar_mapeos(), repo.contar_con_match()
            aviso = f'<div class="card"><p class="ok">{html.escape(msg)}</p></div>' if msg else ""
            cab = (
                '<div class="card"><div class="franja">Correcciones de matching</div>'
                f'<p class="meta">Emparejados <b>{con}</b>/{total} · '
                f"sin producto: <b>{total - con}</b>. Asigna a mano los que falten para que "
                "el menú pueda usar esas recetas.</p></div>"
            )
            n_descatalogados = len(productos_descatalogados(conn))
            if n_descatalogados:
                cab += (
                    '<div class="card"><div class="franja">Posibles descatalogados (#117)</div>'
                    f'<p class="meta"><b>{n_descatalogados}</b> ingrediente(s) emparejados con un '
                    "producto que no apareció en la última actualización del catálogo (puede que "
                    "Alcampo lo haya dejado de vender).</p>"
                    '<form method="post" action="/matching/rematch-descatalogados">'
                    '<button class="btn sec" type="submit">Buscar sustituto automáticamente</button>'
                    "</form></div>"
                )
            if ing:
                # Buscar productos candidatos para el ingrediente `ing`.
                like = f"%{q.strip().lower()}%" if q.strip() else f"%{ing.split()[0]}%"
                prods = conn.execute(
                    "SELECT retailer_product_id, nombre, marca, precio_eur FROM productos "
                    "WHERE apto_receta=1 AND lower(nombre) LIKE ? ORDER BY precio_por_unidad "
                    "LIMIT 40", (like,),
                ).fetchall()
                filas = "".join(
                    f'<tr><td>{html.escape(p["nombre"])}<br>'
                    f'<span class="meta">{html.escape(p["marca"] or "")} · '
                    f'{(f"{p["precio_eur"]:.2f} €") if p["precio_eur"] is not None else "—"}</span></td>'
                    f'<td style="text-align:right"><form method="post" action="/matching/asignar">'
                    f'<input type="hidden" name="ing" value="{html.escape(ing)}">'
                    f'<input type="hidden" name="rid" value="{html.escape(p["retailer_product_id"])}">'
                    f'<button class="btn mini" type="submit">Asignar</button></form></td></tr>'
                    for p in prods
                ) or '<tr><td colspan="2">Sin resultados. Prueba otro término.</td></tr>'
                cuerpo = (
                    aviso + cab
                    + f'<div class="card"><div class="franja">Asignar producto a «{html.escape(ing)}»</div>'
                    '<form method="get" action="/matching">'
                    f'<input type="hidden" name="ing" value="{html.escape(ing)}">'
                    f'<input name="q" value="{html.escape(q)}" placeholder="buscar producto…" '
                    'style="max-width:320px"> <button class="btn sec" type="submit">Buscar</button>'
                    ' <a class="btn sec" href="/matching">← volver a la lista</a></form>'
                    f"<table>{filas}</table></div>"
                )
                return _pagina("Correcciones", cuerpo)
            # Lista de ingredientes sin match.
            faltan = repo.sin_match(limite=200)
            filas = "".join(
                f'<tr><td>{html.escape(i)}</td>'
                f'<td style="text-align:right"><a class="btn mini" '
                f'href="/matching?ing={html.escape(i)}">Buscar producto…</a></td></tr>'
                for i in faltan
            ) or '<tr><td colspan="2">🎉 No hay ingredientes sin emparejar.</td></tr>'
            # Editor de sinonimos (#22/#14).
            sins = repo.sinonimos()
            filas_sin = "".join(
                f'<tr><td>{html.escape(p)} → {html.escape(r)}</td>'
                f'<td style="text-align:right"><form method="post" action="/matching/sinonimo/borrar">'
                f'<input type="hidden" name="palabra" value="{html.escape(p)}">'
                f'<button class="btn mini sec" type="submit">Borrar</button></form></td></tr>'
                for p, r in sorted(sins.items())
            ) or '<tr><td colspan="2">Sin sinónimos definidos.</td></tr>'
            editor = (
                '<div class="card"><div class="franja">Sinónimos (aprender correcciones)</div>'
                '<p class="note">Enseña al matcher que una palabra equivale a otra (p. ej. '
                '«ajoporro → puerro»). Se aplican al volver a emparejar (Catálogo → actualizar, '
                'o el comando de emparejado).</p>'
                '<form method="post" action="/matching/sinonimo" class="row">'
                '<div><label>Palabra</label><input name="palabra" placeholder="ajoporro"></div>'
                '<div><label>Equivale a</label><input name="reemplazo" placeholder="puerro"></div>'
                '<div style="align-self:end"><button class="btn" type="submit">Añadir</button></div>'
                f'</form><table>{filas_sin}</table></div>'
            )
            cuerpo = aviso + cab + f'<div class="card"><table>{filas}</table></div>' + editor
            return _pagina("Correcciones", cuerpo)
        finally:
            conn.close()

    @app.post("/matching/asignar")
    async def matching_asignar(ing: str = Form(""), rid: str = Form("")):
        from datetime import datetime

        conn, _ = _conn()
        try:
            ok = MatchingRepository(conn).asignar_producto(
                ing.strip(), rid.strip(), datetime.now(UTC).isoformat(timespec="seconds")
            )
        finally:
            conn.close()
        invalidar_cache_recetas()  # el mapeo cambio -> recalcular coste/nutricion
        msg = f"«{ing}» asignado." if ok else "No se pudo asignar (producto no encontrado)."
        return RedirectResponse(f"/matching?msg={quote(msg)}", status_code=303)

    # --- Importar receta por URL (#42), reutiliza recipe-scrapers (583 sitios, #48) ---
    @app.post("/recetas/importar")
    async def recetas_importar(url: str = Form("")):
        from datetime import datetime

        from ..recetas.repositorio import RecetaRepository
        from ..recetas.scraper import RecetaScraper

        url = url.strip()
        if not url.startswith("http"):
            return RedirectResponse(
                f"/recetas?msg={quote('Pega una URL válida (http/https).')}", status_code=303
            )
        try:
            with RecetaScraper() as scraper:
                receta = scraper.scrape(url)
        except Exception as e:  # noqa: BLE001 - red/parseo: se informa, no se rompe
            return RedirectResponse(f"/recetas?msg={quote(f'No se pudo importar: {e}')}", status_code=303)
        if receta is None:
            return RedirectResponse(
                f"/recetas?msg={quote('Esa página no tiene una receta reconocible (schema.org).')}",
                status_code=303,
            )
        conn, _ = _conn()
        try:
            RecetaRepository(conn).upsert_receta(
                receta, datetime.now(UTC).isoformat(timespec="seconds")
            )
            conn.commit()
        finally:
            conn.close()
        invalidar_cache_recetas()
        msg = f"Receta importada: «{receta.titulo}». Recuerda emparejarla con el catálogo."
        return RedirectResponse(f"/receta/{receta.id}?msg={quote(msg)}", status_code=303)

    @app.post("/matching/sinonimo")
    async def matching_sinonimo(palabra: str = Form(""), reemplazo: str = Form("")):
        from datetime import datetime

        conn, _ = _conn()
        try:
            if palabra.strip() and reemplazo.strip():
                MatchingRepository(conn).anadir_sinonimo(
                    palabra, reemplazo, datetime.now(UTC).isoformat(timespec="seconds")
                )
                msg = f"Sinónimo «{palabra.strip()} → {reemplazo.strip()}» guardado."
            else:
                msg = "Indica palabra y equivalencia."
        finally:
            conn.close()
        return RedirectResponse(f"/matching?msg={quote(msg)}", status_code=303)

    @app.post("/matching/sinonimo/borrar")
    async def matching_sinonimo_borrar(palabra: str = Form("")):
        conn, _ = _conn()
        try:
            MatchingRepository(conn).borrar_sinonimo(palabra)
        finally:
            conn.close()
        return RedirectResponse("/matching?msg=Sinónimo borrado.", status_code=303)

    @app.post("/matching/rematch-descatalogados")
    def matching_rematch_descatalogados():
        conn, _ = _conn()
        try:
            resumen = rematch_descatalogados(conn)
        finally:
            conn.close()
        msg = (
            f"Revisados {resumen['revisados']}, re-emparejados {resumen['reemparejados']}."
            if resumen["revisados"]
            else "No hay ningún ingrediente descatalogado que revisar."
        )
        return RedirectResponse(f"/matching?msg={quote(msg)}", status_code=303)

    @app.post("/carrito/enviar")
    async def carrito_enviar(request: Request):
        form = await request.form()
        sincronizar = form.get("sincronizar") == "1"
        vaciar_antes = form.get("vaciar_antes") == "1"
        _ok, msg = _lanzar_carrito(config_path, sincronizar=sincronizar, vaciar_antes=vaciar_antes)
        return RedirectResponse(f"/compra?msg={quote(msg)}", status_code=303)

    @app.post("/carrito/instalar-navegador")
    def carrito_instalar_navegador():
        ok = _lanzar_instalar_chromium()
        msg = "Instalando Chromium en 2º plano…" if ok else "Ya hay una instalación en marcha."
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
            "marcadas. Va a ritmo lento para no saturar la web; puedes seguir usando la app.</p>"
            '<p><a class="receta" href="/catalogo/validar">🔍 Revisar datos anómalos (#120)</a></p>'
            "</div>"
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
            '<div class="card">'
            '<div class="franja" style="display:flex;justify-content:space-between;'
            'align-items:center;gap:10px">'
            '<span>Ver y corregir el catálogo</span>'
            '<span style="display:flex;gap:8px">'
            '<a class="btn neu mini" href="/buscar" style="min-width:96px" '
            'title="Buscar recetas o productos">Buscar</a>'
            '<a class="btn neu mini" href="/matching" style="min-width:96px" '
            'title="Emparejar ingredientes sin producto">Correcciones</a>'
            '</span></div>'
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
            "Catálogo", aviso + actualizar_card + visor, refrescar=4 if activa else None,
            activa="catalogo",
        )

    @app.get("/catalogo/validar", response_class=HTMLResponse)
    def catalogo_validar_page():
        conn, _ = _conn()
        try:
            problemas = validar_datos(conn)
        finally:
            conn.close()
        if not problemas:
            return _pagina(
                "Revisión de datos",
                '<div class="card ok">No se ha encontrado ningún dato anómalo. ✓</div>',
            )
        filas = "".join(
            f'<tr><td><a class="receta" href="/catalogo/{html.escape(p["retailer_product_id"])}">'
            f'{html.escape(p["nombre"])}</a></td><td>{html.escape(p["problema"])}</td></tr>'
            for p in problemas
        )
        cuerpo = (
            f'<div class="card"><div class="franja">{len(problemas)} productos para revisar</div>'
            '<p class="meta">Precios/nutrientes físicamente imposibles o inconsistentes (#120). '
            "No se corrige nada automáticamente: revisa y edita cada producto si hace falta.</p>"
            f"<table><tr><th>Producto</th><th>Problema</th></tr>{filas}</table></div>"
        )
        return _pagina("Revisión de datos", cuerpo)

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
        invalidar_cache_recetas()  # el precio/nutricion cambio -> recalcular coste (#34)
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
            '<div style="display:flex;justify-content:space-between;align-items:center;'
            'gap:10px;margin-top:12px">'
            f'<p class="meta" style="margin:0">Mostrando {len(recetas)} recetas (las tuyas '
            "primero). Las del catálogo (scrapeadas) solo se pueden ver; las tuyas se pueden "
            'editar.</p>'
            '<a class="btn neu mini" href="/sustituciones" style="white-space:nowrap" '
            'title="Sustitutos de cocina">Sustituciones</a></div></div>'
            '<div class="card"><div class="franja">Importar receta por URL</div>'
            '<form method="post" action="/recetas/importar" class="row">'
            '<div style="flex:3 1 320px"><input name="url" placeholder="https://…" '
            'style="width:100%"></div>'
            '<div><button class="btn" type="submit">Importar</button></div></form>'
            '<p class="note">Funciona con webs de recetas que publican datos estructurados '
            "(schema.org) — cientos de sitios soportados. Tras importar, empareja sus "
            "ingredientes con el catálogo (Correcciones) para que entre en el menú.</p></div>"
        )
        return _pagina("Recetas", cuerpo, activa="recetas")

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
            # strict=False: el formulario puede llegar con listas de longitud distinta
            # si el JS del cliente falla al añadir/quitar una fila; no debe romper el guardado.
            for n, c, u in zip(nombres, cantidades, unidades, strict=False)
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

    # --------------------- valoración personal de recetas (Lote 12) ---------------------

    @app.get("/valoraciones", response_class=HTMLResponse)
    def valoraciones_page(q: str = "", msg: str = ""):
        conn, _ = _conn()
        try:
            pendientes = recetas_para_valorar(conn)
            valoradas = listar_recetas_valoradas(conn, q=q)
        finally:
            conn.close()
        aviso = f'<div class="card ok">{html.escape(msg)}</div>' if msg else ""
        filas_pend = "".join(
            f'<li><a class="receta" href="/valoraciones/{html.escape(p["receta_id"])}">'
            f'{html.escape(p["titulo"])}</a></li>'
            for p in pendientes
        ) or "<li class='meta'>Nada pendiente: todo lo cocinado recientemente ya está valorado.</li>"
        cola = (
            '<div class="card"><div class="franja">Recetas por valorar</div>'
            '<p class="meta">Cocinadas esta semana o la anterior, sin valorar todavía.</p>'
            f"<ul style='padding-left:20px'>{filas_pend}</ul></div>"
        )
        filas_valoradas = "".join(
            f'<tr><td><a class="receta" href="/valoraciones/{html.escape(v["id"])}">'
            f'{html.escape(v["titulo"])}</a></td>'
            f'<td style="text-align:right">{v["media"]:.1f} ★ ({v["n_baremos"]} baremos)</td></tr>'
            for v in valoradas
        ) or '<tr><td colspan="2" class="meta">Ninguna todavía.</td></tr>'
        historico = (
            '<div class="card"><div class="franja">Ya valoradas (re-valorar)</div>'
            '<form method="get" action="/valoraciones">'
            f'<input name="q" value="{html.escape(q)}" placeholder="Buscar receta…" '
            'style="max-width:320px;display:inline-block">'
            ' <button class="btn mini" type="submit">Buscar</button></form>'
            f'<table style="margin-top:10px"><tr><th>Receta</th><th>Media</th></tr>'
            f"{filas_valoradas}</table></div>"
        )
        return _pagina("Valoración de recetas", aviso + cola + historico)

    @app.get("/valoraciones/{receta_id}", response_class=HTMLResponse)
    def valoracion_receta_page(receta_id: str):
        conn, _ = _conn()
        try:
            titulo_fila = conn.execute(
                "SELECT titulo FROM recetas WHERE id = ?", (receta_id,)
            ).fetchone()
            if titulo_fila is None:
                return _pagina("Valorar receta", '<div class="card warn">Receta no encontrada.</div>')
            actuales = valoraciones_de(conn, receta_id)
            detalle = detalle_de(conn, receta_id)
        finally:
            conn.close()

        filas_baremos = "".join(
            f'<div class="row" style="align-items:center">'
            f'<label style="flex:2">{html.escape(etiqueta)}</label>'
            f'<select name="baremo__{clave}" style="flex:1">'
            + "".join(
                f'<option value="{n}"{" selected" if actuales.get(clave) == n else ""}>'
                f'{"★" * n} ({n})</option>'
                for n in range(1, 6)
            )
            + "</select></div>"
            for clave, etiqueta in BAREMOS
        )
        cuerpo = (
            f'<div class="card"><div class="big">{html.escape(titulo_fila["titulo"])}</div>'
            f'<form method="post" action="/valoraciones/{html.escape(receta_id)}">'
            f"{filas_baremos}"
            '<label style="margin-top:10px">Ingredientes que más te gustaron (uno por línea)</label>'
            f'<textarea name="ingredientes" rows="3">{html.escape(chr(10).join(detalle["ingrediente"]))}</textarea>'
            '<label>¿Algo del método de preparación? (uno por línea)</label>'
            f'<textarea name="metodo" rows="2">{html.escape(chr(10).join(detalle["metodo"]))}</textarea>'
            '<div style="margin-top:10px"><button class="btn" type="submit">Guardar valoración</button></div>'
            "</form></div>"
        )
        return _pagina("Valorar receta", cuerpo)

    @app.post("/valoraciones/{receta_id}")
    async def valoracion_receta_guardar(receta_id: str, request: Request):
        form = await request.form()
        estrellas = {}
        for clave, _etiqueta in BAREMOS:
            valor = form.get(f"baremo__{clave}")
            if valor:
                try:
                    estrellas[clave] = int(valor)
                except ValueError:
                    pass
        ingredientes = [t for t in str(form.get("ingredientes", "")).splitlines() if t.strip()]
        metodo = [t for t in str(form.get("metodo", "")).splitlines() if t.strip()]
        conn, _ = _conn()
        try:
            guardar_valoracion(conn, receta_id, estrellas, ingredientes, metodo)
        finally:
            conn.close()
        return RedirectResponse("/valoraciones?msg=Valoración guardada.", status_code=303)

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
            + _num("ninos", "…de los cuales, niños (#108)", int(cfg.get("ninos", 0) or 0),
                   "Comen una fracción de ración de adulto (ver abajo). 0 = todos adultos.",
                   "1", "0")
            + _num("factor_racion_infantil", "Ración infantil (%)",
                   round(float(cfg.get("factor_racion_infantil", 0.6)) * 100),
                   "Qué fracción de una ración de adulto come un niño.", "5", "0")
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
            + _num("presupuesto_max_semana", "Presupuesto máx./semana (€)",
                   round(float(cfg.get("presupuesto_max_semana", 0) or 0)),
                   "Tope de gasto semanal. 0 = sin tope. Si es muy bajo puede no haber "
                   "menú posible sin saltarse los nutrientes.", "5", "0")
            + _num("presupuesto_max_por_comensal_semana", "…o por comensal (€) (#113)",
                   round(float(cfg.get("presupuesto_max_por_comensal_semana", 0) or 0)),
                   "Si es >0, manda sobre el de arriba y se multiplica por el nº de "
                   "comensales (el tope se ajusta solo si cambia el tamaño del hogar). "
                   "0 = usar el presupuesto por semana.", "1", "0")
            + (
                '<div style="flex:2 1 320px"><label>Ingredientes que NO quieres</label>'
                '<input name="ingredientes_excluidos" '
                f'value="{html.escape(", ".join(cfg.get("ingredientes_excluidos", []) or []))}" '
                'placeholder="hígado, coliflor, cilantro">'
                '<p class="note">Separa por comas. Se excluye cualquier receta que los use.</p></div>'
            )
            + (
                '<div style="flex:2 1 320px"><label>Alérgenos a evitar</label>'
                '<input name="alergenos" '
                f'value="{html.escape(", ".join(cfg.get("alergenos", []) or []))}" '
                'placeholder="gluten, lactosa, frutos secos">'
                '<p class="note">Excluye recetas cuyos productos contengan estos alérgenos '
                "(según datos disponibles; no garantiza ausencia total).</p></div>"
            )
            + (
                '<div style="flex:2 1 320px"><label>Utensilios que NO tienes</label>'
                '<input name="utensilios_excluidos" '
                f'value="{html.escape(", ".join(cfg.get("utensilios_excluidos", []) or []))}" '
                'placeholder="horno, olla exprés, freidora">'
                '<p class="note">Excluye recetas que los requieran (detectado por título/'
                "instrucciones).</p></div>"
            )
            + (
                '<div style="flex:2 1 320px"><label>Despensa (lo que ya tienes en casa)</label>'
                '<input name="despensa" '
                f'value="{html.escape(", ".join(cfg.get("despensa", []) or []))}" '
                'placeholder="sal, aceite de oliva, especias">'
                '<p class="note">Separa por comas. No aparece en la lista de la compra, y si '
                '"Cocinar con la despensa" está por encima de 0 %, se priorizan recetas que lo '
                "usen (#97).</p></div>"
            )
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
            + _slider("salud_pct", "Priorizar salud",
                      _pct(cfg, "salud_pct"),
                      "Premia recetas más sanas (verdura, legumbre, pescado, fruta; menos "
                      "grasa saturada, azúcar y sal). 0 % = solo cuentan coste y sabor.")
            + _slider("sobra_pct", "Reducir sobras",
                      _pct(cfg, "sobra_pct"),
                      "Prefiere menús que aprovechan el formato comprado (menos desperdicio "
                      "de producto). 0 % = desactivado. Sube el tiempo de cálculo (hasta ~25 s).")
            + _slider("evitar_procesados_pct", "Evitar ultraprocesados",
                      _pct(cfg, "evitar_procesados_pct"),
                      "Penaliza recetas con productos muy procesados (bollería, precocinados, "
                      "con aditivos…). 0 % = desactivado.")
            + _slider("estacionalidad_pct", "Preferir temporada",
                      _pct(cfg, "estacionalidad_pct"),
                      "Premia recetas con frutas y verduras de temporada este mes (más baratas "
                      "y sabrosas). 0 % = desactivado.")
            + _slider("despensa_pct", "Cocinar con la despensa",
                      _pct(cfg, "despensa_pct"),
                      "Premia recetas que usan ingredientes de tu despensa (los que ya tienes "
                      "en casa, ver más abajo). 0 % = desactivado.")
            + _slider("festivo_pct", "Temporada festiva",
                      _pct(cfg, "festivo_pct"),
                      "Premia recetas cuyo título encaja con la época del año (Navidad en "
                      "diciembre; barbacoa/platos fríos en verano). 0 % = desactivado.")
            + "</div><div class='row'>"
            + _num("tiempo_max_receta_min", "Tiempo máx. de receta (min)",
                   int(cfg.get("tiempo_max_receta_min", 0) or 0),
                   "Descarta recetas que tarden más de estos minutos (0 = sin límite). "
                   "Útil para entre semana.", "5", "0")
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
        # --- Perfil corporal: calcular kcal automaticamente (#4/#5) ---
        perfil = cfg.get("perfil", {}) or {}
        auto = bool(perfil.get("calcular_kcal_auto"))
        from ..optimizacion.servicio import kcal_desde_perfil as _kcal_perfil
        kcal_calc = _kcal_perfil(perfil)
        estado_kcal = (
            f'<p class="ok">Con este perfil: <b>{kcal_calc:.0f} kcal/día</b>.</p>'
            if kcal_calc else '<p class="note">Completa los datos para calcular las kcal.</p>'
        )

        def _sel_perfil(nombre, etiqueta, opciones, actual):
            ops = "".join(
                f'<option value="{v}"{" selected" if str(actual) == v else ""}>{t}</option>'
                for v, t in opciones
            )
            return f'<div><label>{etiqueta}</label><select name="{nombre}">{ops}</select></div>'

        cuerpo += (
            '<div class="card"><div class="franja">Perfil y calorías</div>'
            '<form method="post" action="/config/perfil"><div class="row">'
            '<div><label style="display:inline-flex;align-items:center;gap:6px">'
            f'<input type="checkbox" name="calcular_kcal_auto" value="1" style="width:auto" '
            f'{"checked" if auto else ""}> Calcular kcal automáticamente</label>'
            '<p class="note">Si lo activas, las kcal salen de tu perfil (Mifflin-St Jeor).</p></div>'
            + _num("peso_kg", "Peso (kg)", int(perfil.get("peso_kg", 70)), "", "1", "20")
            + _num("altura_cm", "Altura (cm)", int(perfil.get("altura_cm", 175)), "", "1", "100")
            + _num("edad", "Edad", int(perfil.get("edad", 30)), "", "1", "10")
            + "</div><div class='row'>"
            + _sel_perfil("sexo", "Sexo", [("h", "Hombre"), ("m", "Mujer")], perfil.get("sexo", "h"))
            + _sel_perfil("actividad", "Actividad", [
                ("sedentario", "Sedentario"), ("ligero", "Ligero"), ("moderado", "Moderado"),
                ("activo", "Activo"), ("muy_activo", "Muy activo")], perfil.get("actividad", "moderado"))
            + _sel_perfil("objetivo", "Objetivo", [
                ("perder", "Perder peso"), ("mantener", "Mantener"), ("ganar", "Ganar músculo")],
                perfil.get("objetivo", "mantener"))
            + "</div>"
            + estado_kcal
            + '<div style="margin-top:10px"><button class="btn" type="submit">Guardar perfil</button></div>'
            "</form></div>"
        )
        # --- Actualizaciones (Fase 11): un solo boton, repo fijo, instala solo ---
        info = _ACTUALIZACION["estado"]
        canal_actual = str((cfg.get("actualizaciones", {}) or {}).get("canal", "estable"))
        if info:
            beta_chip = ' <span class="chip">beta</span>' if info.es_beta else ""
            estado_upd = (
                f'<p class="ok">✨ Nueva versión <b>{html.escape(info.version)}</b>{beta_chip} disponible.</p>'
            )
            if info.notas:  # changelog inline (#76)
                estado_upd += (
                    f'<details><summary class="meta">Ver novedades</summary>'
                    f'<pre class="log" style="white-space:pre-wrap">{html.escape(info.notas[:2000])}</pre></details>'
                )
        elif _ACTUALIZACION["comprobado"]:
            estado_upd = f'<p class="meta">Estás en la última versión (v{__version__}).</p>'
        else:
            estado_upd = '<p class="meta">Pulsa el botón para comprobar si hay una versión nueva.</p>'
        cuerpo += (
            '<div class="card"><div class="franja">Actualizaciones de la aplicación</div>'
            f'<p class="meta">Versión instalada: <b>{__version__}</b></p>'
            '<form method="post" action="/config/canal" style="margin-bottom:10px">'
            '<label>Canal <select name="canal" onchange="this.form.submit()">'
            f'<option value="estable"{" selected" if canal_actual != "beta" else ""}>Estable</option>'
            f'<option value="beta"{" selected" if canal_actual == "beta" else ""}>Beta (#77)</option>'
            "</select></label></form>"
            '<form method="post" action="/actualizaciones/comprobar">'
            '<button class="btn" type="submit">Buscar actualización</button></form>'
            f"{estado_upd}"
            '<p class="note">Comprueba GitHub: si hay una versión nueva, la descarga en 2º plano '
            "y la deja lista; al pulsar Instalar, verifica su integridad (hash) y abre el "
            "instalador. En el canal beta también se ofrecen versiones de prueba.</p></div>"
        )
        # --- Copias de seguridad (#80) ---
        db_path = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        backups = listar_backups(db_path)
        filas_backup = "".join(
            f'<tr><td>{html.escape(b.fecha)}</td><td>{b.tamano_kb:.0f} KB</td>'
            f'<td style="text-align:right"><form method="post" action="/config/backups/restaurar" '
            f'onsubmit="return confirm(\'¿Restaurar este backup? Se sobrescribirán los datos actuales '
            f'(se guarda antes una copia de seguridad).\')">'
            f'<input type="hidden" name="nombre" value="{html.escape(b.ruta.name)}">'
            f'<button class="btn mini sec" type="submit">Restaurar</button></form></td></tr>'
            for b in backups[:15]
        ) or '<tr><td colspan="3" class="meta">Sin copias todavía.</td></tr>'
        cuerpo += (
            '<div class="card"><div class="franja">Copias de seguridad</div>'
            '<form method="post" action="/config/backups/crear">'
            '<button class="btn sec" type="submit">Crear copia ahora</button></form>'
            f'<table><tr><th>Fecha</th><th>Tamaño</th><th></th></tr>{filas_backup}</table>'
            '<p class="note">Se crea una copia automática al arrancar la app (BD + tu '
            "configuración). Se conservan las últimas 10; restaurar guarda antes el estado "
            "actual, por si acaso.</p></div>"
        )
        # --- Catálogo programado (#116) ---
        auto_cat = bool(cfg.get("catalogo_auto_actualizar", False))
        dias_alerta = int(cfg.get("catalogo_dias_alerta", 7) or 7)
        dias_actual = _CATALOGO_ANTIGUEDAD["dias"]
        estado_cat = (
            f'<p class="meta">Catálogo actualizado hace <b>{dias_actual} día(s)</b>.</p>'
            if dias_actual is not None else '<p class="meta">Aún sin comprobar.</p>'
        )
        cuerpo += (
            '<div class="card"><div class="franja">Catálogo programado</div>'
            + estado_cat
            + '<form method="post" action="/config/catalogo-programado">'
            f'<label>Avisar si lleva más de <input name="catalogo_dias_alerta" type="number" '
            f'min="1" value="{dias_alerta}" style="width:70px;display:inline-block"> días sin '
            "actualizarse</label>"
            '<label style="margin-top:8px"><input type="checkbox" name="catalogo_auto_actualizar" '
            f'value="1" style="width:auto" {"checked" if auto_cat else ""}> Actualizarlo solo, en '
            "2º plano, al superar ese umbral</label>"
            '<div style="margin-top:10px"><button class="btn sec" type="submit">Guardar</button></div>'
            "</form>"
            '<p class="note">El auto-refresco tarda y usa la web de Alcampo; por eso está '
            "desactivado por defecto. Sin él, solo verás un aviso en el menú.</p></div>"
        )
        # --- Diagnostico de errores LOCAL, opt-in (#81) ---
        telemetria_on = bool(cfg.get("telemetria_local", False))
        errores = leer_ultimos_errores() if telemetria_on else ""
        cuerpo += (
            '<div class="card"><div class="franja">Diagnóstico de errores</div>'
            '<form method="post" action="/config/telemetria">'
            '<label style="display:inline-flex;align-items:center;gap:6px">'
            f'<input type="checkbox" name="activo" value="1" style="width:auto" '
            f'{"checked" if telemetria_on else ""} onchange="this.form.submit()"> '
            "Guardar un registro local de errores</label></form>"
            + (f'<pre class="log">{html.escape(errores) or "(sin errores registrados)"}</pre>'
               + '<form method="post" action="/config/telemetria/limpiar" style="margin-top:6px">'
               '<button class="btn mini sec" type="submit">Limpiar registro</button></form>'
               if telemetria_on else "")
            + '<p class="note">100% LOCAL: no se envía nada por red (Sazón no tiene servidor '
            "propio). Solo queda en tu equipo, por si necesitas revisar un fallo.</p></div>"
        )
        # --- Apariencia (#63): tema claro/oscuro/sistema (movido aquí desde la barra) ---
        cuerpo += (
            '<div class="card"><div class="franja">Apariencia</div>'
            "<label>Tema</label>"
            '<div class="seg" role="group" aria-label="Tema de color">'
            '<button type="button" data-tema-btn="light" onclick="ponerTema(\'light\')">Claro</button>'
            '<button type="button" data-tema-btn="dark" onclick="ponerTema(\'dark\')">Oscuro</button>'
            '<button type="button" data-tema-btn="system" onclick="ponerTema(null)">Sistema</button>'
            "</div>"
            "<script>"
            "function ponerTema(t){var e=document.documentElement;"
            'if(t){e.setAttribute("data-theme",t);localStorage.setItem("sazon-tema",t);}'
            'else{e.removeAttribute("data-theme");localStorage.removeItem("sazon-tema");}'
            "marcarTemaActivo();}"
            'function marcarTemaActivo(){var t=localStorage.getItem("sazon-tema")||"system";'
            'document.querySelectorAll("[data-tema-btn]").forEach(function(b){'
            'b.classList.toggle("on",b.dataset.temaBtn===t);});}'
            "marcarTemaActivo();"
            "</script></div>"
        )
        return _pagina("Configuración", cuerpo)

    @app.post("/config/perfil")
    async def config_perfil(request: Request):
        form = await request.form()
        try:
            perfil = {
                "calcular_kcal_auto": form.get("calcular_kcal_auto") == "1",
                "peso_kg": float(form.get("peso_kg", 70) or 70),
                "altura_cm": float(form.get("altura_cm", 175) or 175),
                "edad": int(form.get("edad", 30) or 30),
                "sexo": str(form.get("sexo", "h")),
                "actividad": str(form.get("actividad", "moderado")),
                "objetivo": str(form.get("objetivo", "mantener")),
            }
        except (TypeError, ValueError):
            return RedirectResponse("/config?msg=Perfil: valores no válidos.", status_code=303)
        guardar_overlay(config_path, {"perfil": perfil})
        return RedirectResponse("/config?msg=Perfil guardado.", status_code=303)

    @app.post("/config/catalogo-programado")
    async def config_catalogo_programado(request: Request):
        form = await request.form()
        guardar_overlay(config_path, {
            "catalogo_dias_alerta": max(1, int(form.get("catalogo_dias_alerta", 7) or 7)),
            "catalogo_auto_actualizar": form.get("catalogo_auto_actualizar") == "1",
        })
        return RedirectResponse("/config?msg=Preferencia guardada.", status_code=303)

    @app.post("/config/telemetria")
    async def config_telemetria(request: Request):
        form = await request.form()
        guardar_overlay(config_path, {"telemetria_local": form.get("activo") == "1"})
        return RedirectResponse("/config?msg=Preferencia guardada.", status_code=303)

    @app.post("/config/telemetria/limpiar")
    def config_telemetria_limpiar():
        limpiar_log()
        return RedirectResponse("/config?msg=Registro limpiado.", status_code=303)

    @app.post("/config/backups/crear")
    def config_backups_crear():
        cfg = cargar_config(config_path)
        db_path = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        ruta = crear_backup(db_path, ruta_overlay(config_path))
        msg = f"Copia creada: {ruta.name}" if ruta else "No hay base de datos que respaldar."
        return RedirectResponse(f"/config?msg={quote(msg)}", status_code=303)

    @app.post("/config/backups/restaurar")
    async def config_backups_restaurar(nombre: str = Form("")):
        cfg = cargar_config(config_path)
        db_path = Path((cfg.get("almacenamiento", {}) or {}).get("db_path", "data/menu.db"))
        backups = {b.ruta.name: b.ruta for b in listar_backups(db_path)}
        ruta = backups.get(nombre)
        if ruta is None:
            return RedirectResponse(
                f"/config?msg={quote('Backup no encontrado.')}", status_code=303
            )
        restaurar_backup(ruta, db_path, ruta_overlay(config_path))
        return RedirectResponse(
            f"/config?msg={quote(f'Restaurado desde {nombre}.')}", status_code=303
        )

    @app.post("/config/canal")
    async def config_canal(request: Request):
        form = await request.form()
        canal = str(form.get("canal", "estable"))
        if canal not in ("estable", "beta"):
            canal = "estable"
        guardar_overlay(config_path, {"actualizaciones": {"canal": canal}})
        _ACTUALIZACION["comprobado"] = False
        _ACTUALIZACION["estado"] = None
        _ACTUALIZACION["descarga"] = None
        return RedirectResponse("/config?msg=Canal actualizado.", status_code=303)

    @app.post("/actualizaciones/comprobar")
    def actualizaciones_comprobar():
        """Comprueba GitHub y, si hay version nueva, la descarga (o usa la ya
        predescargada en 2º plano, #75) y la instala."""
        cfg = cargar_config(config_path)
        canal = str((cfg.get("actualizaciones", {}) or {}).get("canal", "estable"))
        info = hay_actualizacion(canal=canal)
        if info is None or info != _ACTUALIZACION["estado"]:
            _ACTUALIZACION["descarga"] = None  # version distinta: invalida la pre-descarga
        _ACTUALIZACION["estado"] = info
        _ACTUALIZACION["comprobado"] = True
        if info is None:
            msg = f"Ya tienes la última versión de Sazón (v{__version__})."
        else:
            _ok, msg = instalar(info, ruta_predescargada=_ACTUALIZACION["descarga"])
        return RedirectResponse(f"/config?msg={quote(msg)}", status_code=303)

    @app.post("/config")
    async def config_save(request: Request):
        form = await request.form()
        try:
            cambios = {
                "num_comensales": int(form.get("num_comensales", 2)),
                "ninos": int(form.get("ninos", 0) or 0),
                "factor_racion_infantil": max(0.1, float(form.get("factor_racion_infantil", 60)) / 100),
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
                "salud_pct": float(form.get("salud_pct", 0)),
                "sobra_pct": float(form.get("sobra_pct", 0)),
                "evitar_procesados_pct": float(form.get("evitar_procesados_pct", 0)),
                "estacionalidad_pct": float(form.get("estacionalidad_pct", 0)),
                "despensa_pct": float(form.get("despensa_pct", 0)),
                "festivo_pct": float(form.get("festivo_pct", 0)),
                "tiempo_max_receta_min": int(form.get("tiempo_max_receta_min", 0) or 0),
                "presupuesto_max_semana": float(form.get("presupuesto_max_semana", 0) or 0),
                "presupuesto_max_por_comensal_semana": float(
                    form.get("presupuesto_max_por_comensal_semana", 0) or 0
                ),
                "ingredientes_excluidos": [
                    t.strip() for t in str(form.get("ingredientes_excluidos", "")).split(",")
                    if t.strip()
                ],
                "alergenos": [
                    t.strip() for t in str(form.get("alergenos", "")).split(",") if t.strip()
                ],
                "utensilios_excluidos": [
                    t.strip() for t in str(form.get("utensilios_excluidos", "")).split(",")
                    if t.strip()
                ],
                "despensa": [
                    t.strip() for t in str(form.get("despensa", "")).split(",") if t.strip()
                ],
                "batchcooking": {"dias": [str(d) for d in form.getlist("dias_bc")]},
            }
            # Retira las claves antiguas del overlay para que manden los %.
            cambios.update(
                {
                    "peso_palatabilidad": None,
                    "peso_cena_ligera_simple": None,
                    "peso_favorita": None,
                    "peso_reutilizacion": None,
                    "peso_salud": None,
                    "peso_sobra": None,
                }
            )
        except (TypeError, ValueError):
            return RedirectResponse("/config?msg=Error: valores no válidos.", status_code=303)
        guardar_overlay(config_path, cambios)
        return RedirectResponse("/config?msg=Configuración guardada.", status_code=303)

    return app


app = crear_app()
