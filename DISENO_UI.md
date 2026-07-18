# Guía de diseño de la interfaz (Lote 11)

Este documento es la **fuente de verdad del diseño visual** de cada pantalla de
la app. Se construye pantalla por pantalla en entrevista con el usuario. Al
implementar la UI (sin CDN, todo CSS/HTML embebido para el `.exe`), respetar
exactamente lo aquí descrito.

## Principios globales

- **Paleta: Oliva y Mostaza**, estilo limpio / minimalista.
  - Verde oliva principal (barra de herramientas, acentos): `#4d5d3a`.
  - Verde oliva oscuro para texto de acento: `#3d4a2e`.
  - Mostaza (acento / indicador activo): `#c9962e`.
  - Fondo de la interfaz (crema): `#fdfcf8`.
  - Borde suave general: `#eeead9`.
  - Texto principal: `#2a2a1f`; texto secundario / apagado: `#8f8a75`;
    muy apagado: `#a8a08a` / `#b3ae9e`.
- **Sin unidades ni adornos innecesarios.** Números limpios; las unidades van en
  gris junto a la etiqueta, no repetidas en cada celda.
- **Hovers sutiles**, siempre un tono ligeramente distinto (más claro u oscuro)
  del fondo del propio elemento. Cada zona puede tener su matiz para
  diferenciarse, pero siempre discreto.
- **Modo ayuda (❓)**: botón por pantalla que superpone una capa temporal con
  recuadros verdes (`#4d5d3a`) sobre los elementos interactivos y globos oscuros
  explicando cada función. Se activa/desactiva con el mismo botón. El propio
  botón de ayuda no lleva globo. Textos de los globos **editables en un `.md`
  por pantalla** (no incrustados en código).
- El **selector de tema día/noche NO va en la barra de herramientas**; irá en la
  pantalla de Configuración.

---

## Pantalla: Menú semanal (`/`)

### Barra de herramientas (cabecera verde `#4d5d3a`, padding `12px 14px`)

- **Botones de navegación** (`Menú`, `Compra`, `Recetas`) pegados a la izquierda;
  el borde izquierdo de `Menú` coincide con el de `Generar plan` de debajo.
  - Texto en **bold** (700), blanco, 13px. Todos del **mismo tamaño**: 78×30 px,
    radio 7px, fondo transparente.
  - **Indicador de sección activa**: una **barrita corta** centrada bajo el texto
    (20×2 px, mostaza `#c9962e`, radio 1px) — igual que las barritas de las
    cabeceras de la tabla. NO una línea a todo el ancho.
  - **Hover** por sección, ligeramente más claro que el verde de la barra y de
    matiz distinto: Menú `#5a6e43`, Compra `#6b6539`, Recetas `#4f6a58`.
- **Logo + título "Sazón"** (hoja 🌿 en recuadro `#ffffff22` 24px + texto blanco
  700 16px) **centrados** en el hueco entre el último botón de navegación
  (Recetas) y el botón de ayuda.
- **Botón de ayuda ❓**: a la derecha del todo. Cuadrado 30×30, radio 7px, sin
  borde, icono `?` 16px en tono claro `#eef1e6`, fondo transparente (mismo verde
  de la barra). Hover ligeramente más claro `#5c6d48`.

### Fila de acciones (grid de 4 columnas `1fr 1.3fr 1.3fr 1.3fr`, igual que la tabla)

- **Sobre la columna Día**: par de botones que ocupan todo el ancho de esa
  columna:
  - `Generar plan`: se estira (`flex:1`), fondo verde pastel `#dde4d0`, texto
    `#3d4a2e` 600 12px, radio 7px, sin borde. Hover `#c9d4b3`.
  - `↺` (rehacer / generar alternativa): 29×29, radio 7px, **sin borde**, fondo
    apenas más oscuro que la interfaz `#f3f1e8`, icono `#4a4636`. Cierra el borde
    derecho de la columna Día. Hover `#c9d4b3` (el mismo que Generar plan).
  - Los dos botones van **separados** (no dentro de un mismo recuadro).
