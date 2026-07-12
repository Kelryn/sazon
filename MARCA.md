# Sazón — guía de marca

Identidad visual de la aplicación (Fase 10). Todo va **embebido** (SVG + variables
CSS), sin CDN, para que funcione offline y se empaquete limpio al `.exe`.

## Nombre y voz
- **Nombre:** **Sazón** — evoca el *sabor* (la palatabilidad es un valor central de
  la app) y la cocina de casa; corto, cálido y español.
- **Eslogan:** *«Tu menú semanal sano, rico y al mejor precio.»*
- **Tono:** cercano, práctico y honesto. Habla de comer bien sin gastar de más.
  Nada de tecnicismos; el usuario ve claridad (precios reales, nutrientes por día).

> El nombre y el eslogan son una **propuesta**: se cambian en `web/marca.py`
> (`NOMBRE`, `ESLOGAN`) y se reetiqueta toda la app.

## Paleta
| Rol | Color | Uso |
|---|---|---|
| Verde primario | `#2f8f5b` | Cabecera, botones, acentos |
| Verde oscuro | `#1e5e3a` | Títulos de sección, degradado |
| Terracota | `#e0603a` | Acento cálido, avisos |
| Dorado | `#e7a400` | Favoritas ★, detalles |
| Crema | `#fbf8f2` | Fondo (claro) |
| Carbón | `#20302a` | Texto (claro) |

Se define como **design tokens** (variables CSS `--verde`, `--bg`, `--text`…) con
variantes automáticas para **modo claro y oscuro** (`web/marca.py` → `TOKENS_CSS`).

## Tipografía
- **Interfaz:** stack de sistema (`system-ui`), sin CDN, legible y rápido.
- **Logotipo:** lettering en serif (Georgia) dentro del SVG, para dar carácter sin
  depender de fuentes externas.

## Logo e icono
- **Símbolo:** un **cuenco con una hoja** — comida sana y de cuchara.
- **Logo horizontal** (`LOGO_SVG`): símbolo + palabra «Sazón» en blanco, para la
  cabecera verde.
- **Icono/favicon** (`ICONO_SVG`): el símbolo sobre fondo verde redondeado.
- **Icono del ejecutable:** `assets/icono.ico` (multi-tamaño), generado de forma
  determinista con Pillow (`generar_icono.py`), sin IA.

## Reglas de uso
- Mantener el aire alrededor del logo; no deformarlo ni recolorearlo.
- Un solo acento cálido (terracota o dorado) por bloque; el verde manda.
- Respetar el contraste en modo oscuro (los tokens ya lo resuelven).
- No introducir dependencias externas (fuentes/imagenes remotas): rompe el `.exe`.
