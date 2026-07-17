"""Exportacion del menu y la lista de la compra a CSV y PDF (Fase 7).

- CSV: filas planas, para abrir en Excel/LibreOffice.
- PDF: documento imprimible (fpdf2, pura Python -> empaqueta limpio a .exe).

Todo se genera EN MEMORIA (bytes) para servirlo como descarga desde la web sin
escribir ficheros temporales.
"""

from __future__ import annotations

import csv
import io

from fpdf import FPDF

from .compra import Compra
from .planes import asignar_dias

_DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
_NOMBRE_DIA = {
    "lun": "Lunes", "mar": "Martes", "mie": "Miercoles", "jue": "Jueves",
    "vie": "Viernes", "sab": "Sabado", "dom": "Domingo",
}


def _titulo(datos: dict, rid: str) -> str:
    return (datos.get("recetas_info", {}).get(rid, {}) or {}).get("titulo", rid)


def menu_a_csv(semanas: dict[int, dict]) -> bytes:
    """CSV del plan completo: una fila por (semana, dia, franja, receta)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Semana", "Dia", "Franja", "Receta", "Batchcooking"])
    for semana in sorted(semanas):
        datos = semanas[semana]
        if not datos.get("factible"):
            continue
        for dia, comida, cena, es_bc in asignar_dias(datos, _DIAS):
            nombre = _NOMBRE_DIA.get(dia, dia)
            if comida:
                w.writerow([semana, nombre, "Comida", _titulo(datos, comida), "Si" if es_bc else "No"])
            if cena:
                w.writerow([semana, nombre, "Cena", _titulo(datos, cena), "No"])
    return buf.getvalue().encode("utf-8-sig")


def compra_a_csv(compra: Compra) -> bytes:
    """CSV de la lista de la compra (con pasillo, unidades, precio, total)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Pasillo", "Producto", "Unidades", "Cantidad necesaria", "€/ud", "Total €", "Enlace"])
    for pasillo, lineas in compra.por_pasillo().items():
        for linea in lineas:
            w.writerow([
                pasillo, linea.nombre, linea.unidades, linea.cantidad_legible,
                f"{linea.precio_unidad:.2f}" if linea.precio_unidad is not None else "",
                f"{linea.total:.2f}" if linea.total is not None else "", linea.url or "",
            ])
    w.writerow([])
    w.writerow(["", "", "", "", "", f"TOTAL {compra.total:.2f}", ""])
    return buf.getvalue().encode("utf-8-sig")


def _pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def menu_a_pdf(semanas: dict[int, dict]) -> bytes:
    """PDF del plan de menus (una tabla por semana)."""
    pdf = _pdf()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Plan de menus", new_x="LMARGIN", new_y="NEXT")
    for semana in sorted(semanas):
        datos = semanas[semana]
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Semana {semana}", new_x="LMARGIN", new_y="NEXT")
        if not datos.get("factible"):
            pdf.set_font("Helvetica", "I", 10)
            pdf.cell(0, 6, "(sin menu factible esta semana)", new_x="LMARGIN", new_y="NEXT")
            continue
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 7, "Dia", border=1)
        pdf.cell(80, 7, "Comida", border=1)
        pdf.cell(80, 7, "Cena", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for dia, comida, cena, es_bc in asignar_dias(datos, _DIAS):
            etiqueta = _NOMBRE_DIA.get(dia, dia) + (" *" if es_bc else "")
            pdf.cell(30, 7, etiqueta, border=1)
            pdf.cell(80, 7, _ascii(_titulo(datos, comida))[:46] if comida else "-", border=1)
            pdf.cell(80, 7, _ascii(_titulo(datos, cena))[:46] if cena else "-", border=1,
                     new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 6, f"Coste semana: {datos.get('coste_total', 0):.2f} EUR   "
                 "(* = dia batchcooking, plato unico)", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def compra_a_pdf(compra: Compra) -> bytes:
    """PDF de la lista de la compra agrupada por pasillo."""
    pdf = _pdf()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Lista de la compra", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, f"{compra.semanas} semana(s) de menus - Total {compra.total:.2f} EUR",
             new_x="LMARGIN", new_y="NEXT")
    for pasillo, lineas in compra.por_pasillo().items():
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _ascii(pasillo), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for linea in lineas:
            precio = f"{linea.total:.2f} EUR" if linea.total is not None else ""
            pdf.cell(12, 6, f"{linea.unidades}x", border="B")
            pdf.cell(150, 6, _ascii(linea.nombre)[:70], border="B")
            pdf.cell(28, 6, precio, border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def _ascii(texto: str) -> str:
    """fpdf con fuentes core solo admite latin-1; se sustituyen los no representables."""
    return (texto or "").encode("latin-1", "replace").decode("latin-1")
