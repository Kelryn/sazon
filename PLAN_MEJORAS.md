# Plan de implementación de mejoras (selección del usuario)

El usuario seleccionó **112 de las 120** mejoras de [MEJORAS.md](MEJORAS.md)
(excluidas: 1, 6, 8, 29, 32, 56, 79, 104). Se implementan **por lotes temáticos
versionados**, publicando cada lote en GitHub. Este documento es el mapa vivo.

Leyenda: ⬜ pendiente · 🚧 en curso · ✅ hecho.

## Lote 1 — Motor: ahorro, exclusiones y rendimiento (v0.6.0)
- ✅ **25** Presupuesto máximo semanal (tope de € como restricción dura).
- ✅ **31** Exclusión de ingredientes que no gustan (lista negra).
- ✅ **36** `timeLimit`/`gap` del MILP configurables.
- ✅ **83** Índices SQLite en columnas de join/match.
- ✅ **34** Cache de `RecetaCalculada` (coste/nutrición).

## Lote 2 — Motor: variedad, explicabilidad y estructura de menú
- ✅ **26** Multiobjetivo coste/salud/sabor (deslizador Pareto).
- ✅ **27** Variedad de grupos por día · ✅ **28** Rotación multi-semana.
- ✅ **30** Tiempo máximo de preparación entre semana.
- ✅ **35** Explicabilidad (por qué entró cada receta).
- ✅ **23/24** Racionalización Enfoque B (sobra real) + coste real de compra.
- ⏸️ **33** Warm-start del solver — evaluado: **bajo ROI** para nuestros tamaños (el solve
  base son ~4 s) y el warm-start de CBC vía PuLP es delicado; se deja aparcado.
- ⏸️ **37** Batchcooking multi-día · ⏸️ **38** Nº de platos por comida — **requieren
  rediseñar el modelo por día** del solver (hoy produce comida/cena planas y `asignar_dias`
  las reparte a posteriori). Son cambios grandes y arriesgados: se abordarán en una
  **sesión dedicada** (mini-proyecto propio) para no desestabilizar el motor.

## Lote 3 — Nutrición y salud (v0.7.0)
- ✅ **2** Nutri-Score · ✅ **3** NOVA/ultraprocesados · ✅ **4** kcal por peso/actividad.
- ✅ **5** Perfiles por objetivo · ⏸️ **7** azúcares libres · ⏸️ **9** omega/trans (⚠️ el catálogo no da estos datos) · ✅ **10** alertas por comida.
- ✅ **11** Estacionalidad · ✅ **12** fibra por comida.

## Lote 4 — Matching (v0.8.0)
- ✅ **13** Cola de correcciones · ✅ **14** aprender sinónimos · ✅ **15** más barato · ✅ **16** marca blanca.
- ⬜ ⏸️ **17** Alérgenos (sin datos OFF) · ✅ **18** densidad por ingrediente · ⏸️ **19** multi-formato · ⏸️ **20** desambiguación (avanzadas, aparcadas).
- ✅ **21** Umbral fuzzy · ✅ **22** editor de sinónimos.

## Lote 5 — Recetas (v0.9.0)
- ✅ **39** Pasos de elaboración · ✅ **40** fotos · ✅ **41** escalado · ✅ **42** importar por URL · ⏸️ **43** OCR (requiere libreria externa, aparcado).
- ⏸️ **44** Valoraciones propias (ver Lote 12, es el mismo sistema completo) · ✅ **45** dedup · ✅ **46** tags · ✅ **47** utensilios · ✅ **48** más fuentes (recipe-scrapers soporta 583 sitios) · ✅ **49** calidad · ✅ **50** desayunos/meriendas (sugeridor separado del MILP).

## Lote 6 — Carrito y compra (v0.10.0)
- ✅ **53** Sustituir agotados (misma subcategoría, no cruza pasillo) · ✅ **54** sincronizar
  (ajusta a la cantidad exacta) · ✅ **55** vaciar cesta antes.
