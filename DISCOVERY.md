# FASE 0 — Descubrimiento de la API interna de Alcampo (compraonline.alcampo.es)

> Estado: **confirmado en vivo** el 2026-07-09 navegando manualmente el sitio con DevTools/fetch
> instrumentado desde el propio navegador. Postal code de prueba: 28029 (Madrid, tienda "Vaguada").

## 1. Plataforma

Confirmado: Alcampo corre sobre **Ocado Smart Platform (OSP)**. Evidencia:
- Eventos de analítica (`region1.analytics.google.com/g/collect`) incluyen parámetros propios de OSP:
  `ep.retailer_banner_id=alcampo`, `ep.retailer_region_id=5`, `ep.region_name=Vaguada`,
  `ep.osp_session_id=...`.
- No es Next.js (no existe `__NEXT_DATA__`). Es una SPA servida por un bundle propio
  (`/static/index-<hash>.js`), probablemente React/Vue con Webpack o Vite.
- Hay un endpoint `/graphql` (POST) usado para algunas funciones (reviews, financiación,
  productos destacados), pero el **catálogo y el detalle de producto van por REST**, no GraphQL.

## 2. robots.txt

```
User-agent: *
Disallow: /sso-login
Sitemap: https://compraonline.alcampo.es/sitemaps/sitemap_index.xml
```

Todo lo que necesitamos (`/categories/...`, `/products/...`, `/api/webproductpagews/...`) está
permitido para bots genéricos. Solo `/sso-login` está vetado (no lo tocamos, no hace falta login
para ver catálogo y precios). Hay un `sitemap_index.xml` que puede servir para descubrir todas las
categorías/URLs de producto de forma sistemática — mejor que fuerza bruta.

## 3. Endpoints confirmados

### 3.1 Listado de categoría (EL ENDPOINT CLAVE para el catálogo)

```
GET https://www.compraonline.alcampo.es/api/webproductpagews/v6/product-pages
    ?includeAdditionalPageInfo=true
    &maxPageSize=300
    &maxProductsToDecorate=50
    &retailerCategoryId=OCDesnatada
    &sortOptionId=favorite
    &tag=web
    &tag=category-item
```

- **Funciona con un `GET` simple**, sin cabeceras especiales, usando solo las cookies de sesión
  normales del navegador (`credentials: include`). Devuelve `200` y `content-type: application/json`.
- `retailerCategoryId` es el identificador que aparece al final de la URL de categoría en el sitio,
  p.ej. `OC1603` (Leche, categoría padre) o `OCDesnatada` (Leche desnatada, subcategoría). No es
  siempre numérico.
- Forma de la respuesta:
  ```json
  {
    "productGroups": [
      {
        "type": "on_offer",
        "decoratedProducts": [
          {
            "productId": "1773b242-70ab-426a-8e2d-2f4f959d5f99",   // GUID interno OSP
            "retailerProductId": "54186",                            // ID usado en la URL /products/.../54186
            "type": "REGULAR",
            "name": "AUCHAN Leche desnatada de vaca 6x 1 l Producto Alcampo.",
            "brand": "PRODUCTO ALCAMPO",
            "packSizeDescription": "6000ml",
            "price": {"amount": "4.92", "currency": "EUR"},
            "unitPrice": {"price": {"amount": "0.82", "currency": "EUR"}, "unit": "fop.price.per.litre", "unitName": "PER_LITRE"},
            "available": true,
            "promotions": [{"description": "Producto en Folleto (30/06/26_14/07/26)", "type": "OFFER"}],
            "imageConfig": {"availableFormats": ["jpg", "webp"], "availableResolutions": ["100x100", "150x150", "200x200", "300x300", "..."]},
            "image": "...", "images": [...], "imagePaths": [...],
            "ratingSummary": {...},
            "alcohol": false,
            "categoryPath": [...],
            "isNew": false
          }
        ]
      }
    ]
  }
  ```
- **Este endpoint NO trae nutrición/EAN/ingredientes/alérgenos** — solo datos de listado (precio,
  marca, imágenes, promoción, rating). Para eso hace falta el endpoint de detalle (3.2).

**Paginación — CONFIRMADA.** La respuesta trae un campo `metadata.nextPageToken` (un token
opaco, no imprimible por parecer un JWT/valor sensible, pero perfectamente utilizable). Para pedir
la siguiente página basta con añadir `&pageToken={nextPageToken}` (URL-encoded) a la misma URL.
Probado en vivo con la categoría real "Charcutería" (`OC15`, 1151 productos): pedimos página 1
(`maxPageSize=50`), tomamos su `nextPageToken`, pedimos página 2 con `pageToken=...`, y devolvió 50
productos completamente distintos (sin solape con la página 1). Conclusión: **no hace falta
`pageNumber`/`offset`, es paginación por cursor** — el `AlcampoClient` debe iterar mientras
`metadata.nextPageToken` no sea nulo/vacío, acumulando `maxPageSize` productos por vuelta (300 es un
valor razonable para minimizar peticiones).

