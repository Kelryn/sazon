"""Clasificador determinista del ROL de una receta en el menu.

Distingue el PLATO PRINCIPAL (comida/cena de verdad) de postres, desayunos/
meriendas y guarniciones/salsas. El menu de comidas principales debe elegir solo
'principal': asi no entran bizcochos, tortitas ni mermeladas como si fueran una
cena, y en los dias de batchcooking (dia laboral) se cumple el "plato unico sin
postre".

Combina el campo `categoria` del scraper (cuando es fiable) con palabras clave del
titulo, con una GUARDA DE SALADO para no marcar como postre los horneados salados
("pastel de carne", "tarta de puerros", "quiche" son principales; "tarta de
manzana", "pastel de chocolate" son postres).
"""

from __future__ import annotations

import sqlite3

from ..matching.normalizar import quitar_acentos

PRINCIPAL = "principal"
POSTRE = "postre"
DESAYUNO = "desayuno"
GUARNICION = "guarnicion"

# Postres casi inequivocos (no necesitan guarda).
_POSTRE_FUERTE = (
    "bizcocho", "galleta", "mousse", "flan", "helado", "cheesecake", "brownie",
    "cupcake", "magdalena", "muffin", "natilla", "tiramisu", "churro", "roscon",
    "turron", "macaron", "donut", "dona ", "cookie", "pudin", "pudding", "sorbete",
    "granizado", "profiterol", "torrija", "merengue", "alfajor", "polvoron",
    "arroz con leche", "crema catalana", "tocino de cielo", "leche frita", "coulant",
    "panna cotta", "tarta de queso", "pastel de queso", "rosquilla", "pestino",
    "marquesa", "trufa", "mermelada", "confitura", "compota", "glaseado", "frosting",
    "crema pastelera", "buñuelo", "bunuelo", "chocolate caliente", "petit four",
    "carrot cake", "red velvet", "cake ", "tartaleta", "financier", "clafoutis",
    "crumble", "mazapan", "yema de santa", "flan de", "postre",
)

# Horneados/dulces AMBIGUOS: postre salvo que el titulo lleve marca de salado.
_AMBIGUOS = ("tarta", "torta", "pastel", "pie", "bica", "coca dulce")
_SALADO = (
    "carne", "pollo", "pavo", "cerdo", "ternera", "pescado", "atun", "bonito",
    "bacalao", "merluza", "salmon", "gambas", "marisco", "verdura", "verduras",
    "patata", "puerro", "espinaca", "calabacin", "berenjena", "cebolla", "setas",
    "champinon", "jamon", "bacon", "chorizo", "morcilla", "queso azul", "espinacas",
    "salado", "salada", "espárrago", "esparrago", "tortilla", "acelga",
)

# Desayuno / merienda / bebidas.
_DESAYUNO = (
    "tostada", "tortita", "panqueque", "pancake", "gofre", "waffle", "granola",
    "porridge", "gachas", "smoothie", "batido", "crepe", "crep ", "creps", "crepes",
    "cafe con", "croissant", "napolitana", "cruasan", "poridge", "overnight oats",
    "bowl de avena", "pan de leche", "licuado", "zumo", "jugo de", "agua de",
    "agua fresca", "cafe ", "chocolate a la taza",
)

# Bases / ingredientes / guarniciones que no son un plato en si.
_GUARNICION = (
    "harina de", "harina casera", "masa para", "masa de", "masa quebrada",
    "salsa ", "alino", "aliño", "aderezo", "vinagreta", "sofrito", "majado",
    "caldo casero", "caldo de", "fondo de", "guarnicion", "condimento",
    "mantequilla de", "pan rallado", "picada de",
)

_CAT_POSTRE = {"postre", "postres", "reposteria"}
_CAT_DESAYUNO = {"desayuno", "merienda", "meriendas"}
_CAT_GUARNICION = {"acompañamiento", "acompanamiento", "salsa", "salsas", "aperitivo"}
_CAT_PRINCIPAL = {
    "plato principal", "principal", "cena", "comida", "dinner", "main course",
    "lunch", "supper", "mains",
}


def rol_receta(titulo: str | None, categoria: str | None = None) -> str:
    t = quitar_acentos(titulo or "")
    # Muchas fuentes prefijan "Receta de ..."; se quita para que las reglas por
    # inicio de titulo (guarniciones/bases) funcionen.
    for pref in ("receta de ", "receta "):
        if t.startswith(pref):
            t = t[len(pref):]
            break
    cat = quitar_acentos(categoria or "")
    es_salado = any(s in t for s in _SALADO)

    # 1) Palabras del titulo (mandan sobre la categoria, que a veces esta mal).
    if not es_salado:
        if any(p in t for p in _POSTRE_FUERTE):
            return POSTRE
        if any(a in t for a in _AMBIGUOS):
            return POSTRE
    if any(d in t for d in _DESAYUNO) and not es_salado:
        return DESAYUNO

    # 1b) Bases/guarniciones: solo si el titulo EMPIEZA por la marca, para no
    #     confundir "Pollo en salsa" (plato) con "Salsa de tomate" (base).
    if any(t.startswith(g) for g in _GUARNICION):
        return GUARNICION

    # 2) Categoria del scraper.
    if cat in _CAT_POSTRE:
        return POSTRE
    if cat in _CAT_DESAYUNO:
        return DESAYUNO
    if cat in _CAT_GUARNICION:
        return GUARNICION
    if cat in _CAT_PRINCIPAL:
        return PRINCIPAL

    # 3) Por defecto, principal (guisos, arroces, pastas, carnes, pescados,
    #    legumbres, ensaladas, sopas, entrantes salados...).
    return PRINCIPAL


def clasificar_roles(conn: sqlite3.Connection) -> dict[str, int]:
    filas = conn.execute("SELECT id, titulo, categoria FROM recetas").fetchall()
    conteo: dict[str, int] = {PRINCIPAL: 0, POSTRE: 0, DESAYUNO: 0, GUARNICION: 0}
    for f in filas:
        rol = rol_receta(f["titulo"], f["categoria"])
        conn.execute("UPDATE recetas SET rol = ? WHERE id = ?", (rol, f["id"]))
        conteo[rol] = conteo.get(rol, 0) + 1
    conn.commit()
    return conteo