- ✅ **57** Ofertas (precio de oferta + ahorro mostrado) · ✅ **59** resumen (ahorro total,
  nº sustituidos) · ✅ **60** reintento (1 vez, solo fallos transitorios).
- ⏸️ **52** Cantidad exacta — ya cubierto en la práctica por **54** (sincronizar logra
  cantidad exacta incluso si ya había algo en la cesta).
- ⬜ **51** Vía 1 API directa — el endpoint del carrito ya se captura (ver carrito/alcampo.py)
  pero reconstruir la llamada autenticada es mas fragil que Playwright; se deja para cuando
  haya evidencia de que el navegador da problemas.
- ⏸️ **58** Otros supermercados (Mercadona, Carrefour, DIA) — arquitectura grande (nuevo
  modulo de scraping+carrito por cadena); se aparca como los "modelo por dia" (#37/#38):
  mismo patron ya construido para Alcampo, a replicar en una sesion dedicada si se decide.
- Nota: #53/#57/#59 verificados con tests (sustitucion respeta subcategoria, rechaza
  cruzar a "Especias" desde "Verduras"; oferta calcula ahorro correcto). #54/#55/#60 usan
  selectores CONFIRMADOS en vivo en sesiones anteriores (no son conjeturas), pero como
  cualquier cambio en el carrito, conviene una prueba en vivo con el usuario antes de
  confiar en ellos a ciegas la primera vez.

## Lote 7 — Interfaz (v0.11.0)
- ✅ **63** Modo oscuro toggle (botón 🌓, persiste en localStorage, gana al del sistema).
- ✅ **64** Buscador global (`/buscar`: recetas + productos en una caja).
- ✅ **65** Dashboard (`/dashboard`: sparkline SVG de gasto por semana + top recetas usadas;
  SVG generado en servidor, sin librería de gráficos ni CDN).
- ✅ **66** Lista marcable (`/compra`: checkboxes que tachan la línea, persisten en
  localStorage por plan+producto — sigues aunque cierres y reabras la app).
- ✅ **67** Recordatorio "hoy toca" (banner en el menú según el día de la semana actual;
  nota: por nombre de día lun..dom dentro de la semana MOSTRADA, no por fecha calendario
  real — el plan no guarda fechas exactas).
- ✅ **68** Vista de impresión (`@media print`: oculta nav/botones, ideal para imprimir el
  ticket o el menú).
- ✅ **69** Onboarding (checklist "Primeros pasos" cuando falta catálogo/recetas/plan).
- ✅ **70** Accesibilidad: enlace "saltar al contenido", `aria-label` en botones-icono
  (flechas semana, toggle tema), `alt` descriptivo en fotos de receta.
- ⏸️ **61** Sin recargar (SPA-like con HTMX/Alpine) — cubierto PARCIALMENTE ya (checkbox de
  compra, escalado de receta, tema, todo vía JS+localStorage sin recargar); una migración
  completa a HTMX es un cambio de arquitectura grande, se aparca.
- ⏸️ **62** Calendario drag&drop — requiere UI de arrastrar + endpoint de reordenar
  persistente; scope grande, mismo criterio que #37/#38 (sesión dedicada).
- ⏸️ **71** i18n — extraer y traducir todas las cadenas de la app; trabajo transversal
  grande, se aparca (la app es monolingüe ES por decisión de producto, ver CLAUDE.md).
- ⏸️ **72** Móvil/PWA — la app corre en `pywebview` (ventana nativa local), no como sitio
  público; un manifest/service worker no aporta valor real aquí. Aparcado por bajo ROI.
- ⏸️ **73** Deshacer/rehacer — requiere una máquina de estados sobre las acciones del menú
  (generar/cambiar/alternativa); scope grande, se aparca.

