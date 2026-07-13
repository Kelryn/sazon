# Lluvia de ideas — mejoras posibles de Sazón (≥100)

Fase de brainstorming (petición del usuario): investigación a fondo de **todas las
partes** de la aplicación con posibles mejoras, para valorarlas juntos y priorizar.
Cada punto es una idea concreta y accionable; al lado, el porqué. **No están
priorizadas todavía** — eso lo decidimos después.

Estado de referencia: motor 100% determinista, corpus 4263 recetas, matching ~95,6%,
carrito Alcampo funcionando, racionalización (Enfoque A) y actualizaciones por GitHub.

---

## A) Nutrición y salud
1. **Micronutrientes** (hierro, calcio, vit. C/D, folato, B12, potasio, magnesio) desde BEDCA/USDA y como bandas en el solver (la estructura ya lo admite). → dieta realmente completa, no solo macros.
2. **Nutri-Score** por receta y por menú (fórmula oficial FSA) mostrado como letra A–E. → señal de salud fácil de leer.
3. **Clasificación NOVA / ultraprocesados** y penalización en el objetivo + tope semanal (ROADMAP B). → menos procesados sin prohibirlos.
4. **Cálculo de kcal objetivo** desde peso/edad/sexo/actividad (Mifflin-St Jeor) en vez de fijarlas a mano. → personalización real.
5. **Perfiles por objetivo**: mantenimiento / pérdida de grasa / ganancia muscular (ajustan kcal y proteína). 
6. **Perfiles médicos**: diabético, hipertensión, colesterol alto (endurecen topes de azúcar/sal/grasa saturada).
7. **Azúcares libres vs totales**: hoy solo totales; estimar libres cruzando ingredientes para no penalizar fruta/lácteos.
8. **Índice/carga glucémica** estimada por receta.
9. **Ratio omega-3/omega-6** y aviso de grasas trans.
10. **Alertas por comida**: exceso de sodio o azúcar en una comida concreta.
11. **Estacionalidad**: preferir fruta/verdura de temporada (más barata, mejor sabor, menos huella).
12. **Objetivo de fibra por comida** además del diario.

## B) Matching ingrediente → producto
13. **Cola de correcciones** desde la web: revisar los "sin match" y corregirlos a mano.
14. **Aprendizaje de correcciones**: cada corrección se guarda como sinónimo permanente (mejora continua).
15. **Elegir el producto más barato** entre equivalentes (hoy se coge uno; optimizar €/kg).
16. **Preferir marca blanca** (Producto Alcampo) por defecto para ahorrar, configurable.
17. **Detección de alérgenos** en el producto casado (avisar si contiene un alérgeno del perfil).
18. **Densidad por ingrediente** (hoy 1 ml ≈ 1 g genérico) → gramos/coste más exactos en líquidos.
19. **Match multi-formato**: cubrir un ingrediente combinando varios paquetes.
20. **Desambiguación por contexto** (p. ej. "nata cocinar" vs "montar", "chocolate postres" vs "cobertura").
21. **Umbral fuzzy configurable** como último recurso para los que no casan por token.
22. **Editor de sinónimos/equivalencias** desde la UI (glosario ampliable sin tocar código).

## C) Optimizador de menú (solver)
23. **Racionalización Enfoque B**: penalizar la **sobra real** por producto (`unidades·formato − gramos`), no solo el nº de productos.
24. **Coste real de compra** como objetivo (unidades×formato con IVA), no la suma de coste por ración.
25. **Presupuesto máximo semanal** como restricción dura (tope de €).
26. **Multiobjetivo Pareto** coste/salud/sabor con un deslizador para moverse por la frontera.
27. **Variedad de grupos por día** (no legumbre dos días seguidos; alternar proteínas).
28. **Rotación multi-semana** (memoria de N semanas para no repetir).
29. **Equilibrio de técnica de cocción** (no todo frito/horno).
30. **Tiempo máximo de preparación** entre semana (recetas rápidas de lunes a viernes).
31. **Exclusión de ingredientes que no gustan** (lista negra del usuario).
32. **Restricciones dietéticas**: vegetariano/vegano/sin gluten/sin lactosa (filtro de corpus).
33. **Warm-start** del solver con el menú anterior → resuelve más rápido.
34. **Cache de `RecetaCalculada`** (coste/nutrición) para no recalcular en cada generación.
35. **Explicabilidad**: mostrar por qué entró cada receta (coste, sabor, grupo, favorita).
36. **`timeLimit`/`gap` del MILP configurables** para equilibrar velocidad y optimalidad.
37. **Cocina en tanda multi-día**: cocinar el doble un día y reutilizar al siguiente (menos esfuerzo y sobras).
38. **Nº de platos por comida** configurable (primero + segundo + postre).