- **Selector de semana** sobre la columna Comida: `Semana N/M` centrado; flecha
  `◀` centrada sobre el borde Desayuno↔Comida y `▶` sobre el borde Comida↔Cena.
  Flechas 28×28, transparentes, glifo perfectamente centrado. Hover `#f1eee0`
  (beige ligeramente más oscuro que el fondo).

### Tabla del menú (tarjeta blanca, borde `#eeead9`, radio 10px)

- **4 columnas**: Día (`1fr`) · Desayuno · Comida · Cena (`1.3fr` cada una).
- **Cabecera sin fondo propio**: cada celda de cabecera toma el color de su
  columna. Etiquetas en mayúsculas, 11px, `#8f8a75`, 700, `letter-spacing .4px`,
  con una **barrita** debajo (20×2 px):
  - Día: fondo `#faf9f3`, barra negra `#111`.
  - Desayuno: fondo `#f8faf6`, barra verde apagado `#a8b593`.
  - Comida: fondo `#fdf9f0`, barra mostaza `#c9962e`.
  - Cena: fondo `#faf8fb`, barra morado apagado `#8a6f9c`.
- **Columna Día** (celdas de cuerpo): fondo `#faf9f3` (ligeramente más claro que
  la cabecera para diferenciar), nombre del día 13px 600, y debajo el **coste
  diario** en gris clarito `#b3ae9e` 10px.
- **Celdas de receta**: cada columna mantiene su tinte en reposo
  (Desayuno `#f8faf6`, Comida `#fdf9f0`, Cena `#faf8fb`), separadas por borde
  vertical `#eeead9` (sin divisores horizontales). Texto tierra oscuro (no azul).
  - Son **enlaces** a la ficha de receta; al pasar el cursor oscurecen su propio
    tinte de forma sutil (Desayuno `#eef3e8`, Comida `#f8f0dd`, Cena `#f2ecf4`).
  - **Sin sugerencia** → se muestra `–` con el **mismo fondo de la columna** (no
    cambia de color) y sin hover.
- El salmón/plato repetido NO se resalta: mismo fondo que el resto de su columna.

### Tabla de nutrientes (plegable, debajo del menú)

- Tarjeta blanca, borde `#eeead9`, radio 10px.
- **Cabecera plegable** "Nutrientes por persona y día" (12px, `#3d4a2e`, 700) con
  chevron `▴/▾` a la derecha. Tiene **hover** (`#f8f6ee`, chevron a `#5b5748`)
  para indicar que se puede plegar/desplegar. **Sin** el texto "(comida + cena)".
  - **Borde inferior leve** `#f1eee2` que la separa del encabezado de la tabla.
- **Tabla** (grid `1.7fr 1fr 1.15fr 0.7fr`):
  - Columnas: **Nutriente** (izquierda), **Total/día** (centrada),
    **Objetivo/día** (centrada, texto `#8f8a75`), **✓/✗** (centrada).
  - Encabezado con el **mismo formato que el del menú**: 11px, mayúsculas,
    `#8f8a75`, 700, `letter-spacing .4px`, **sin fondo**.
  - **Nombre del nutriente** con su **unidad en gris** `#a8a08a` y **sin
    paréntesis**: `Energía Kcal`, `Proteínas g`, etc. Sin unidades en el resto de
    columnas.
  - **Objetivo siempre como rango** `mín - máx` (p. ej. `28 - 48`; energía
    `595 - 805`; fibra sin tope `12 - —`).
  - Marca de cumplimiento: `✓` verde `#4d7a3a`, `✗` terracota `#b5482f`.
  - **Sin líneas divisorias**; filas con **color alterno muy suave** `#fbfaf6`.