## Lote 8 — Distribución y robustez (v0.12.0)
- ✅ **75** Auto-descarga en 2º plano (pre-descarga al detectar versión nueva; "Instalar"
  es instantáneo). ✅ **76** Changelog en la app (notas de la release, inline, con
  `<details>`). ✅ **77** Canal beta (selector estable/beta en Configuración; beta
  consulta `/releases` e incluye pre-releases).
- ✅ **78** Playwright bajo demanda (botón "Instalar navegador de respaldo" en
  `/compra`; solo aparece si Playwright está pero Chromium no — el flujo normal usa
  tu Chrome/Edge, esto es una red de seguridad). ✅ **80** Backups (automático al
  arrancar + Configuración: crear/listar/restaurar, purga a 10, restaurar hace copia
  de seguridad antes — **bug real detectado y corregido**: los nombres por segundo
  colisionaban y se sobreescribían; ahora usan microsegundos). ✅ **81** Telemetría
  **100% LOCAL, opt-in** (Sazón no tiene servidor propio: no se envía nada por red;
  es un log local de errores que el usuario activa si quiere). ✅ **82** Hash del
  instalador (el workflow publica `SHA256SUMS.txt`; la app verifica el hash antes de
  lanzar el instalador y aborta si no coincide — verificado con test: hash incorrecto
  bloquea la instalación y borra el fichero).
- ⏸️ **74** Firmar el `.exe` — **requiere comprar un certificado de firma de código**
  (Authenticode, de una CA); no es algo que se pueda "implementar" sin ese recurso
  externo. Dejado el paso de firma en el workflow, **inactivo** salvo que el usuario
  añada `SIGNING_CERT_BASE64`/`SIGNING_CERT_PASSWORD` como secrets del repo.

## Lote 9 — Rendimiento, arquitectura, testing (v0.13.0)
- ✅ **84** Migraciones de esquema: runner de migraciones versionadas (`_MIGRACIONES`
  en `almacenamiento/db.py`) sobre el `schema_version` ya existente en `meta`, para
  cambios que un simple `ALTER TABLE ADD COLUMN` no puede expresar (la evolución
  aditiva de columnas, que cubre el 100% de las versiones 1-5, ya era idempotente
  desde antes). 3 tests nuevos (orden, ejecución única, BD nueva ya al día).
- ✅ **86** Modularizar `web/app.py`: extraídos `web/plantillas.py` (helpers de
  render HTML, funciones puras) y `web/tareas.py` (jobs en 2º plano + su estado:
  catálogo, carrito, Chromium, actualizaciones). `app.py` baja de 2189 a 1639
  líneas (-27%). El resto de rutas (~50 endpoints, todas closures sobre `_conn`
  dentro de `crear_app()`) se deja **aparcado**: partirlas en routers exige tocar
  las ~50 a la vez con riesgo real de regresión, para un beneficio puramente
  interno/estético en una app de escritorio de un solo usuario — mismo criterio
  que #37/#38/#58/#62 (sesión dedicada si se decide abordarlo).
- ✅ **87** mypy: adoptado en modo laxo (`disallow_untyped_defs = false`,
  progresivo). Encontró un bug real: `escritorio.py` sobreescribía
  `server.install_signal_handlers` con un no-op, pero ese método **ya no existe**
  en uvicorn 0.51 (ahora `capture_signals()` detecta el hilo no-principal por su
  cuenta) — el parche llevaba tiempo sin hacer nada. Eliminado. Quedan 82 avisos,
  todos del mismo patrón en `web/app.py` (`Form(...)` sin narrowing de
  `UploadFile | str`); documentado como base de partida, no bloqueante.
