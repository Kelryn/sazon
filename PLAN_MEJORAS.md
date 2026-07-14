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
- ⬜ **34** Cache de `RecetaCalculada` (coste/nutrición).

## Lote 2 — Motor: variedad, explicabilidad y estructura de menú
- 🚧 **26** Multiobjetivo coste/salud/sabor (deslizador Pareto).
- ⬜ **27** Variedad de grupos por día · **28** Rotación multi-semana.
- ✅ **30** Tiempo máximo de preparación entre semana.
- ✅ **35** Explicabilidad (por qué entró cada receta).
- ⬜ **33** Warm-start del solver · **37** batchcooking multi-día · **38** nº de platos por comida.
- ⬜ **23/24** Racionalización Enfoque B (sobra real) + coste real de compra.

## Lote 3 — Nutrición y salud (v0.7.0)
- ⬜ **2** Nutri-Score · **3** NOVA/ultraprocesados · **4** kcal por peso/actividad.
- ⬜ **5** Perfiles por objetivo · **7** azúcares libres · **9** omega/trans · **10** alertas por comida.
- ⬜ **11** Estacionalidad · **12** fibra por comida.

## Lote 4 — Matching (v0.8.0)
- ⬜ **13** Cola de correcciones · **14** aprender sinónimos · **15** más barato · **16** marca blanca.
- ⬜ **17** Alérgenos · **18** densidad por ingrediente · **19** multi-formato · **20** desambiguación.
- ⬜ **21** Umbral fuzzy · **22** editor de sinónimos.

## Lote 5 — Recetas (v0.9.0)
- ⬜ **39** Pasos de elaboración · **40** fotos · **41** escalado · **42** importar por URL · **43** OCR.
- ⬜ **44** Valoraciones propias · **45** dedup · **46** tags · **47** utensilios · **48** más fuentes · **49** calidad · **50** desayunos/meriendas.

## Lote 6 — Carrito y compra (v0.10.0)
- ⬜ **51** Vía 1 API directa · **52** cantidad exacta · **53** sustituir agotados · **54** sincronizar.
- ⬜ **55** Vaciar cesta · **57** ofertas/comparador · **58** otros súper · **59** resumen · **60** reintento.

## Lote 7 — Interfaz (v0.11.0)
- ⬜ **61** Sin recargar (HTMX/Alpine) · **62** calendario drag&drop · **63** modo oscuro toggle.
- ⬜ **64** Buscador global · **65** dashboard · **66** lista marcable · **67** recordatorios · **68** impresión.
- ⬜ **69** Onboarding · **70** accesibilidad · **71** i18n · **72** móvil/PWA · **73** deshacer/rehacer.

## Lote 8 — Distribución y robustez (v0.12.0)
- ⬜ **74** Firmar .exe · **75** auto-descarga 2º plano · **76** changelog en la app · **77** canal beta.
- ⬜ **78** Playwright bajo demanda · **80** backups · **81** telemetría opt-in · **82** hash del instalador.

## Lote 9 — Rendimiento, arquitectura, testing (v0.13.0)
- ⬜ **84** Migraciones de esquema · **85** ingesta paralela · **86** modularizar app.py · **87** mypy.
- ⬜ **88** Reducir .exe · **89** cache nutrientes · **90** catálogo perezoso.
- ⬜ **91** Cobertura · **92** ruff/black · **93** QA en CI · **94** mock Alcampo · **95** hypothesis · **96** snapshots.

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