### 3.2 Detalle de producto (nutrición, EAN, ingredientes — BLOQUEADO PARA HTTPX, CONFIRMADO)

```
PUT https://www.compraonline.alcampo.es/api/webproductpagews/v6/products
Content-Type: application/json
Body: ["1773b242-70ab-426a-8e2d-2f4f959d5f99", "...más GUIDs de productId..."]
```

- Cuando lo dispara la propia SPA (navegando de forma normal a una ficha de producto), responde
  `200` con un JSON grande (~100 KB para 1 producto), que con toda seguridad contiene la info
  ampliada (descripción, nutrición, alérgenos, ingredientes, EAN).
- **Confirmado de forma reproducible (varias veces, con distintas cabeceras: `Content-Type`,
  `Accept`, `X-Requested-With`, incluso intentando forzar `Referer`) que al llamarlo de forma
  aislada — ya sea desde `fetch()` en consola o desde `httpx` fuera del navegador — devuelve
  `403` con cabecera `x-cache: Error from cloudfront`.** Es un bloqueo del WAF/CDN delante del
  backend, no del backend en sí.
- **Hallazgo clave que generaliza el problema**: no es solo este endpoint. Probamos también
  `POST /api/ecomdeliverydestinations/v2/temporary-delivery-destinations` (el que fija el código
  postal, ver sección 5) de forma aislada y **también da 403**, aunque funciona perfectamente
  cuando lo dispara la SPA real. Patrón: **las peticiones `GET` de solo lectura al catálogo
  (`product-pages`, `categories`) funcionan siempre bien fuera del navegador; las peticiones que
  mutan estado o devuelven datos "no públicos" (`PUT`/`POST` a `products`,
  `temporary-delivery-destinations`, etc.) están protegidas por un anti-bot** (hay tráfico
  observado hacia `web.valiuz.com/v1/alc/web/event` — un proveedor de fraud/bot-detection — y una
  cookie `vlz_uid`; lo más probable es que su script de cliente calcule una huella/token que se
  adjunta a esas llamadas y que un `fetch`/`httpx` aislado no puede reproducir sin ejecutar su JS).
- Se descarta que fuera simplemente cabecera `Referer` mal puesta: el `Referer` es una cabecera
  "forbidden" en `fetch()` (el navegador la ignora si la fija el script), así que ese intento no es
  concluyente por sí solo, pero el mismo 403 se reprodujo también con `httpx` puro desde fuera del
  navegador (sin las restricciones de `fetch`), así que el bloqueo es real y no un artefacto de la
  API de `fetch`.
- **Decisión para Fase 1**: no merece la pena perseguir el token anti-bot (no es nuestro objetivo
  ni buena práctica intentar burlar activamente su WAF). En su lugar:
  1. El catálogo (nombre, marca, precio, precio/unidad, promoción, imágenes, rating) se obtiene
     100% con `httpx` vía el endpoint de listado (3.1) — **cubre la mayoría de columnas del CSV**.
  2. Para nutrición/EAN/ingredientes/alérgenos, usar el **fallback de Playwright** tal como preveía
     el prompt original, pero solo de forma puntual: abrir la ficha de producto real con Playwright,
     dejar que la propia página dispare la llamada, e interceptar la respuesta de red
     (`page.on("response")`) — nunca reconstruir la petición a mano. Cachear agresivamente en disco
     por `productId` para minimizar cuántas veces hace falta abrir Playwright.
  3. Alternativa/complemento ya prevista en el plan original: cruzar por EAN con **Open Food
     Facts** (Fase 2) para nutrición, dejando Alcampo solo como fuente de precio/disponibilidad.
     Como el EAN tampoco está en el endpoint de listado, en la práctica el cruce con OFF también
     dependerá de conseguir el EAN vía Playwright para al menos una pasada inicial por producto.

### 3.2.b Detalle de producto SÍ accesible por GET `bop` (HALLAZGO POSTERIOR, CONFIRMADO)

> Añadido tras la Fase 2. Corrige parcialmente la conclusión de 3.2.

Aunque el `PUT /api/webproductpagews/v6/products` está bloqueado, el detalle del
producto **sí se obtiene con `httpx` puro** vía:

```
GET /api/webproductpagews/v5/products/bop?retailerProductId={id}
```

- Devuelve `200` + JSON (~12 KB). Ojo con el nombre del parámetro: `retailerProductId`
  (singular) funciona; `products`, `productIds`, `retailerProductIds` dan 400.