- **Nota al pie**, fondo ligeramente más oscuro `#f6f4ec`, borde superior
  `#f1eee2`, texto 11px `#8f8a75`. **Editable en el `.md` de la pantalla.**
  - Contenido actual: objetivos escalados al % de energía que cubre el menú
    (comida + cena, reparto FEN/AESAN) según las kcal/día configuradas.

### Orden de nutrientes (del modelo, `_ORDEN_NUTRIENTES`)

Energía · Proteínas · Hidratos de Carbono · Grasas insaturadas · Grasas
saturadas · Azúcares · Sal · Fibra.

---

## Elementos comunes (aplican a TODAS las pantallas)

- **Títulos de tarjeta (franja)**: 15px, 700, verde `#3d4a2e`, con separador fino
  a todo el ancho debajo.
- **Cuadros de texto (`input`)**: fondo crema `#fdfcf8`, **borde ocre** 1px
  `#eeead9`, radio 8px. En **hover y foco**, el borde solo **cambia de color a
  verde** `#4d5d3a` (mismo grosor 1px, sin `outline` ni `box-shadow`: forzar
  `outline:none; box-shadow:none` con `!important` porque el host añade un anillo
  de foco grueso). Son `<input>`: forzar también fondo/borde con `!important`.
- **Botones de acción secundarios** (Nueva receta, Importar, etc.): verde pastel
  `#dde4d0`, texto `#3d4a2e`, hover `#c9d4b3`.
- **Botones con signo + / −**: el signo se dibuja como **SVG** (líneas
  `stroke="currentColor"`), NO como carácter de texto, porque los glifos `+`/`−`
  no quedan centrados verticalmente por métrica de fuente. Así quedan centrados
  vertical y horizontalmente en cualquier botón (raciones, filas de ingredientes,
  etc.).
- **Casillas de marcar** (`checkbox`): `appearance:none`, cuadrado blanco con
  borde `#cfcabb`, radio 4px; al marcar, **tic** oliva `#4d5d3a`; hover oscurece
  el fondo (`#efece0`).

## Barra de herramientas (común a TODAS las pantallas)

- **Formato idéntico** al de la pantalla Menú, en todas las pantallas.
- **Siempre visible**: la barra es *sticky* (`position:sticky; top:0`) y se
  mantiene arriba al desplazar la pantalla.
- Botones **sin borde** y fondo transparente. En el widget de maqueta hay que
  forzar `border:none !important; background:transparent !important` porque el
  host pinta un borde/hover por defecto en los `<button>`.
- Hover por sección (nunca un color único para todos): Menú `#5a6e43`,
  Compra `#6b6539`, Recetas `#4f6a58`; ayuda `#5c6d48`.
- **Sección activa**: barrita mostaza bajo el texto (ver Menú). En Detalle de
  receta la sección activa es **Recetas**.
- **Botón "Catálogo"**: 4º botón fijo de la barra en TODAS las pantallas (mismo
  patrón que los demás; hover `#5a6553`).
- **Pendiente**: el resto de secciones que hoy están en el `<nav>` del código
  (Valoraciones, Buscar, Sustituciones, Correcciones, Historial, Dashboard,
  Configuración) necesitan un hogar en la barra rediseñada (p. ej. un menú
  "más"/overflow). El selector de tema 🌓 se saca del nav y va a Configuración.

---

## Pantalla: Detalle de receta (`/receta/{id}`)

Barra de herramientas común (sticky), sección **Recetas** activa. Contenido en
tarjetas blancas (`#fff`, borde `#eeead9`, radio 12px).

### Tarjeta principal

- **Nombre de la receta** = **enlace a la fuente original** (título 22px 700
  `#2a2a1f`, hover a `#4d5d3a`). NO se muestra la línea "fuente:".