## D) Recetas y corpus
39. **Pasos de elaboración** en la ficha (hoy solo ingredientes) y tiempo/dificultad.
40. **Fotos de receta** cuando la fuente las ofrece.
41. **Escalado dinámico de raciones** en la ficha.
42. **Importar receta por URL** (pegar enlace → scrape con recipe-scrapers).
43. **Importar receta por foto/OCR** (libro o etiqueta).
44. **Valoraciones propias**: el usuario puntúa → alimenta la palatabilidad personalizada.
45. **Deduplicar** recetas casi idénticas (near-duplicate).
46. **Tags** (rápido, niños, picante, fiesta, sin horno…).
47. **Utensilios necesarios** (olla exprés, horno, batidora) y filtrar por lo que tienes.
48. **Más fuentes mediterráneas** (portuguesas, magrebíes) manteniendo el all-match.
49. **Puntuación de calidad de receta** (claridad, nº pasos, valoraciones) como desempate.
50. **Desayunos y meriendas** planificados (hoy solo comida y cena).

## E) Carrito y compra (Alcampo y más)
51. **Vía 1 — API directa del carrito** con `httpx` reutilizando cookies (mucho más rápida que el navegador); ya se captura el endpoint.
52. **Fijar cantidad exacta** leyendo el contador del producto (no solo pulsar "+").
53. **Sustituir agotados** por una alternativa equivalente automáticamente.
54. **Sincronizar cantidades** (si ya hay algo en la cesta, ajustar a lo pedido en vez de sumar).
55. **Vaciar cesta antes de enviar** (opción).
56. **Reservar franja de entrega** automáticamente.
57. **Comparador de precios** y **detección de ofertas** (preferir producto en promoción).
58. **Otros supermercados** (Mercadona, Carrefour, DIA) con la misma arquitectura de carrito.
59. **Resumen de compra** post-envío (qué entró, qué faltó, ahorro estimado).
60. **Reintento inteligente** de líneas fallidas.

## F) Interfaz web y UX
61. **Interactividad sin recargar** (HTMX/Alpine embebido, respetando el "sin CDN").
62. **Calendario semanal drag & drop** para mover recetas entre días.
63. **Modo oscuro con toggle manual** (hoy sigue al sistema).
64. **Buscador global** (recetas + productos + ingredientes).
65. **Dashboard**: gasto histórico, evolución nutricional, top recetas.
66. **Lista de la compra marcable** (checkboxes que persisten mientras compras).
67. **Recordatorios** ("hoy toca cocinar X", "descongela Y").
68. **Vista de impresión** bonita del menú y del ticket.
69. **Onboarding/tour** la primera vez.
70. **Accesibilidad WCAG** (roles ARIA, contraste, navegación por teclado).
71. **Internacionalización (i18n)** para poder usarla en inglés u otros idiomas.
72. **Mejoras móvil / responsive** y **PWA instalable** (uso offline básico).
73. **Deshacer/rehacer** cambios del menú.