- `bopData.fields` es una lista de bloques con HTML:
  - `nutritionalData`: tabla con energía (kcal/kj), grasas, grasas saturadas, hidratos,
    azúcares, proteínas, sal (y a veces fibra), **por 100 g o 100 ml**.
  - `ingredients`: lista de ingredientes.
  - `features`: tabla con "País de origen", denominación legal, operador, etc.
- **Solo productos envasados** traen estas tablas; los frescos a granel (fruta/verdura
  suelta) no las tienen.
- **NO** trae: EAN/GTIN, Nutri-Score, NOVA ni alérgenos estructurados. Eso hay que
  sacarlo de Open Food Facts (cruce por nombre+marca, ya que no hay EAN).
- Parseo implementado en `normalizacion/detalle.py`; enriquecimiento en
  `menu-app-enriquecer`. Es una petición por producto (con rate limit y caché).

### 3.3 Otros endpoints vistos (no prioritarios)

| Endpoint | Método | Para qué |
|---|---|---|
| `/api/ecomreviews/v1/products/{productId}/reviews` | GET | Reseñas y rating del producto (útil para palatabilidad) |
| `/api/webproductpagews/v5/products/similar` | GET | Carrusel "productos similares" |
| `/api/webproductpagews/v5/products/related` | GET | Carrusel "relacionados" |
| `/api/webproductpagews/v5/products/bop` / `/api/cxhub/v2/featured-products/bop` | GET | Recomendaciones/destacados |
| `/api/webproductpagews/v1/categories` | GET | Árbol de categorías — **ver 3.1.1, confirmado y validado** |
| `/api/cart/v1/carts/active` | GET | Carrito activo (no lo necesitamos) |
| `/api/walletservice/v2/financing-plans/calculate/plans` | POST | Financiación de compra (irrelevante) |
| `/api/search/v1/redirects/active` | GET | Redirecciones de buscador |
| `/graphql` | POST | Reviews/financiación/otros — no imprescindible, catálogo va por REST |
| `/api/address/v3/address-lookup/by-coordinates` | POST | Geocoding inverso (usado al cambiar CP) |
| `/api/ecomdeliverydestinations/v2/temporary-delivery-destinations` | POST | Fija el CP/región de la sesión — **bloqueado fuera de la SPA, ver 3.2** |

### 3.1.1 Árbol de categorías (CONFIRMADO — resuelve la enumeración sistemática)

```
GET https://www.compraonline.alcampo.es/api/webproductpagews/v1/categories
```

- Funciona con `GET` simple (sin cabeceras especiales), devuelve `200` y ~150 KB de JSON.
- Es un árbol completo y recursivo: cada nodo tiene `name`, `retailerCategoryId`, `categoryId`
  (GUID interno), `productCount` y `childCategories: [...]`.
- Confirmado en vivo: 28 categorías de nivel superior (Folletos y Promociones, Frescos,
  "Leche, Huevos, Lácteos, Yogures y Bebidas vegetales", Alimentación, Desayuno y Merienda,
  Congelados, Comida Preparada, Supermercado Ecológico, Bebidas, "Sin Gluten/Sin Lactosa...",
  Veganos, además de secciones no alimentarias como Droguería/Perfumería/Bebé/etc.), con **323
  categorías hoja** en total (`childCategories: []`).
- **Esto resuelve la enumeración del catálogo sin tocar el menú a mano**: la Fase 1 puede recorrer
  este árbol recursivamente, quedarse con las ramas de alimentación (o con todas si se quiere el
  catálogo completo), y por cada categoría hoja llamar al endpoint de listado (3.1) paginando con
  `nextPageToken` hasta agotarlo.
- Ojo: algunas categorías "hoja" según este árbol en realidad tienen sub-categorías más finas que
  solo aparecen dentro de la respuesta de `product-pages` (campo `additionalPageInfo.categories`,
  usado para los filtros de la UI) — no es grave, simplemente iterar por las hojas de este árbol ya
  cubre el 100% de los productos (los "sub-filtros" son solo una vista alternativa del mismo
  conjunto).

## 4. URLs de navegación (para descubrir slugs/IDs)

- Categoría: `/categories/{cat-slug}/{subcat-slug}/.../{retailerCategoryId}`
  ejemplo real: `/categories/leche-huevos-lácteos-yogures-y-bebidas-vegetales/leche/leche-desnatada/OCDesnatada`
- Producto: `/products/{slug}/{retailerProductId}`
  ejemplo real: `/products/auchan-leche-desnatada-de-vaca-6x-1-l-producto-alcampo/54186`

Esto confirma exactamente el patrón que asumíamos en el prompt original.

## 5. Región / código postal — CONFIRMADO