- **Tiempo de preparación** (`⏱ N min`, gris) **junto al nombre**.
- **Chips** debajo del nombre. El primero es **★ Favorita** con color distintivo
  suave (fondo `#faf1d8`, texto `#9d7a1b`); el resto son etiquetas/utensilios
  con el chip estándar (fondo `#eef1e6`, texto `#4d5d3a`). "Favorita" NO va
  junto al título.
- **"Valorar esta receta"**: **fila a todo el ancho** de la tarjeta (márgenes
  negativos para llegar a los bordes), con **borde fino arriba y abajo**
  (`#f1eee2`), un `›` a la derecha y **hover** `#f8f6ee`. Sin icono. Enlaza a la
  pantalla de valoración.
- **Selector de raciones**: recuadro pequeño **sin borde**, poco alto, fondo muy
  claro `#faf9f4`, que engloba la etiqueta "Raciones" + el número. A los lados
  del número, botones **circulares pequeños** (17px): **−** a la izquierda
  (círculo rojo suave, fondo `#f6e7e3`, signo `#b5482f`) y **+** a la derecha
  (círculo verde suave, fondo `#e9f0e0`, signo `#4d7a3a`). Discretos. Muestra las
  raciones por defecto de la receta y **recalcula todas las cantidades y el
  coste** al cambiarlo (JS por factor).
- **Tabla de ingredientes** (filas alternas `#fbfaf6`, sin divisores):
  - Columnas: **Ingrediente** (izquierda), **Cantidad** (centrada),
    **Producto Alcampo** (izquierda), **Coste usado** (centrada). Cabecera con el
    formato estándar (11px, mayúsculas, `#8f8a75`, 700).
  - **Producto Alcampo** = **botón** (no enlace subrayado): `padding` + radio 6px
    y **hover verde suave** `#eef3e8`. Incluye el precio por unidad en gris.
  - **Celdas vacías**: un **"–"** en gris `#c9c4ae`, **centrado horizontalmente**
    en su columna (en cualquier columna, sea cual sea su alineación normal).
- **Borde separador** (`#eeead9`) debajo de la tabla, antes del bloque "Coste de
  la receta".
- **Coste de la receta (N raciones): X € (Y €/ración)** + nota (editable en el
  `.md`) explicando qué es el "coste usado".

### Tarjeta de elaboración

- Foto de la receta (si la fuente la trae, `border-radius:10px`) + **franja
  "Elaboración"** + pasos numerados (`<ol>`, línea 1.7).

### Tarjeta "Recetas afines"

- Franja "Recetas afines". Cada receta es una **fila-botón a todo el ancho**
  (márgenes negativos a los bordes de la tarjeta), **sin subrayado**, texto
  alineado con la "R" de la franja, con el % de ingredientes en común a la
  derecha (gris) y **hover muy sutil** `#faf7f0`. Enlaza a la ficha de esa receta.

---

## Pantalla: Lista de la compra (`/compra`)

Barra de herramientas común (sticky), sección **Compra** activa. Contenido en
tarjetas blancas.

### Regla general de tarjetas

- **Bajo cada título de recuadro** (franja) va un **separador fino a todo el
  ancho** de la tarjeta (`#eeead9`, con márgenes negativos para llegar a los
  bordes).
- El título de la tarjeta va **centrado verticalmente** respecto a su meta
  (cuando la hay, p. ej. "2 semanas de menús" a la derecha).

### Tabla de la compra

- **Fila de encabezado** con **color de fondo a todo el ancho** (`#ece7d8`, de
  borde a borde). Etiquetas en **negro** (`#1c1c18`), mayúsculas, 11px, 700.
