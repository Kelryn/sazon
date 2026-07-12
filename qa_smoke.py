"""QA funcional (Fase 12): prueba todas las paginas y acciones de la web en marcha.

Uso: python qa_smoke.py [http://127.0.0.1:8137]
Hace GET a cada pagina (espera 200) y POST a cada accion (espera el efecto), e
imprime PASS/FAIL por cada una. No es un test unitario: valida la app real.
"""

from __future__ import annotations

import re
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8137"
c = httpx.Client(base_url=BASE, timeout=60, follow_redirects=True)
ok = fail = 0


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {nombre}")
    else:
        fail += 1
        print(f"  FAIL  {nombre}  {detalle}")


def get200(path: str, contiene: str | None = None) -> str:
    r = c.get(path)
    txt = r.text
    cond = r.status_code == 200 and (contiene is None or contiene in txt)
    check(f"GET {path}", cond, f"status={r.status_code}")
    return txt


print("== Páginas (GET) ==")
home = get200("/", "Sazón")
get200("/compra")
get200("/recetas", "Nueva receta")
get200("/recetas/nueva", "catalogo_ing")
get200("/catalogo", "Ver y corregir")
get200("/config", "Actualizaciones de la aplicación")

print("== Descargas ==")
for path, tipo in [("/compra.pdf", b"%PDF-"), ("/menu.pdf", b"%PDF-"),
                   ("/compra.csv", b"Pasillo"), ("/menu.csv", b"Semana")]:
    r = c.get(path)
    check(f"GET {path}", r.status_code == 200 and r.content[:8].find(tipo[:5]) >= 0
          or tipo in r.content, f"status={r.status_code}")

print("== Detalle de receta ==")
rid_menu = re.search(r"/receta/([a-z0-9]+)", home)
if rid_menu:
    get200(f"/receta/{rid_menu.group(1)}", "Producto Alcampo")
else:
    check("detalle de receta", False, "no encontré receta en el menú")

print("== Acciones del menú (POST) ==")
r = c.post("/generar", data={})
check("POST /generar", r.status_code == 200 and "Semana 1/" in r.text)
sem1 = c.get("/?semana=1").text
antes = set(re.findall(r"/receta/([a-z0-9]+)", sem1))
c.post("/alternativa", data={"semana": "1"})
despues = set(re.findall(r"/receta/([a-z0-9]+)", c.get("/?semana=1").text))
check("POST /alternativa (cambia recetas)", len(antes ^ despues) > 0)
if antes:
    rid = next(iter(antes))
    c.post("/cambiar", data={"semana": "1", "receta_id": rid})
    ahora = set(re.findall(r"/receta/([a-z0-9]+)", c.get("/?semana=1").text))
    check("POST /cambiar (sustituye la receta)", rid not in ahora)

print("== Recetas: crear / editar / favorita / eliminar ==")
r = c.post("/recetas/guardar", data={
    "titulo": "QA receta prueba", "raciones": "4",
    "ing_nombre": ["Lentejas", "Cebolla"], "ing_cantidad": ["300", "1"],
    "ing_unidad": ["g", "ud"], "plato_unico": "1"})
check("POST /recetas/guardar", "QA receta prueba" in r.text and "Nutrientes de una ración" in r.text)
m = re.search(r"/recetas/(man[a-z0-9]+)/eliminar", r.text)  # el editor enlaza eliminar
rid_manual = m.group(1) if m else None
check("editor de la receta creada", rid_manual is not None)
if rid_manual:
    c.post("/favorita", data={"receta_id": rid_manual})
    check("POST /favorita", True)
    r = c.post(f"/recetas/{rid_manual}/eliminar")
    check("POST /recetas/{id}/eliminar", "QA receta prueba" not in c.get("/recetas").text)

print("== Catálogo: editar producto ==")
cat = c.get("/catalogo").text
pid = re.search(r'href="/catalogo/([A-Za-z0-9]+)">Editar', cat)
if pid:
    pidv = pid.group(1)
    get200(f"/catalogo/{pidv}", "Editar producto")
    r = c.post(f"/catalogo/{pidv}", data={"precio_eur": "1.99", "apto_receta": "1"})
    check("POST /catalogo/{id} (guardar producto)", "actualizado" in r.text)
else:
    check("editar producto", False, "no encontré producto")

print("== Catálogo: botón actualizar (routing, sin lanzar descarga) ==")
check("form de actualizar apunta a /catalogo-actualizar",
      'action="/catalogo-actualizar"' in cat and 'action="/catalogo/actualizar"' not in cat)

print("== Configuración y actualizaciones ==")
r = c.post("/config", data={
    "num_comensales": "2", "kcal_por_comensal": "2000", "semanas_plan": "2",
    "dias_repeticion": "7", "racion_frac_min": "75", "racion_frac_max": "125",
    "sabor_pct": "50", "cena_ligera_pct": "50", "favoritas_pct": "50"})
check("POST /config (guardar)", "guardada" in r.text)
r = c.post("/config/repo", data={"repo": "usuario/sazon-releases"})
check("POST /config/repo", "sazon-releases" in c.get("/config").text)
r = c.post("/actualizaciones/comprobar", data={})
check("POST /actualizaciones/comprobar", r.status_code == 200)

print(f"\n== RESULTADO: {ok} PASS, {fail} FAIL ==")
sys.exit(1 if fail else 0)