## G) Distribución, empaquetado y actualizaciones
74. **Firmar el `.exe`** (code signing) para evitar el aviso de SmartScreen.
75. **Auto-descarga en 2º plano** de la actualización y aviso "listo para instalar".
76. **Changelog en la app** antes de instalar (leer las notas de la release).
77. **Canal beta / estable** seleccionable.
78. **Playwright/Chromium bajo demanda**: instalar el navegador la primera vez que se usa el carrito (no hinchar el `.exe`).
79. **Versión portable** (sin instalador).
80. **Backups automáticos** de la BD, config y planes (y restaurar).
81. **Telemetría de errores opt-in** y anónima para depurar en producción.
82. **Verificación de integridad** (hash) del instalador descargado antes de ejecutarlo.

## H) Rendimiento y arquitectura
83. **Índices SQLite** en columnas de `join`/match y `retailer_product_id`.
84. **Migraciones de esquema** versionadas (evitar romper BDs antiguas al actualizar).
85. **Ingesta del catálogo en paralelo** (async) respetando el rate-limit.
86. **Modularizar `web/app.py`** (es enorme) en routers por sección.
87. **Tipado estático completo** + `mypy` en CI.
88. **Reducir tamaño del `.exe`** (excluir binarios/paquetes no usados).
89. **Cache de nutrientes** por producto y de la lista de la compra.
90. **Cargar el catálogo perezosamente** en la web (ya hay paginación; optimizar consultas).

## I) Calidad, testing y CI
91. **Cobertura medida** con objetivo (>85%) y badge.
92. **`ruff` + `black` en pre-commit y CI** (lint/formato automáticos).
93. **QA funcional (`qa_smoke`) en CI** en cada push.
94. **Tests end-to-end del carrito** contra un mock de Alcampo (sin red real).
95. **Tests de propiedades** (`hypothesis`) para el parser de ingredientes/cantidades.
96. **Snapshot tests** de las páginas web clave.

## J) Datos, personalización e IA opcional
97. **Cocinar con lo que hay en la despensa**: introduces lo que tienes → prioriza recetas que lo usen.
98. **Escaneo de ticket/despensa por foto** (OCR) para rellenar la despensa.
99. **Recomendador por afinidad** (aprende de tus valoraciones).
100. **Asistente de sustituciones** ("no tengo nata, ¿por qué la cambio?").
101. **Explicación nutricional en lenguaje natural** (LLM **opcional**, nunca en el camino por defecto).
102. **Chat opcional** para pedir cambios ("hazme la semana más barata / más proteica").
103. **Predicción de gasto mensual** y objetivos de ahorro.

## K) Sostenibilidad, hogar y ecosistema
104. **Huella de carbono** estimada por receta y por menú.
105. **Minimizar desperdicio**: ordenar la compra por caducidad y avisar de perecederos.
106. **Modo "usa lo que caduca antes"** al planificar.
107. **Multi-perfil / hogar**: varias personas con objetivos y gustos distintos.
108. **Raciones infantiles** y modo familiar.
109. **Historial de menús** y "repetir semana pasada".
110. **Menús por temporada/festivos** (Navidad, verano, barbacoa).
111. **Exportar a apps de fitness** (MyFitnessPal, etc.) y a **listas** (Google Keep, Todoist).
112. **Cupones/descuentos** de Alcampo aplicados automáticamente.
113. **Presupuesto por comensal** y ajuste automático del menú al presupuesto.
114. **Compartir menús** entre usuarios (exportar/importar un plan).
115. **Modo "despensa básica"**: comprar solo lo que falta respecto a lo que ya tienes.

## L) Robustez y datos de Alcampo
116. **Actualización programada del catálogo** (cron) para precios/ofertas al día.
117. **Detección de productos descatalogados** y re-match automático.
118. **Aviso de subidas de precio** relevantes desde la última compra.
119. **Cobertura del dato de fibra/nutrientes**: completar con OFF para subir del ~86%.
120. **Validación de datos**: detectar precios/nutrientes anómalos (outliers) y marcarlos para revisión.

---

**Total: 120 mejoras.** Siguiente paso: valorarlas juntos (impacto × esfuerzo) y elegir
las que entran en las próximas versiones. Sugerencia de criterios: (1) impacto en el
objetivo central —ahorro y salud—, (2) esfuerzo, (3) riesgo, (4) si mantiene el
principio "determinista y sin APIs de IA por defecto".
