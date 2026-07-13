# Plan del proyecto (roadmap)

Estado y hoja de ruta de **Sazón** (antes «menu-app» / «Menu + Alcampo»). Refleja el
**pivote a motor 100% determinista sin APIs de IA** (decisión del usuario: el espíritu de
la app es el ahorro).

## Estado actual (2026-07-12)

- **Versión publicada:** `0.2.0` — repo público **[github.com/Kelryn/sazon](https://github.com/Kelryn/sazon)**,
  Release **v0.2.0** con `Sazon.exe`. El módulo de actualización se comprueba contra ese
  repo (verificado: desde 0.1.0 detecta la 0.2.0; desde 0.2.0 dice «al día»).
- **A partir de ahora, cada versión se sube a GitHub** (petición del usuario, para usar el
  módulo de actualización): subir `version.py`, `git tag vX.Y.Z`, `push` → el workflow
  compila `.exe` + instalador y publica la Release automáticamente.
- **Corpus:** 4263 recetas (ES + IT + GR mediterráneas), ~48% batchcooking, 100% con
  `cocina` española/mediterránea contada para el mínimo local. Pool utilizable ~869.
- **Matching:** ~95,6% ponderado por uso (88% de ingredientes distintos).
- **Fases 0–12 completadas.** Pendiente = estudios documentados aún sin implementar
  (secciones B, D, I) y extensiones de la Fase 9 (micronutrientes, estacionalidad).

## Fases completadas

| Fase | Qué | Estado |
|---|---|---|
| 0 | Descubrimiento de la API interna de Alcampo (OSP) | ✅ (ver DISCOVERY.md) |
| 1 | Ingesta del catálogo → CSV/SQLite (`AlcampoClient`) | ✅ |
| 2 | Almacenamiento + normalización + clasificación `apto_receta` + enriquecimiento nutricional (`bop`) | ✅ |
| 2b | **Nutrición estimada para frescos** (fruta/verdura/carne/pescado/huevo) desde USDA FoodData Central + BEDCA; columna `fuente_nutricion` ('bop'\|'estimada'); especias excluidas. Cobertura 86% | ✅ |
| 3 | Ingesta de recetas (ES+EN, recipe-scrapers) + **crawler BFS** por recetas relacionadas + **corpus mediterráneo ES/IT/GR** (`--mediterranea`, ver E); medidas a métrico | ✅ **4263 recetas** (ES + italianas + griegas) |
| 4 | Matching ingrediente→producto **determinista** (índice invertido + cobertura de tokens con stem de plurales + glosario EN/LatAm + quita marca en mayúsculas + alternativas "X o Y" + frases/erratas y sinónimos LatAm añadidos por el usuario) | ✅ **~95,6% ponderado por uso** (88% de ingr. distintos; el resto son exóticos que Alcampo no vende — ver `ingredientes_sin_match.md`) |
| 4b | **Alcohol de cocina** en el catálogo (vino, jerez, brandy, ron, cerveza, cava… `apto` como excepción) + **regla all-ingredients-match**: se excluye la receta si le falta cualquier ingrediente NO opcional en Alcampo | ✅ |
| 5 | Motor de menú determinista: bandas de nutrientes (EFSA/OMS, **suelo de proteína**, fibra=suelo **blando** por falta de dato), coste+nutrición reales, palatabilidad bayesiana, **solver MILP (PuLP)**, ≥50% españolas, **rol de plato** (solo principales), **fracción de ingesta** (comida+cena≈65% del día) | ✅ **menú real factible** ~90 €/sem (2 pers) |

## Pendiente / hoja de ruta

### A) Módulo de recetas manuales + favoritas  ✅ *(backend hecho; falta el formulario UI)*
Permitir al usuario **añadir recetas a mano** y marcar **favoritas** para que se usen
preferentemente, sin saltarse coste ni macronutrientes.

- **Entrada**: nombre de la receta, raciones, y lista de ingredientes con cantidad y
  unidad (p.ej. "200 g de lentejas", "2 huevos"). Reutiliza el parser de ingredientes
  de la Fase 3 (cantidad/unidad/nombre + conversión a métrico).
- **Almacenamiento**: en las mismas tablas `recetas` / `receta_ingredientes`, con
  `fuente = 'manual'` y una columna nueva `es_favorita` (bool). Se cuentan como
  españolas por defecto para el mínimo de cocina local.
- **Favoritas en el solver**: bonus fuerte de palatabilidad (`peso_favorita`) para que
  entren preferentemente. **No** son obligatorias: siguen sujetas a las bandas de
  nutrientes y al coste; si una favorita hiciera inviable la nutrición o dispara el
  coste, el solver puede no usarla (o se puede forzar un mínimo configurable de
  comidas favoritas por semana, `favoritas_min`).
- **Interfaz**: formulario en la UI (Fase 6) — nombre + filas de ingredientes + casilla
  "favorita". Backend: función `añadir_receta_manual(...)` + `RecetaRepository`.
- **Config**: aprovecha `recetas_favoritas[]` / `recetas_excluidas[]` ya previstos.

### B) Penalización de alimentos ultraprocesados  *(NUEVO — petición usuario)*
Uno de los objetivos es **facilitar una dieta más sana**, así que hay que **reducir la
probabilidad** de que entren en el menú alimentos ultraprocesados.

- **Estudio / clasificación del grado de procesado** (aproximación NOVA):
  - **NOVA 1** (sin procesar/mínimamente): fruta, verdura, carne/pescado fresco, huevo,
    legumbre seca, arroz… (muchos ya marcados con `fuente_nutricion='estimada'`).
  - **NOVA 4** (ultraprocesado): productos con lista de ingredientes larga, aditivos
    (números E), azúcares/grasas/sales añadidas, o de categorías como bollería,
    golosinas, precocinados, refrescos (varias ya excluidas por `apto_receta`).
  - **Señales para puntuar** (deterministas, sin IA): (1) nº de ingredientes y presencia
    de aditivos/E-números en el campo `ingredientes` del `bop`; (2) azúcares/grasa
    saturada/sal por 100 g altos; (3) categoría/subcategoría; (4) si existe, el grupo
    `nova` de Open Food Facts. Resultado: `nivel_procesado` (1-4) por producto.
- **Efecto en el motor**: 
  - Penalizar en el objetivo del MILP los productos/recetas con alto procesado
    (`peso_ultraprocesado`), para que a igualdad de coste/nutrición se prefieran los
    menos procesados — reduce su probabilidad sin prohibirlos.
  - Opción de **tope semanal** de raciones NOVA-4 (`max_ultraprocesado_semana`), en línea
    con el `max_nova4_semana` ya previsto en la config avanzada del plan original.
- **Fuentes**: heurística NOVA (Monteiro et al.) + composición USDA/BEDCA + ingredientes
  de Alcampo. Todo determinista y offline.

### C) Batchcooking (cocinar en tanda) + días laborales  *(NUEVO — petición usuario)*
Dividir el catálogo entre recetas **óptimas para batchcooking** y el resto, para poder
marcar días concretos como "batchcooking" y que ese día se cocine en tanda.

- **Clasificador determinista** *(ya construido)*: `optimizacion/batchcooking.py`
  (`es_batchcooking(titulo, categoria, cocina)`), por palabras clave (guisos, legumbres,
  arroces, sopas/cremas, asados, pasta al horno, currys, proteína en salsa, caldos y
  **ensaladas** —se preparan la víspera con el aliño aparte— vs. plancha, frituras, crudos).
  Columna `recetas.es_batchcooking` +
  comando `menu-app-clasificar-batchcooking` (reporta el reparto). Estado actual del corpus:
  **~48% batchcooking** (tras ampliar con el corpus mediterráneo), mayoría españolas.
- **Objetivo de composición**: que **~50% del corpus** sea batchcooking, y **de esas ≥50%
  españolas** (esto último ya se cumple con holgura). El resto del corpus son mayormente
  postres/ensaladas/frituras que *no* son batchcooking; para subir la cuota a 50% hay que
  **sembrar el crawler con más guisos/legumbres/arroces** (categorías de cocina de cuchara),
  NO reetiquetar postres. → tarea de corpus (Fase 3), monitorizada por el comando.
- **Selección por día** *(pendiente — requiere modelar días en el solver)*: hoy el menú es
  una lista plana de N comidas. Se añadirá estructura por día: cada día podrá marcarse como
  `batchcooking`. Ya está el cimiento en el solver (`RecetaOpt.es_batchcooking` +
  `optimizar(solo_batchcooking=True)` y `menu-app-generar-menu --batchcooking`, que
  restringe TODO el menú al catálogo batchcooking). Falta el modelo por día para mezclar
  días batchcooking y no-batchcooking en la misma semana.
- **Día batchcooking = día LABORAL** ⇒ reglas de ese día:
  - **Plato único** (una sola receta, cocinada en tanda y repartida en raciones/tuppers),
    para minimizar el nº de platos y facilitar transporte e ingesta en la oficina.
  - **Sin postre** (se excluyen recetas de categoría postre ese día).
  - En días NO batchcooking (fin de semana / no laboral) se elige del catálogo completo y se
    puede incluir postre / más de un plato.
  - Requiere además clasificar recetas como **postre vs plato** (categoría del scraper o
    heurística de palabras) — pendiente, ligado al modelo por día.
- **Config prevista**: sección `batchcooking:` con los días marcados como laborales/tanda
  (p.ej. `dias_laborales: [lun,mar,mie,jue,vie]`) y `fraccion_batchcooking_espanolas_min: 0.5`.

### D) Añadir la compra automáticamente al carrito de Alcampo  ✅ *(petición usuario — PROTOTIPO VALIDADO)*

**Validado de punta a punta (2026-07-12):** `menu-app-carrito --confirmar` añade la compra
completa del plan al carrito real de Alcampo (probado: 30/31, 1 agotado, 153 €). Playwright
**asíncrono**: tras el login (autodetección por "Mi cuenta"/ausencia de "Iniciar sesión", sin
ENTER) abre **una pestaña por producto y las añade TODAS en paralelo** (`asyncio.gather`, por
defecto sin tope — el anti-bot lo aguanta), sube cantidades con el stepper
"Aumentar la cantidad de {nombre}", salta agotados (aria-disabled), y al terminar abre `/basket`
y cierra las pestañas de producto dejando la ventana abierta para pagar. Sesión y contraseña
SIEMPRE del usuario (perfil persistente; la app nunca ve la contraseña). Pendiente: integrar
como botón "Enviar al carrito de Alcampo" en la web/.exe. Detalles y hallazgos abajo.

### D-bis) Estudio original *(referencia)*
Objetivo: que la app coja la lista de la compra y **añada los productos a la cesta**
de compraonline.alcampo.es sin intervención manual.

- **Vías posibles** (a estudiar, de menos a más frágil):
  1. **API interna OSP con sesión**: la web usa la API de Ocado Smart Platform; añadir al
     carrito es un `POST` autenticado (cookies/token de la sesión del usuario). Habría que
     estudiar los endpoints del carrito en DevTools (igual que se hizo en DISCOVERY.md) y
     reutilizar la sesión iniciada del navegador. Riesgo: endpoints no documentados,
     protección anti-bot (Akamai), y ToS de Alcampo.
  2. **Automatización de navegador** (Playwright ya es dependencia opcional): abrir la web
     con el perfil del usuario ya logueado e ir producto a producto pulsando "añadir".
     Más lento pero más robusto frente a cambios de API; mismo riesgo anti-bot/ToS.
  3. **Enlaces profundos** (lo que ya hay): el ticket enlaza cada producto a su página,
     y el usuario pulsa "añadir" — 1 clic por producto, sin riesgo.
- **Decisiones previas**: revisar los Términos de Servicio de Alcampo sobre automatización;
  la sesión/credenciales SIEMPRE del lado del usuario (la app nunca guarda la contraseña;
  en todo caso reutiliza la sesión del navegador). Empezar con un prototipo Playwright
  sobre 2-3 productos para medir viabilidad y fricción anti-bot.

**Estudio iniciado (2026-07-12):**
- **Ventaja de partida**: ya tenemos el `retailerProductId` de cada producto del menú (en la
  BD) y las **unidades a comprar** (módulo `compra.py`). Eso es justo lo que necesita
  cualquier API de carrito.
- **Vía 1 — API OSP del carrito (a investigar en DevTools)**: al añadir un producto en
  compraonline.alcampo.es se dispara una petición autenticada (probablemente
  `POST/PUT .../trolley|basket/items` con `{retailerProductId, quantity}` y cookies de sesión
  Akamai). Plan: capturar esas peticiones logueado, replicarlas con `httpx` **reutilizando
  las cookies del navegador del usuario** (nunca la contraseña). Riesgo: endpoints no
  documentados y protección anti-bot.
- **Vía 2 — Playwright (más robusta ante cambios de API)**: abrir el navegador con el perfil
  del usuario ya logueado y, por cada línea de la compra, ir a su URL y pulsar "añadir".
  Playwright ya está disponible en el entorno. Más lento pero resistente.
- **Vía 3 — semiautomática (la de hoy)**: el ticket enlaza cada producto; el usuario añade
  con 1 clic. Sin riesgo; sirve de respaldo.
- **Siguiente paso concreto**: prototipo que, a partir de la lista de la compra, abra en el
  navegador logueado cada producto y confirme que se puede añadir (Vía 2), y en paralelo
  capturar el endpoint del carrito (Vía 1) para decidir cuál es más fiable. **Requiere
  sesión iniciada del usuario y su visto bueno explícito antes de tocar el carrito.**

**Prototipo construido (2026-07-12):** paquete `menu_app/carrito/` + CLI `menu-app-carrito`.
- **Diseño**: contexto Playwright **persistente** en `%LOCALAPPDATA%\Sazon\navegador_alcampo`
  → el usuario inicia sesión UNA vez, a mano, en la ventana real de Alcampo (la app **nunca**
  ve ni guarda la contraseña). Por cada `LineaCompra` abre la ficha y pulsa "Añadir" subiendo
  a las `unidades` pedidas. En paralelo captura las peticiones POST/PUT/PATCH al carrito
  (`/trolley|/basket|/cart`) para diseñar la Vía 1/API en el futuro.
- **Seguridad**: **DRY-RUN por defecto** (solo comprueba que cada ficha tiene botón de añadir,
  no toca el carrito). Añadir de verdad exige `--confirmar` (visto bueno explícito). UA de
  Chrome real + `--disable-blink-features=AutomationControlled`. Playwright es extra opcional.
- **Uso**: `uv sync --extra playwright && uv run playwright install chromium`; luego
  `menu-app-carrito` (dry-run) o `menu-app-carrito --confirmar` (añade). `--reporte r.json`
  guarda el resultado + endpoints capturados.
- **Hallazgo (anti-bot)**: en modo **headless y sin sesión**, CloudFront/Akamai responde
  «The request could not be satisfied» (bloqueo). Confirma que el flujo **debe ir con ventana
  (headed) y sesión real del usuario** — una sesión humana e iniciada se considera legítima
  (igual que `ingesta/playwright_fallback.py`). El código de navegador arranca, navega y
  sondea selectores sin errores; los **selectores de "Añadir"/"+" son best-effort con varias
  alternativas** y hay que **validarlos contra el DOM logueado real** en una ejecución
  supervisada con el usuario (queda como siguiente paso antes de integrarlo en la web/.exe).

### E) Ampliar el corpus con cocina italiana y griega  ✅ *(petición usuario — HECHO)*
**Realizado (2026-07-12):** ingeridas recetas mediterráneas ES/IT/GR con el flag
`menu-app-ingestar-recetas --mediterranea` (+ `--paginas-categoria`), sembrando categorías
de cuchara y búsquedas mediterráneas (risotto, carbonara, moussaka, tzatziki, souvlaki…).
Corpus 1103 → **4263 recetas**; pool utilizable ~166 → **~869**; matching ~95,6% ponderado.

Motivo: los ingredientes de la cocina española, **italiana y griega** están casi todos en
Alcampo (pasta, arroz, aceite de oliva, tomate, queso feta, aceitunas, legumbres, pescado,
**vino de cocina**…). Ampliar el corpus a estas tres cocinas mediterráneas hace que la
regla *all-ingredients-match* excluya muy pocas recetas, y da variedad sin ingredientes
exóticos que no se venden.
- **Qué hacer**: añadir semillas de crawl de fuentes italianas y griegas soportadas por
  `recipe-scrapers` (p.ej. italianas: giallozafferano.it; griegas: akispetretzikis.com /
  otras del listado soportado), además de más fuentes españolas. Marcar su `cocina` para el
  mínimo de cocina local (contar ES/IT/GR como "mediterránea aceptable").
- **Relación con el matching**: cuanto más mediterráneo el corpus, más alto sube la cobertura
  real y menos recetas caen por la regla all-match. Es la vía natural para subir el pool
  utilizable (166 → ~869 tras la ingesta mediterránea) sin bajar la exigencia.
- **all-ingredients-match (ya implementado)**: `exigir_todos_ingredientes: true` — una receta
  solo entra si TODOS sus ingredientes no opcionales tienen producto en Alcampo. Los
  opcionales se detectan por texto ("opcional", "al gusto", "para decorar"…).

### I) Racionalizar ingredientes entre recetas (reducir desperdicio)  ✅ *(petición usuario — Enfoque A IMPLEMENTADO)*
Elegir las recetas del menú de forma que **compartan ingredientes**, para aprovechar el
formato comprado (si el producto es 1 kg de cebolla y una receta usa 250 g, que el resto de
recetas usen esa misma cebolla) → menos sobras, menos productos distintos y menos gasto.

**Implementado (2026-07-12) — Enfoque A:**
- `economia_recetas` expone los **productos de Alcampo que usa cada receta**; el solver los
  recibe en `RecetaOpt.productos`.
- En `optimizar_comida_cena`, `peso_reutilizacion` añade un binario `y_p`=1 si algún plato
  del menú usa el producto `p`, y penaliza `Σ y_p` en el objetivo → premia reutilizar los
  mismos productos. Config/UI: barra **`reutilizacion_pct`** (0-100, **0 = desactivado**).
- **Rendimiento (clave)**: la versión exacta (todos los productos compartidos, sin límite)
  tardaba **461 s** — inservible. Tratada con: (1) binarios **solo para productos poco
  comunes** (usados por 2..~3% del pool: son los que de verdad discriminan; comprar un
  producto para UN plato = sobras casi seguras); (2) **big-M ajustado** al máximo real de
  usos; (3) **límite de tiempo de 25 s** aceptando el mejor menú encontrado (incumbente).
- **Resultado medido** (plan 2 semanas, corpus real): productos distintos a comprar
  **38 → 32-33** (−15%), coste **+~1 €**, tiempo **~6 s al 40 %** / ≤25 s al 100 %. Por
  defecto desactivado (no afecta al rendimiento base ni a los tests).
- **Pendiente (Enfoque B, más preciso)**: penalizar la **sobra** real
  (`unidades·formato − gramos_necesarios`) por producto, no solo el nº de productos.

**Diseño (a implementar):**
- **Modelar el uso de PRODUCTO en el MILP**: hoy el solver solo maneja coste/nutrición
  agregados por receta. Habría que exponer, por receta, los gramos de cada producto de
  Alcampo (ya se calcula en `economia_recetas`/`compra`) y meterlo en el modelo.
- **Enfoque A (variedad de ingredientes, más simple)**: binario `y_p`=1 si algún plato del
  menú usa el producto `p`; penalizar `Σ y_p` en el objetivo (`peso_reutilizacion`) → premia
  reutilizar los mismos productos. Requiere ligar receta→producto con big-M.
- **Enfoque B (sobras, más preciso)**: para cada producto, `unidades = ceil(gramos_necesarios
  / formato)`; `sobra = unidades·formato − gramos_necesarios`; penalizar la sobra → ataca
  directamente el caso "1 kg de cebolla". Más variables (una por producto candidato).
- **Tensión con la variedad**: se opone al `peso_variedad` (que busca platos distintos). Se
  equilibra con pesos configurables; objetivo: recetas de **tipos** variados pero con
  **ingredientes** compatibles.
- **Recomendación**: empezar por el Enfoque A (penalización blanda de nº de productos
  distintos), medir reducción de sobras en la lista de la compra, y si compensa, pasar al B.

### Fases originales restantes
| Fase | Qué |
|---|---|
| 6 | **UI web (FastAPI + HTML, sin CDN)** ✅: vista de menú con **plan por día** (días 🍱 batchcooking = plato único; finde libre), página de recetas manuales/favoritas y **pantalla de configuración** (guarda en `config.usuario.yaml`, overlay sobre config.yaml). Modelo por día en el solver (`dias_batchcooking`, grupos cb/cl/d). `menu-app-web`. |
| 7 | **Exportación ✅**: menú y lista de la compra a **CSV y PDF** (fpdf2), lista **agrupada por pasillo**; botones de descarga en `/compra` (`optimizacion/exportar.py`) |
| 8 | **Empaquetado ✅**: PyInstaller onefile → `dist/MenuAlcampo.exe` (57 MB, incluye catálogo), lanzador que siembra datos en `%LOCALAPPDATA%\MenuAlcampo` y abre el navegador; instalador Inno Setup (`installer.iss`); ver `EMPAQUETADO.md` |
| 9 | Config avanzada y pulido: **equilibrio por grupos de alimentos AESAN ✅**, **despensa ✅**, **macros POR COMIDA ✅** (energía+proteína repartidas entre comida/cena por su % de energía FEN/AESAN + proteína pareja, Mamerow 2014; `escalar_bandas`, bandas por franja en el solver, `raciones_comida/cena`). Pendiente: micronutrientes (BEDCA/OFF), estacionalidad |
| 10 | **Identidad de marca ✅**: nombre **Sazón**, paleta mediterránea + design tokens (CSS vars, `web/marca.py`), logo e icono SVG, favicon, `.ico` del `.exe` (`assets/icono.ico`, `generar_icono.py`), rediseño de la UI con tokens. `dist/Sazon.exe`. |
| 11 | **Módulo de actualizaciones ✅** (NUEVO — petición usuario): `actualizaciones.py` (consulta GitHub Releases API, compara `version.py`), **banner** de nueva versión + sección en Configuración (repo + "Buscar actualizaciones"), workflow `.github/workflows/release.yml` (build `.exe` + Inno al pushear tag `v*`). **Publicado y verificado** contra `Kelryn/sazon` (repo real ya fijado en `config.yaml`). Ver G. |
| 12 | **QA final** (NUEVO — petición usuario, FASE FINAL): probar TODOS los botones y funciones de la app. Ver H. |

### M) Programa de escritorio (ventana nativa, sin terminal)  🚧 *(petición usuario)*
La app dejaba impresión de "terminal que abre una web". Se convierte en un **programa con
ventana propia**: `menu_app/escritorio.py` arranca el servidor FastAPI en un hilo y muestra
la UI en una **ventana nativa con pywebview** (WebView2/Edge, ya en Windows 10/11). El `.exe`
pasa a `console=False` (sin terminal) y entra por `escritorio.py`. El navegador externo solo
se abre para el carrito. Se empaqueta **Playwright** en el `.exe` (usa Chrome/Edge del
sistema, sin descargar Chromium) para que el carrito funcione en la app instalada — eso
arregla el "Falta el navegador automatizado". Comando `menu-app` (escritorio); `menu-app-web`
sigue sirviendo solo el servidor. **Verificado desde código fuente; pendiente validar el
`.exe`** (pywebview+pythonnet+playwright en PyInstaller es delicado; se vigila el build de CI).

### K) Fase — Lluvia de ideas (100+ mejoras)  ✅ *(petición usuario — HECHA, pendiente de valorar)*
Fase **antes de la QA final**: investigación a fondo de todas las partes de la app con un
**mínimo de 100 mejoras** posibles, para valorarlas juntos y priorizar. **Realizada
(2026-07-12): ver [MEJORAS.md](MEJORAS.md) — 120 mejoras** en 12 áreas (nutrición, matching,
solver, recetas, carrito, UI/UX, distribución, rendimiento, testing, IA opcional,
sostenibilidad, datos Alcampo). **Siguiente paso: priorizarlas con el usuario** (impacto ×
esfuerzo × riesgo, manteniendo el principio determinista) y meter las elegidas en el ROADMAP
como fases nuevas antes de la QA final.

### H) Fase final — QA (probar todos los botones y funciones)  *(NUEVO — petición usuario)*
Antes de cada release, verificar que **cada botón, enlace y acción funciona**. Se ejecuta
sobre la app en marcha (`Sazon.exe` o `menu-app-web`), comprobando que cada ruta responde y
que cada acción tiene el efecto esperado, además de la suite de tests automáticos.

**Checklist de la interfaz (todas las páginas y acciones):**
- **Menú (`/`)**: carga; flechas ◀▶ de semana; **Generar plan**; **Generar alternativa**;
  **Cambiar por otra** (cada receta); chips de grupos; banner de actualización (si aplica);
  enlaces de receta → detalle.
- **Detalle de receta (`/receta/{id}`)**: ingredientes con cantidad (g/ml), producto y precio;
  enlaces a Alcampo; coste total/ración.
- **Lista de la compra (`/compra`)**: agrupada por pasillo; enlaces a Alcampo; descargas
  **PDF/CSV de compra y de menú** (`/compra.pdf`, `/compra.csv`, `/menu.pdf`, `/menu.csv`).
- **Recetas (`/recetas`)**: buscar; **Nueva receta** (desplegable de ingredientes, unidades,
  +/- filas, flags, guardar → barras de nutrientes); **Editar**; **Eliminar**; favoritas.
- **Catálogo (`/catalogo`)**: buscar/paginar; **Editar producto** (guardar precio/nutrición/
  apto); **Actualizar catálogo** por categorías; visor.
- **Configuración (`/config`)**: guardar (sliders, días, raciones…); **Actualizaciones**
  (guardar repo, **Buscar actualizaciones**).
- **Empaquetado**: el `.exe` arranca, siembra datos, abre el navegador, y todas las páginas
  responden 200.

**Cómo**: además de `pytest` (suite de regresión), un barrido funcional (`qa_smoke.py`) que
hace GET a cada página (200) y POST a cada acción verificando el efecto. Se documentan y
corrigen los fallos encontrados.

**Ejecutada (2026-07-12): 23/23 PASS.** La QA detectó y corrigió un **bug crítico**: el
solver **CBC no se empaquetaba** en el `.exe` (faltaba `collect_all("pulp")` en el `.spec`),
por lo que "Generar menú" fallaba con `PulpSolverError` en el ejecutable (no en desarrollo).
Arreglado y reconstruido (`dist/Sazon.exe`, ~79 MB). Todas las páginas y acciones verificadas
sobre el `.exe` real.

### G) Fase 11 — Módulo de actualizaciones (distribución vía GitHub)  ✅ *(petición usuario — HECHO)*

**Publicado (2026-07-12):**
- Repo público **[github.com/Kelryn/sazon](https://github.com/Kelryn/sazon)** (rama `master`),
  código subido (v0.2.0). Cuenta GitHub `Kelryn`; `gh` autenticado (en
  `C:\Program Files\GitHub CLI\gh.exe`; si PowerShell no lo ve, abrir una terminal nueva).
- Tag `v0.2.0` → el workflow `release.yml` compiló en un runner Windows y **publicó la
  Release v0.2.0** (3m10s) con `Sazon.exe`.
- `config.yaml` → `actualizaciones.repo: "Kelryn/sazon"`.
- **Módulo de actualización verificado contra GitHub real:** `hay_actualizacion('Kelryn/sazon',
  '0.1.0')` detecta la 0.2.0 con su enlace; desde `'0.2.0'` → `None` (al día).
- **Fix aplicado:** `installer.iss` tenía `OutputBaseFilename=MenuAlcampo-Setup` ≠
  `Sazon-Setup.exe` que buscaba el workflow, por eso el instalador NO se adjuntó a la
  Release v0.2.0 (solo el `.exe`). Corregido → la próxima release incluirá también
  `Sazon-Setup.exe`.
- **Procedimiento de release (a partir de ahora):** actualizar `version.py` (+ `pyproject`),
  `git tag vX.Y.Z && git push origin master --tags` → Release automática. La app avisará con
  el banner y el enlace de descarga.
- **Nota:** el `dist/Sazon.exe` local se construyó antes de fijar el repo, así que su
  comprobación va en blanco hasta ponerlo en Configuración → Actualizaciones; las builds de
  CI ya lo llevan embebido.

Cómo publicar nuevas versiones de la app y avisar/instalar al usuario. Hay que distinguir
DOS tipos de actualización:
- **Datos** (precios, ofertas, productos, recetas): YA resuelto dentro de la app
  (pestaña Catálogo → actualizar; `--mediterranea` para recetas). No necesita nada nuevo.
- **Aplicación** (código: nuevas funciones, arreglos → nuevo `.exe`): es lo que cubre este
  módulo.

**Estudio de opciones (para el binario):**
| Opción | Coste/infra | Complejidad | Veredicto |
|---|---|---|---|
| **GitHub Releases + API** | Gratis, 0 infra | Baja | ✅ **RECOMENDADA** |
| PyUpdater (auto-update PyInstaller) | Gratis | Media-alta | Potente pero poco mantenido; overkill |
| WinSparkle (appcast XML) | Gratis, host del XML | Media | Requiere alojar el appcast; C lib |
| Servidor propio (version.json + .exe) | De pago/mantenimiento | Media | Contradice el espíritu de ahorro |
| Winget / Microsoft Store | Gratis pero trámites | Alta | Excesivo para una app personal |

**Por qué GitHub es lo óptimo aquí:** gratis, sin servidor que mantener, versionado con
changelog, página de descargas pública, y la **API de releases es pública** (no necesita
token si el repo de binarios es público). Encaja con el "espíritu de ahorro" de la app.

**Diseño recomendado:**
1. **Versionado**: `menu_app/version.py` (`__version__`, ya creado) como fuente única; el
   `.spec` y el instalador leen de ahí. Cada release lleva un *tag* `vX.Y.Z`.
2. **Publicación con GitHub Actions**: al hac*push* de un tag `v*`, un workflow
   (`.github/workflows/release.yml`) construye en un runner Windows el `.exe`
   (PyInstaller) y el instalador (Inno Setup) y los adjunta como *assets* de la Release.
   Repro­ducible y sin trabajo manual.
3. **Repos**: el código puede quedar **privado** (contiene el scraping de Alcampo) y
   publicar solo los BINARIOS en un repo **público** `sazon-releases` (o hacer público el
   propio repo). La comprobación usa `GET api.github.com/repos/{owner}/sazon-releases/releases/latest`
   (sin auth).
4. **Aviso dentro de la app**: al arrancar (o con un botón "Buscar actualizaciones" en
   Configuración), consultar la API con `httpx` (ya es dependencia), comparar `tag_name`
   con `__version__`. Si hay una más nueva → **banner** en la web con las notas de la
   versión y un **enlace de descarga** al instalador.
5. **Seguridad/UX (importante)**: NO auto-descargar-y-ejecutar en silencio. Lo seguro es
   **avisar + enlazar** a la Release para que el usuario descargue y ejecute el instalador
   él mismo (o, como mucho, descargar el instalador a *Descargas* y pedirle que lo lance).
   La contraseña/credenciales nunca intervienen; el instalador Inno ya no requiere admin.
6. **Instalación desde GitHub**: el README enlaza a la última Release; el usuario descarga
   `Sazon-Setup.exe` y lo instala. El módulo de auto-aviso solo apunta ahí.

**Componentes a crear (cuando se aborde):** `menu_app/actualizaciones.py`
(`hay_actualizacion() -> (version, url_release, notas) | None`), endpoint/-banner en la web,
`.github/workflows/release.yml` (build .exe + Inno + adjuntar a Release), y `config` con
`repo_releases: usuario/sazon-releases`.

### F) Fase 10 — Identidad de marca y diseño  *(NUEVO — petición usuario, FASE FINAL)*
Darle a la plataforma una imagen de marca reconocible y un diseño web atractivo.

**Entregables:**
- **Nombre** definitivo de la app (hoy provisional "Menu + Alcampo") y claim/eslogan.
- **Logo** (principal + variantes: horizontal, isotipo) y **favicon/icono** de la app y del
  `.exe` (`.ico` para PyInstaller `icon=`).
- **Paleta de colores** (clara y oscura) y **tipografía** (pareja display+texto).
- **Design tokens** (variables CSS) y **rediseño de la UI** (cabecera, tarjetas, tablas,
  botones, ticket de la compra, barras de nutrientes) manteniendo la regla de *sin CDN*
  (todo embebido / assets como data-URI) para que siga empaquetando limpio a `.exe`.
- **Guía de estilo** breve (uso de logo, colores, voz de marca).

**Skills/plugins a usar** *(analizados; ya disponibles como skills — no requieren instalar
plugins, que además no están habilitados en este entorno)*:
- `ui-ux-pro-max` → paleta de colores, pareja tipográfica, estilos de UI, layout, tokens.
- `design` / `design-system` → generación de **logo** e **icono** (SVG), design tokens,
  identidad corporativa, banners. *Ojo*: la generación por IA (Gemini) del skill `design`
  necesitaría clave de API; para respetar el enfoque sin-IA se priorizará **SVG hecho a mano
  / determinista** y las paletas de `ui-ux-pro-max`.
- `brand` → voz de marca, mensajería, nombre, consistencia.
- `banner-design` → recursos gráficos (redes/cabecera) si se quieren.
- `ui-styling` → si se moderniza el front con componentes (aunque hoy es HTML plano sin build;
  mantenerlo simple para el `.exe`).

**Cómo abordarla (a estructurar al llegar):**
1. Definir nombre + voz de marca (`brand`) y 2-3 direcciones creativas.
2. Elegir paleta + tipografía (`ui-ux-pro-max`) y fijar **design tokens** (variables CSS).
3. Crear logo + icono en **SVG** (y exportar `.ico` para el `.exe`).
4. Rediseñar la UI aplicando los tokens, sin romper el "sin CDN" ni el empaquetado.
5. Regenerar el `.exe` con el icono y la nueva imagen; mini guía de estilo.

## Pendiente de implementar (resumen)

Todo lo anterior de las Fases 0–12 está **hecho y publicado (v0.2.0)**. Lo que queda son
mejoras futuras, ninguna bloqueante:

1. **Racionalizar ingredientes** (sección I) — *Enfoque A IMPLEMENTADO* (barra
   `reutilizacion_pct`, 38→32 productos, ~6 s). Falta el **Enfoque B** (penalizar la sobra
   real por producto, no solo el nº de productos distintos).
2. **Carrito de Alcampo automático** (sección D) — *estudio hecho + prototipo construido*
   (`menu_app/carrito/`, CLI `menu-app-carrito`, dry-run por defecto). Falta **validar los
   selectores contra el DOM logueado real** (ejecución supervisada con el usuario), y luego
   integrarlo en la web/.exe. **Requiere sesión iniciada del usuario y su OK explícito antes
   de tocar el carrito**; la app nunca guarda la contraseña.
3. **Penalización de ultraprocesados / NOVA** (sección B) — sin empezar; clasificar
   `nivel_procesado` (1-4) y penalizar en el objetivo + tope semanal NOVA-4.
4. **Extensiones de la Fase 9** — micronutrientes (BEDCA/OFF) y estacionalidad; la estructura
   de `nutrientes.py` ya lo admite.
5. **Selección por día del batchcooking** (sección C) — el modelo por día ya existe; falta
   afinar postre-vs-plato y la mezcla de días tanda/no-tanda.

## Notas de diseño vigentes
- **Sin APIs de IA en el camino por defecto.** El desambiguador LLM (Gemini/Claude) queda
  como refinamiento OPCIONAL (`menu-app-emparejar --con-llm`).
- **Micronutrientes**: aún no restringidos (el `bop` solo da macros). Extensión futura con
  BEDCA/OFF; la estructura de `optimizacion/nutrientes.py` ya lo admite.
- **≥50% recetas españolas** en el menú (restricción del solver) y corpus dominado por
  fuentes ES.