- ✅ **89** Cache de nutrientes: el cruce con OFF ya cacheaba peticiones HTTP
  (`ingesta.cache.HttpCache`, de antes) y el coste/nutrición por receta ya se
  cacheaba (Lote 1 #34). Lo que faltaba: `IndiceProductos.construir()` (fuzzy
  matching) se reconstruía de cero en cada vista del editor de recetas —
  **230 ms medidos** sobre el catálogo real (13886 productos aptos). Cacheado por
  firma del catálogo (patrón igual al de #34): **230 ms → 28 ms** (8x) en
  llamadas repetidas. 2 tests nuevos.
- ✅ **90** Catálogo perezoso: la misma cache de #89 evita reconstruir el índice
  completo en memoria en cada petición; no se ha encontrado otro punto caliente
  que cargue el catálogo entero innecesariamente.
- ✅ **91** Cobertura: `pytest-cov` instalado y medido — **52% global**. Los
  huecos grandes son los `cli.py` de cada etapa (0%, son wrappers finos de
  argumentos sobre lógica ya testeada) y ramas de HTML poco visitadas; no hay
  ningún módulo de negocio crítico sin cubrir. Sin gate de cobertura mínima (no
  tiene sentido perseguir el 100% en una app de un usuario).
- ✅ **92** ruff adoptado (no black: ruff format se descartó para no reformatear
  en bloque los muchos f-strings de HTML embebido, con un diff enorme y sin
  beneficio real). `ruff check` arrancó con 114 errores; corregidos todos
  (imports muertos, variable `l` ambigua, `zip()` sin `strict=`, claves de dict
  duplicadas en `glosario.py`, `raise ... from`, etc.) — **0 errores** ahora.
- ✅ **93** QA en CI: `.github/workflows/tests.yml` nuevo, corre en cada push/PR
  (`ruff check` + `pytest -m "not live"`), separado de `release.yml` (solo en
  tags). De paso, arreglado un bug real: `test_contract_live.py` no tenía
  registrado el marcador `live` que CLAUDE.md documenta (`-m "not live"`) — sólo
  un `skipif` por variable de entorno; el comando documentado no hacía nada.
  Añadido el marcador para que el comando funcione de verdad.
- ✅ **94** Mock de Alcampo: ya cubierto desde antes (`pytest-httpx` en toda la
  suite salvo `test_contract_live.py`, deshabilitado por defecto); verificado que
  sigue siendo así.
- ✅ **95** Hypothesis: 3 tests de propiedades (`es_mas_nueva` nunca se compara
  como más nueva que sí misma / incrementar el patch siempre gana; `_distribuir`
  coloca cada receta exactamente las veces pedidas para cualquier reparto y N).
- ✅ **96** Snapshots: test de snapshot para `compra_a_csv` — fija el CSV EXACTO
  byte a byte (no solo subcadenas como los tests existentes), para detectar
  cualquier cambio de formato no intencionado.
- ⏸️ **85** Ingesta paralela — revisado: `RateLimiter` (ya preparado con lock
  para el futuro, ver su docstring) impone un intervalo MÍNIMO entre peticiones
  para "ser un buen ciudadano" con el servidor de Alcampo; ese intervalo (no el
  procesado local: JSON+SQLite tarda milisegundos) es lo que domina el tiempo
  total. Paralelizar los HILOS de fetching NO reduciría el tiempo real sin
  acortar también el intervalo entre peticiones — que es exactamente lo que NO
  se quiere hacer (arriesga que Alcampo bloquee la IP/sesión). Aparcado: no hay
  una forma segura de acelerar esto sin dejar de "ser gentiles".
- ⏸️ **88** Reducir el `.exe` — revisado: `menu-app.spec` ya excluye
  `matplotlib/tkinter/google/anthropic/IPython` (el desambiguador IA es
  solo-CLI, no lo usa la app de escritorio) y `pandas` no se empaqueta porque
  nada en el arbol de imports de `escritorio.py`/`web/app.py` lo toca. Tamaño ya
  documentado en EMPAQUETADO.md (~57 MB con catálogo, ~40 MB sin él). No se ha
  encontrado grasa adicional que quitar sin un build-and-measure completo (caro,
  bajo ROI dado que ya está ajustado); aparcado salvo que aparezca una razón
  concreta para revisarlo.

## Lote 10 — Datos, IA opcional y sostenibilidad (v0.14.0)
- ⬜ **97** Cocinar con la despensa · **98** OCR ticket · **99** recomendador · **100** sustituciones.
- ⬜ **101** Explicación NL (IA opc.) · **102** chat (IA opc.) · **103** predicción de gasto.
- ⬜ **105** Anti-desperdicio · **106** usa lo que caduca · **107** multi-perfil · **108** raciones infantiles.
- ⬜ **109** Historial/repetir · **110** temporada/festivos · **111** export fitness/listas · **112** cupones.
- ⬜ **113** Presupuesto por comensal · **114** compartir menús · **115** despensa básica.
- ⬜ **116** Catálogo programado · **117** re-match descatalogados · **118** avisar subidas · **119** cobertura fibra · **120** validación de datos.

## Lote 11 — Rediseño completo GUIADO por el usuario (v0.15.0) *(petición usuario)*
Rediseño **integral** de la interfaz, dirigido por el usuario: se le preguntará
**sección por sección** (menú, lista de la compra, recetas, catálogo, configuración,
carrito, detalle de receta) y **elemento por elemento** (cada botón, columna, bloque,
tarjeta, tabla, cabecera, formulario…) qué quiere y cómo lo quiere. Metodología:
- ⬜ Inventario de TODAS las pantallas y sus elementos (checklist para no dejarse nada).
- ⬜ Entrevista guiada por secciones: yo pregunto, el usuario da ideas (estilo, colores,
  disposición, textos, comportamiento) de cada bloque/botón/columna.
- ⬜ Mockups/propuestas por sección para validar antes de implementar.
- ⬜ Implementación respetando "sin CDN" (todo embebido) para que siga empaquetando a `.exe`.
- ⬜ Revisión final y guía de estilo actualizada.
Depende de decisiones del usuario (no se puede hacer en autónomo). Idealmente después
del Lote 7 (interfaz) o cuando el usuario quiera abrir la entrevista.

## Lote 12 — Sistema de valoración personal de recetas (v0.16.0) *(petición usuario)*
Sistema completo para **clasificar personalmente** cada receta hecha, y usarlo para
afinar los gustos y la adherencia a la dieta. Requisitos del usuario:
- ⬜ **Cola de valoración**: mostrar las recetas **hechas esta semana o una semana
  anterior** que aún no se han valorado. Al valorar una, no se vuelve a pedir.
- ⬜ **Baremos con 1–5 estrellas**: **sabor**, **frescura** (más de verano ↔ invierno),
  **recepción estomacal** (sentó mejor/peor), y otros útiles que se propongan
  (**saciedad**, **facilidad de preparación**, **se repetiría**, **relación calidad/precio**,
  **apetecible en frío/tupper**). El usuario validará la lista final de baremos.
- ⬜ **Persistencia**: la valoración se guarda; no se vuelve a solicitar. Se puede
  **re-valorar** buscando en las recetas **ya clasificadas** (buscador/histórico).
- ⬜ **Detalle cualitativo**: marcar **qué ingredientes** gustaron más y/o si fue el
  **método de preparación**, para **recomendar por similitud** (ingredientes/técnica).
- ⬜ **Uso en el motor**: la valoración personal alimenta la palatabilidad y ayuda a
  proponer recetas afines; permite una dieta más estricta sin perder gusto.
- ⬜ **Modelo de datos**: tabla `valoraciones` (receta_id, baremo, estrellas, fecha) +
  `valoracion_detalle` (ingredientes/aspectos preferidos); recomendador por similitud.
Se apoya en el histórico de planes (recetas hechas) y en el editor de recetas.

---
Al terminar todos los lotes → **QA final** (fase última del ROADMAP).