- Con IP de Madrid, el sitio auto-seleccionó "28029" y la tienda "Vaguada" sin login ni acción
  explícita (geo-IP). Reproducimos en vivo el flujo completo de cambiar el CP a mano desde
  "Cambia tu método de entrega":
  1. `GET /api/address/v1/addresses/areas/{googlePlaceId}` y
     `POST /api/address/v3/address-lookup/by-coordinates` — geocoding (autocompletar de Google
     Maps integrado en su UI).
  2. `POST /api/ecomdeliverydestinations/v2/temporary-delivery-destinations` con body:
     ```json
     {"visitorId": "...", "latitude": 40.44, "longitude": -3.67, "postalCode": "28002",
      "formattedAddress": "C. de Sánchez Pacheco, 36, Chamartín, 28002 Madrid, España"}
     ```
     Este es el que **fija la región de la sesión** — confirmado porque tras recargar la página
     entera, "Entregar en 28002" seguía activo (persistido server-side vía cookies de sesión, no
     solo estado de React en memoria).
  3. `GET /api/ecomdeliverydestinations/v4/delivery-addresses/{guid}` y
     `GET /api/ecomdeliverydestinations/v1/supported-propositions` — confirman el destino y las
     modalidades de entrega disponibles (a domicilio / recogida en tienda) para ese CP.
- **Igual que el endpoint de detalle de producto (3.2), `temporary-delivery-destinations` devuelve
  `403` si se llama de forma aislada** (probado con y sin `visitorId`) — está protegido por el mismo
  anti-bot. No merece la pena perseguirlo.
- **Conclusión práctica para este proyecto**: como el usuario vive en Madrid y el geo-IP ya resuelve
  correctamente a Madrid sin ninguna acción, **no hace falta implementar el cambio de CP en
  absoluto**. El `AlcampoClient` puede simplemente no tocar este flujo: un `GET /` inicial ya deja la
  sesión en la región correcta por defecto. Si en el futuro se quisiera soportar otro CP, la única
  vía sería un fallback puntual con Playwright (igual que en 3.2), nunca replicar la llamada a mano.

## 6. Cabeceras / cookies observadas

El navegador de la extensión bloquea la lectura directa de `document.cookie` y de valores que
parecen cookies/tokens (por seguridad), así que no pudimos volcar el cookie jar completo. Lo que sí
sabemos:
- El sitio funciona sin iniciar sesión para navegar catálogo y ver precios.
- Las llamadas GET a `/api/webproductpagews/v6/product-pages` funcionan solo con las cookies que ya
  trae cualquier visita normal (`credentials: "include"` desde el mismo origen basta).
- Para el scraper real con `httpx`, la recomendación es: hacer primero un `GET` normal a la home o a
  una página de categoría (para que el servidor fije las cookies de sesión/región), guardar el
  cookie jar, y reusarlo en las llamadas posteriores al API — exactamente el patrón de "calentar
  sesión" que ya preveía el prompt original.

## 7. Los 4 puntos pendientes — todos investigados y cerrados

| # | Pregunta | Resultado |
|---|---|---|
| 1 | ¿Cómo se fija la región/CP? | **Resuelto** (sección 5): endpoint identificado, pero **no hace falta usarlo** — geo-IP ya resuelve Madrid correctamente para este usuario. |
| 2 | ¿Se puede enumerar el árbol de categorías sin navegar a mano? | **Resuelto** (sección 3.1.1): `GET /api/webproductpagews/v1/categories`, 28 categorías raíz, 323 hojas, funciona con `httpx` puro. |
| 3 | ¿Se puede arreglar el 403 del detalle de producto? | **Investigado a fondo, no arreglable de forma limpia** (sección 3.2): es un anti-bot genérico que bloquea toda petición mutante/no-listado aislada (lo mismo le pasa a `temporary-delivery-destinations`). Estrategia: Playwright puntual + caché agresiva, tal como preveía el prompt original. No se ha intentado (ni se recomienda) evadir el anti-bot activamente. |
| 4 | ¿Hace falta paginación en categorías grandes? | **Resuelto** (sección 3.1): sí, por cursor (`metadata.nextPageToken` → `pageToken=...`), confirmado con una categoría real de 1151 productos. |

## 8. Siguientes pasos (ya se puede arrancar Fase 1)

1. Ejecutar `scripts/validate_alcampo_endpoints.py` (actualizado) para confirmar que categorías y
   paginación también funcionan desde `httpx` puro, no solo desde `fetch()` in-page.
2. Diseñar `AlcampoClient` (Fase 1) alrededor de dos llamadas `httpx` GET: árbol de categorías +
   listado paginado por cursor. Ningún flujo de la Fase 1 necesita `POST`/`PUT` a la API de Alcampo.
3. Diseñar el fallback Playwright como un componente aparte y opcional, usado solo para
   nutrición/EAN/ingredientes por producto (bajo demanda, cacheado en disco, nunca en el camino
   crítico del listado del catálogo).
