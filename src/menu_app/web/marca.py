"""Identidad de marca de la aplicacion (Fase 10).

Todo el diseño va aqui centralizado y EMBEBIDO (SVG + variables CSS), sin CDN ni
recursos externos, para que la web funcione offline y se empaquete limpia a .exe.

Nombre y eslogan son PROPUESTA: cambiarlos aqui reetiqueta toda la app.
"""

from __future__ import annotations

NOMBRE = "Sazón"
ESLOGAN = "Tu menú semanal sano, rico y al mejor precio"

# --- Paleta (mediterranea: verde fresco + terracota + crema/dorado) ---
VERDE = "#2f8f5b"        # primario
VERDE_OSCURO = "#1e5e3a"  # acento/texto sobre claro
TERRACOTA = "#e0603a"     # acento calido (tomate)
DORADO = "#e7a400"        # favoritos / detalles
CREMA = "#fbf8f2"         # fondo claro
CARBON = "#20302a"        # texto claro

# Variables CSS (design tokens) para claro y oscuro.
TOKENS_CSS = f"""
:root {{
  --verde: {VERDE};
  --verde-osc: {VERDE_OSCURO};
  --terracota: {TERRACOTA};
  --dorado: {DORADO};
  --bg: {CREMA};
  --surface: #ffffff;
  --border: #ece7dd;
  --text: {CARBON};
  --muted: #7b8079;
  --chip-bg: #eef4ee;
  --chip-text: {VERDE_OSCURO};
  --shadow: 0 2px 8px rgba(30,60,40,.08);
  --radio: 12px;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --verde: #46b377;
    --verde-osc: #8fd6ab;
    --bg: #14181a;
    --surface: #1e2427;
    --border: #2c3438;
    --text: #e8ede9;
    --muted: #9aa39c;
    --chip-bg: #26332c;
    --chip-text: #cfe6d0;
    --shadow: none;
  }}
}}
"""

# Simbolo (cuenco con hoja) — cuadrado, para favicon e icono de app.
ICONO_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="15" fill="{VERDE}"/>
<path d="M32 12c7 3 8 12 2 17-6-5-5-14-2-17z" fill="#bfe6cc"/>
<path d="M32 15c0 5 0 9-1 13" stroke="{VERDE_OSCURO}" stroke-width="1.4" fill="none"/>
<rect x="15" y="30" width="34" height="4" rx="2" fill="{CREMA}"/>
<path d="M17 34a15 15 0 0 0 30 0z" fill="{CREMA}"/>
<circle cx="32" cy="45" r="2.3" fill="{TERRACOTA}"/>
</svg>"""

# Logotipo horizontal (simbolo + nombre) en blanco, para la cabecera verde.
LOGO_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 190 48" role="img" aria-label="{NOMBRE}">
<rect x="2" y="6" width="36" height="36" rx="9" fill="rgba(255,255,255,.16)"/>
<path d="M20 12c4.6 2 5.2 8 1.3 11.2C17.4 20 18 14 20 12z" fill="#cfeed9"/>
<rect x="9" y="24" width="22" height="2.6" rx="1.3" fill="#fff"/>
<path d="M10.5 26.6a9.5 9.5 0 0 0 19 0z" fill="#fff"/>
<circle cx="20" cy="33.5" r="1.5" fill="{DORADO}"/>
<text x="48" y="32" font-family="Georgia, 'Times New Roman', serif" font-size="24"
 font-weight="700" fill="#fff" letter-spacing=".5">{NOMBRE}</text>
</svg>"""


def favicon_data_uri() -> str:
    """SVG del icono como data URI para <link rel=icon> (sin fichero externo)."""
    import urllib.parse

    return "data:image/svg+xml," + urllib.parse.quote(ICONO_SVG)
