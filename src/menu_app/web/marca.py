"""Identidad de marca de la aplicacion (Fase 10).

Todo el diseño va aqui centralizado y EMBEBIDO (SVG + variables CSS), sin CDN ni
recursos externos, para que la web funcione offline y se empaquete limpia a .exe.

Nombre y eslogan son PROPUESTA: cambiarlos aqui reetiqueta toda la app.
"""

from __future__ import annotations

NOMBRE = "Sazón"
ESLOGAN = "Tu menú semanal sano, rico y al mejor precio"

# --- Paleta (Lote 11: "Oliva y Mostaza", limpio/minimalista) ---
VERDE = "#4d5d3a"        # oliva primario (barra, acentos)
VERDE_OSCURO = "#3d4a2e"  # oliva oscuro (texto de acento)
TERRACOTA = "#b5482f"     # rojo/terracota (avisos, quitar)
DORADO = "#c9962e"        # mostaza (favoritos, indicador activo)
CREMA = "#fdfcf8"         # fondo claro
CARBON = "#2a2a1f"        # texto principal

# Verde vivo para acciones (generar, guardar, actualizar).
VERDE_ACCION = "#3f7a3a"
VERDE_ACCION_HOVER = "#4d9147"

# Variables CSS (design tokens) para claro y oscuro.
TOKENS_CSS = f"""
:root {{
  --verde: {VERDE};
  --barra: {VERDE};
  --verde-osc: {VERDE_OSCURO};
  --verde-accion: {VERDE_ACCION};
  --verde-accion-h: {VERDE_ACCION_HOVER};
  --terracota: {TERRACOTA};
  --dorado: {DORADO};
  --bg: {CREMA};
  --surface: #ffffff;
  --border: #eeead9;
  --text: {CARBON};
  --muted: #8f8a75;
  --chip-bg: #eef1e6;
  --chip-text: {VERDE_OSCURO};
  --sec-bg: #dde4d0;
  --sec-bg-h: #c9d4b3;
  --neutro-bg: #f1eee2;
  --neutro-bg-h: #e9e5d5;
  --fila-alt: #faf8f1;
  --hover-fila: #eef3e8;
  /* Tintes de columna de la tabla del menu (Lote 11). */
  --tinte-dia: #faf9f3;
  --tinte-com: #fdf9f0;
  --tinte-cen: #faf8fb;
  --tinte-com-h: #f8f0dd;
  --tinte-cen-h: #f2ecf4;
  --fila-nutri: #fbfaf6;
  --nota-bg: #f6f4ec;
  --plegar-h: #f8f6ee;
  --flecha-h: #f1eee0;
  --ico-bg: #f3f1e8;
  --shadow: 0 2px 8px rgba(60,74,46,.07);
  --radio: 12px;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --verde: #8fa06e;
    --barra: #313826;
    --verde-osc: #b7c2a2;
    --verde-accion: #5c9a55;
    --verde-accion-h: #6faa66;
    --bg: #17190f;
    --surface: #20241a;
    --border: #333827;
    --text: #e8e6da;
    --muted: #9c9885;
    --chip-bg: #2b3020;
    --chip-text: #cdd8bd;
    --sec-bg: #3a4230;
    --sec-bg-h: #47523a;
    --neutro-bg: #2b2c22;
    --neutro-bg-h: #34362a;
    --fila-alt: #1f2216;
    --hover-fila: #2a2f1e;
    --tinte-dia: #22251a;
    --tinte-com: #262316;
    --tinte-cen: #242028;
    --tinte-com-h: #322d1c;
    --tinte-cen-h: #302a35;
    --fila-nutri: #1f2216;
    --nota-bg: #2b2c22;
    --plegar-h: #2a2f1e;
    --flecha-h: #2a2f1e;
    --ico-bg: #2b2c22;
    --shadow: none;
  }}
}}
/* Toggle MANUAL de tema (#63): gana siempre al prefers-color-scheme del sistema. */
:root[data-theme="dark"] {{
  --barra: #313826;
  --verde: #8fa06e; --verde-osc: #b7c2a2; --verde-accion: #5c9a55;
  --verde-accion-h: #6faa66; --bg: #17190f; --surface: #20241a;
  --border: #333827; --text: #e8e6da; --muted: #9c9885; --chip-bg: #2b3020;
  --chip-text: #cdd8bd; --sec-bg: #3a4230; --sec-bg-h: #47523a;
  --neutro-bg: #2b2c22; --neutro-bg-h: #34362a; --fila-alt: #1f2216;
  --hover-fila: #2a2f1e;
  --tinte-dia: #22251a; --tinte-com: #262316; --tinte-cen: #242028;
  --tinte-com-h: #322d1c; --tinte-cen-h: #302a35; --fila-nutri: #1f2216;
  --nota-bg: #2b2c22; --plegar-h: #2a2f1e; --flecha-h: #2a2f1e;
  --ico-bg: #2b2c22; --shadow: none;
}}
:root[data-theme="light"] {{
  --barra: {VERDE};
  --verde: {VERDE}; --verde-osc: {VERDE_OSCURO}; --verde-accion: {VERDE_ACCION};
  --verde-accion-h: {VERDE_ACCION_HOVER}; --bg: {CREMA}; --surface: #ffffff;
  --border: #eeead9; --text: {CARBON}; --muted: #8f8a75; --chip-bg: #eef1e6;
  --chip-text: {VERDE_OSCURO}; --sec-bg: #dde4d0; --sec-bg-h: #c9d4b3;
  --neutro-bg: #f1eee2; --neutro-bg-h: #e9e5d5; --fila-alt: #faf8f1;
  --hover-fila: #eef3e8;
  --tinte-dia: #faf9f3; --tinte-com: #fdf9f0; --tinte-cen: #faf8fb;
  --tinte-com-h: #f8f0dd; --tinte-cen-h: #f2ecf4; --fila-nutri: #fbfaf6;
  --nota-bg: #f6f4ec; --plegar-h: #f8f6ee; --flecha-h: #f1eee0;
  --ico-bg: #f3f1e8; --shadow: 0 2px 8px rgba(60,74,46,.07);
}}
"""

# Script de arranque: aplica el tema guardado ANTES de pintar (evita parpadeo).
# Lote 11: el tema por defecto es CLARO (el aspecto de diseño); solo se sigue al
# tema del SO si el usuario elige "Sistema" en Configuración → Apariencia.
TEMA_SCRIPT = """<script>
(function(){
  var t = localStorage.getItem('sazon-tema') || 'light';
  if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
  // t === 'system': sin atributo -> sigue al prefers-color-scheme del SO.
})();
function alternarTema(){
  var actual = document.documentElement.getAttribute('data-theme') || 'light';
  var siguiente = actual === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', siguiente);
  localStorage.setItem('sazon-tema', siguiente);
}
</script>"""

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