- **Columnas**: [casilla] · **Producto** · **Compra** · **Necesita** · **Sobra**
  · **€/ud** · [cambio de precio, sin encabezado] · **Total**.
  - **Producto**: enlace al producto en Alcampo. Su **hover cambia el fondo de
    TODA la fila** (verde suave `#e6efdd`), de borde a borde y del alto de la
    fila. El encabezado "Producto" y los nombres empiezan a la misma vertical que
    los títulos de sección.
  - **Compra / Necesita / Sobra**: cantidades, centradas ("Sobra" en gris
    `#8f8a75`).
  - **€/ud**: precio, centrado.
  - **Cambio de precio**: columna propia **sin encabezado**, a la derecha del
    precio: `↑ +N%` rojo `#b5482f` si sube, `↓ −N%` verde `#4d7a3a` si baja.
  - **Total**: **centrado** (encabezado y valores).
- **Títulos de sección/pasillo** (p. ej. "Legumbres y arroz"): mismo tamaño que
  los productos (12px) pero **negrita** y **gris claro** `#9b9683` (destacan
  menos que el encabezado negro). **Sin subtotal**. Debajo del título va el único
  **borde separador** (los productos ya no llevan borde entre filas).
- **Filas de producto alternas**: `#f7f4ea` y un tono muy ligeramente más oscuro
  `#f2efe3`, a todo el ancho. Todas las filas del **mismo alto** (36px). El "–"
  de celda vacía va centrado (regla global).
- **Casillas de marcar** (tachar al comprar): cuadrado **blanco** con borde
  `#cfcabb`, radio 4px; al marcar muestra un **tic** oliva `#4d5d3a`; hover
  oscurece ligeramente el fondo (`#efece0`). Estado persistido en el navegador.
- **TOTAL**: fila con borde superior grueso `#2b2b26`; el **ahorro/aumento total**
  va en la **misma columna que el cambio de precio** (`↓ −0,30 €` verde / `↑`
  rojo); el importe total, centrado en la columna Total.
- **Nota "Estos productos no se incluyen a la cesta:"** (parte fija **editable en
  el `.md`**) seguida de la lista de productos sin asignar, sobre fondo `#f6f4ec`.

### Tarjeta "Descargar"

- Botones (`<a>`, no cart-icons, **sin iconos**) **todos del mismo tamaño**
  (ancho fijo ~122px, misma altura), separados ~14px. Fondo `#f1eee2` (crema algo
  más oscuro que el fondo), hover `#e9e5d5`. Botones: Compra (PDF), Compra (CSV),
  Menú (PDF), Menú (CSV).

### Tarjeta "Enviar al carrito de Alcampo"

- Dos opciones con **casillas** del mismo estilo (blancas, tic al marcar, hover
  que oscurece): "Ajustar a la cantidad exacta si ya está en la cesta" y "Vaciar
  la cesta antes de empezar".
- Botón **"Enviar a Alcampo"** (texto exacto), **verde** `#3f7a3a`, hover a un
  verde más claro `#4d9147`. (Es un `<button>`: en la maqueta forzar sus estilos
  con `!important` porque el host pinta un fondo/hover por defecto.)
- **Sin** la aclaración larga del proceso ni el borde que la separaba: esa
  explicación se muestra desde el **modo ayuda ❓**, no fija en la tarjeta.

---

## Pantalla: Recetas (`/recetas`)

Barra de herramientas común (sticky), sección **Recetas** activa.

### Tarjeta "Recetas"

- Título "Recetas" (franja 15px) con botón **"Nueva receta"** (sin "+", con los
  colores de botón secundario) a la derecha, y separador fino debajo.
- **Buscador** por nombre: `input` de ancho normal (dentro de la tarjeta), con el
  estilo común de inputs.
- **Listado de recetas**: cada fila es **clicable entera** (enlace a
  `/receta/{id}`), con **hover que cambia el fondo** de toda la fila (verde suave
  `#eef3e8`). Sin botones Editar/Ver.
  - Columna izquierda: **nombre** de la receta (+ ★ mostaza `#c9962e` si es
    favorita), alineado con el **texto interior del buscador** (empieza a la
    altura de la "B" de "Buscar…", es decir `padding-left` extra ~12px respecto al
    borde de la tarjeta).
  - Columna derecha: **etiqueta** "propia"/"catálogo" en **columna propia sin
    encabezado**, centrada, gris `#8f8a75`.
- **Nota al pie** en gris muy claro `#bdb8a8` (no llama la atención):
  "Mostrando N recetas. X del catálogo y Y personales."

### Tarjeta "Importar receta por URL"

- `input` de URL (estilo común) + botón **"Importar"** (botón secundario) + nota
  explicativa.

---

## Pantalla: Editor de receta (`/recetas/nueva`, `/recetas/{id}/editar`)

Barra común (sticky), sección **Recetas** activa. Una sola tarjeta "Nueva
receta" / "Editar receta".

- **Título** (input, ocupa el ancho) + **Raciones** a su derecha como control
  compacto **− / número / +** (mismo estilo que la ficha de receta: recuadro
  `#faf9f4`, círculos rojo/verde con signo SVG).
- **Ingredientes** — filas con:
  - **Selector de ingrediente con buscador** (combobox): al abrir muestra un
    campo "Buscar ingrediente en Alcampo…" (ajustado al ancho del desplegable,
    con margen a ambos lados) y la lista filtrable de productos del catálogo. El
    desplegable tiene el mismo ancho que el recuadro del ingrediente.
  - **Cantidad** (recuadro estrecho, centrada) y **Unidad** (recuadro aún más
    estrecho, centrada) **pegadas a la derecha**; el ingrediente ocupa el resto.
    Texto centrado vertical y horizontalmente. Alto de fila 38px.
  - **− quitar fila** a la derecha; en la **última fila**, además **+ añadir** a
    su derecha. Se reserva el hueco del `+` (botón oculto) en todas las filas para
    que los anchos de ingrediente/cantidad/unidad sean idénticos en todas.
  - Botones − / + de fila: **sutiles en reposo** (fondo `#f4f2ec`, signo gris
    `#b3ae9e`); en hover el **−** se tiñe de **rojo** (fondo `#f7e4e0`, signo
    `#b5482f`) y el **+** de **verde** (fondo `#e7f0dd`, signo `#4d7a3a`).
- **Campo de preparación** (textarea): va **de borde a borde** de la tarjeta,
  **superpuesto** a los laterales del contenedor (`margin: -19px`, sin doble
  borde), **esquinas rectas**, borde del color de los separadores `#eeead9`,
  **sin fondo gris** (blanco), y **hover** a un tono ligeramente más oscuro
  `#f7f5ee`. Alto inicial de 2 filas y **autoexpandible** al escribir. Placeholder:
  "Escribir aquí el método de preparación de esta receta si es necesario".
- **Casillas**: **Batchcooking**, **Desayuno**, **Cena**, **Favorita** (sin
  estrella). *(Desayuno es un flag NUEVO: requiere columna `es_desayuno` +
  migración + lectura en el guardado + `cargar_receta`; pendiente de cablear en
  la fase de implementación.)*
- **Botones** finales **"Guardar"** (verde) y **"Eliminar"** (rojo suave, solo al
  editar), **mismo ancho y alto** (130px).
- **Sin** el texto explicativo inferior: su explicación (adaptada) va en el
  **modo ayuda ❓**.

---

## Pantalla: Catálogo (`/catalogo`)

Barra común (sticky). **Pendiente de decidir**: si "Catálogo" es un 4º botón fijo
de la barra de navegación (ahora mismo en la maqueta va como 4º botón, sección
activa aquí). Dos tarjetas.

### Tarjeta "Actualizar"

- Título **"Actualizar"** (antes "Descargar / actualizar catálogo").
- Línea con nº de productos en BD (negrita) + última actualización (gris).
- Etiqueta "Categorías a descargar / actualizar" + **casillas** de categorías
  (estilo común de checkbox).
- Dos **botones del mismo ancho y alto** (128px), lado a lado:
  - **"Actualizar"** (antes "Actualizar seleccionadas") — verde `#3f7a3a`.
  - **"Revisar"** (antes "Revisar datos anómalos") — **mucho menos llamativo**
    (fondo crema `#f4f2ec`, texto gris `#8f8a75`, hover `#ece9dd`).
- Márgenes iguales arriba/abajo de los botones (≈12px: categorías→botones y
  botones→borde inferior de la tarjeta). **Sin** la nota "Refresca precios…" (va
  al modo ayuda ❓).

### Tarjeta "Catálogo"

- Título **"Catálogo"** (antes "Ver y corregir el catálogo").
- Buscador (input común) + casilla **"Aptos"** (antes "solo aptos").
- **Tabla** de productos, columnas: Producto · Precio · Apto · Nutric. · (Editar).
  - **Encabezado**: fila del **mismo alto** que las de datos, **fondo gris ligero**
    `#f2f0ea`, etiquetas gris `#6b6754`, con **borde inferior fino** `#e4e0d2`.
  - Filas alternas (`#faf8f1`), "Apto" ✓ en verde `#4d7a3a`, botón **Editar**
    (secundario) por fila.
- **Paginación** (◀ · Página X/Y (N productos) · ▶) **centrada horizontalmente**;
  flechas con estilo de botón neutro.

---

## Pantalla: Valoraciones — lista (`/valoraciones`)

Se accede desde el enlace **"Valorar esta receta"** de la ficha de cada receta y
(en el nav completo) desde "Valoraciones". Barra común. Dos tarjetas:

- **"Valorar"** (antes "Recetas por valorar"): cola de recetas cocinadas esta
  semana o la anterior sin valorar. Cada una es una **fila clicable** (hover de
  fondo `#eef3e8`) que lleva a su formulario, con "valorar ›" a la derecha. **Sin**
  la nota "Cocinadas esta semana o la anterior…" (va al modo ayuda ❓). **Sin**
  bordes separadores entre filas.
- **"Valoraciones"** (antes "Ya valoradas (re-valorar)"): buscador (input común +
  botón "Buscar") y listado de recetas ya valoradas, cada fila con la **media ★**
  mostaza y el nº de baremos. Filas clicables (re-valorar), **sin** bordes
  separadores.

---

## Pantalla: Valoraciones — formulario (`/valoraciones/{id}`)

Barra común. Una tarjeta con el **título** de la receta y separador.

- **8 baremos** (uno por fila, con borde inferior fino entre filas): Sabor ·
  Frescura (más de verano ↔ invierno) · Sentó bien · Saciedad · Facilidad de
  preparación · ¿Se repetiría? · Relación calidad/precio · Apetecible en
  frío/tupper. Cada uno se valora con **estrellas 1–5 interactivas** (en el
  código eran `<select>`; en el rediseño son estrellas clicables):
  - Reposo/seleccionado: estrellas hasta el valor en **mostaza** `#c9962e`, resto
    gris `#dcd7c6`.
  - **Hover**: hasta la estrella señalada en **dorado más claro** `#e3c264` y con
    un ligero `scale(1.12)` (preview).
  - Clic fija el valor.
- **"Ingredientes que más te gustaron"** y **"¿Algo del método de preparación?"**:
  ya NO son textareas libres, sino **filas de selector desplegable** (combobox)
  que eligen entre opciones existentes (ingredientes = los de la receta; métodos =
  catálogo por definir), cada fila con **− (quitar)** y **+ (añadir otra)** a su
  derecha (mismo estilo sutil de botones ± que el editor). *Pendiente en el
  roadmap: definir/curar las listas de opciones y afinar la UX.*
- Botón final **"Guardar valoración"** (verde).

---

<!-- Pantallas pendientes de revisar: Buscar · Sustituciones ·
Correcciones de matching · Historial · Dashboard · Configuración. -->
