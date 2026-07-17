"""Automatizacion del carrito de Alcampo con Playwright ASINCRONO (Via 2 del estudio).

Estrategia (ver ROADMAP.md D):
- **Sesion persistente**: se lanza Chrome/Edge con un `user_data_dir` propio bajo
  %LOCALAPPDATA%\\Sazon, para que el usuario inicie sesion UNA vez (a mano, en la
  ventana real de Alcampo) y la sesion se reutilice. La app NUNCA ve la contrasena.
- **Anadir en PARALELO**: tras el login se abre una pestaña por producto y se anaden
  TODOS a la vez (asyncio.gather, con un tope de concurrencia). Cada pestaña pulsa
  "Anadir" y sube la cantidad con el "+". Al terminar se abre la cesta y se cierran
  las pestañas de producto.
- **Captura del endpoint del carrito**: se registran las peticiones POST/PUT/PATCH al
  carrito (trolley/basket) para disenar en el futuro la Via 1 (API directa).

DRY-RUN por defecto: navega y comprueba que cada ficha tiene el control de anadir,
SIN pulsarlo. Anadir de verdad exige `dry_run=False` (la CLI lo pide con --confirmar).

Requiere el extra opcional `playwright`:
    uv sync --extra playwright
    uv run playwright install chromium
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

BASE_URL = "https://www.compraonline.alcampo.es"
LOGIN_URL = f"{BASE_URL}/login"

# UA de Chrome real (sin sufijo de bot). El anti-bot (CloudFront/Akamai) bloquea
# headless y contextos "limpios"; por eso se usa contexto PERSISTENTE + ventana.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_ARGS_NAVEGADOR = ("--disable-blink-features=AutomationControlled",)
# Primero el Chrome/Edge YA instalado (mas fiable con ventana que el Chromium
# empaquetado, que en Windows da "spawn UNKNOWN"); None = Chromium de Playwright.
_CANALES = ("chrome", "msedge", None)
_TIMEOUT_LANZAMIENTO_MS = 120_000

# Fragmentos de URL de las peticiones del carrito (OSP/Ocado) para capturar la API.
_FRAGMENTOS_CARRITO = ("/trolley", "/basket", "/cart")

# Boton de anadir: data-synthetics="add-button" (estable, independiente del idioma).
_BASES_ANADIR = (
    'button[data-synthetics="add-button"]',
    'button[aria-label^="Añadir"][aria-label*="al carrito"]',
)
# "+" para subir cantidad: aria-label "Aumentar la cantidad de {nombre} en el carrito".
_SEL_INCREMENTO = 'button[aria-label^="Aumentar la cantidad"]'
# "-" para bajar cantidad (confirmado en vivo: se uso para limpiar la cesta de prueba).
_SEL_DECREMENTO = 'button[aria-label^="Reducir la cantidad"]'
# Disparadores para ABRIR el login desde la home si la URL directa no lo muestra.
_SEL_ABRIR_LOGIN = (
    'a[href="/login"]',
    'button:has-text("Iniciar sesión")',
    'a:has-text("Iniciar sesión")',
    'button:has-text("Identifícate")',
    'button:has-text("Mi cuenta")',
)
_SEL_CAMPO_PASSWORD = 'input[type="password"]'
# "Iniciar sesion" VISIBLE -> NO hay sesion (confirmado en vivo, por texto).
_SEL_LOGIN_TRIGGER = (
    'button:has-text("Iniciar sesión")',
    'a[href="/login"]',
)
# Señal POSITIVA de sesion: boton "Mi cuenta" (logueado) vs "Iniciar sesion".
_SEL_CUENTA = (
    'button:has-text("Mi cuenta")',
    'a:has-text("Mi cuenta")',
)
# Enlace de la cesta; su aria-label lleva el total ("Carrito X,XX € - Ir a...").
_SEL_CESTA = 'a[href="/basket"]'
_URL_CESTA = f"{BASE_URL}/basket"
_DOMINIO = "compraonline.alcampo.es"

# Tope de pestañas anadiendo a la vez (0 = sin tope, TODAS a la vez, por defecto:
# validado en vivo, el anti-bot lo aguanta). Se puede limitar si hiciera falta.
_PARALELO_DEFECTO = 0


@dataclass
class ResultadoLinea:
    producto_id: str
    nombre: str
    unidades_pedidas: int
    ok: bool
    detalle: str


@dataclass
class ResultadoCarrito:
    dry_run: bool
    logueado: bool = False
    lineas: list[ResultadoLinea] = field(default_factory=list)
    endpoints_carrito: list[dict[str, Any]] = field(default_factory=list)
    botones_diagnostico: list[dict[str, str]] = field(default_factory=list)
    total_cesta: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.lineas) and all(l.ok for l in self.lineas)

    @property
    def n_ok(self) -> int:
        return sum(1 for l in self.lineas if l.ok)


def playwright_disponible() -> bool:
    """True si el extra `playwright` esta instalado."""
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def chromium_instalado() -> bool:
    """True si el Chromium PROPIO de Playwright ya esta descargado (#78). No hace
    falta si el usuario tiene Chrome/Edge (se prueban primero, ver _CANALES), pero
    sirve de respaldo hermetico sin depender del sistema."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    carpeta = Path(base) / "ms-playwright"
    return any(carpeta.glob("chromium-*")) if carpeta.exists() else False


def instalar_chromium(log: Callable[[str], None] = print) -> tuple[bool, str]:
    """Descarga el Chromium de Playwright BAJO DEMANDA (#78): solo cuando el usuario
    quiere usar el carrito y no tiene Chrome/Edge disponibles para Playwright. No
    requiere `uv`/codigo fuente: usa el propio interprete empaquetado."""
    import subprocess

    try:
        proceso = subprocess.Popen(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
        )
        for linea in proceso.stdout or []:
            log(linea.rstrip())
        codigo = proceso.wait()
    except Exception as e:  # noqa: BLE001
        return False, f"No se pudo lanzar la instalación: {e}"
    if codigo == 0 and chromium_instalado():
        return True, "Chromium instalado correctamente."
    return False, f"La instalación terminó con código {codigo}."


# --- helpers puros (sin navegador) -------------------------------------------

def _dir_navegador() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    destino = Path(base) / "Sazon" / "navegador_alcampo"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _url_producto(producto_id: str, url: str | None) -> str:
    return url or f"{BASE_URL}/products/producto/{producto_id}"


def _norm(texto: str) -> str:
    import re

    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


@dataclass
class _Linea:
    producto_id: str
    nombre: str
    url: str | None
    unidades: int


def _normalizar_lineas(lineas: Iterable[Any]) -> list[_Linea]:
    """Acepta objetos LineaCompra (optimizacion.compra) o dicts equivalentes."""
    out: list[_Linea] = []
    for l in lineas:
        if isinstance(l, dict):
            pid = str(l.get("producto_id") or l.get("retailer_product_id") or "")
            nombre = str(l.get("nombre") or "")
            url = l.get("url")
            unidades = int(l.get("unidades") or 1)
        else:
            pid = str(getattr(l, "producto_id", "") or "")
            nombre = str(getattr(l, "nombre", "") or "")
            url = getattr(l, "url", None)
            unidades = int(getattr(l, "unidades", 1) or 1)
        if pid:
            out.append(_Linea(pid, nombre, url, max(1, unidades)))
    return out


# --- helpers de navegador (async) --------------------------------------------

async def _a_primero_visible(page: Any, selectores: Iterable[str]):
    for sel in selectores:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                return sel, loc
        except Exception:  # noqa: BLE001
            continue
    return None, None


async def _a_lanzar_contexto(p: Any, user_dir: Path, headless: bool, log: Callable[[str], None]):
    """Contexto persistente probando Chrome, Edge y por ultimo el Chromium empaquetado."""
    errores: list[str] = []
    for canal in _CANALES:
        opciones: dict[str, Any] = dict(
            user_data_dir=str(user_dir),
            headless=headless,
            locale="es-ES",
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 900},
            args=list(_ARGS_NAVEGADOR),
            timeout=_TIMEOUT_LANZAMIENTO_MS,
        )
        if canal:
            opciones["channel"] = canal
        try:
            ctx = await p.chromium.launch_persistent_context(**opciones)
            log(f"Navegador: {canal or 'chromium (Playwright)'}.")
            return ctx
        except Exception as e:  # noqa: BLE001
            errores.append(f"{canal or 'chromium'}: {str(e).splitlines()[0][:120]}")
            log(f"No pude abrir {canal or 'chromium'}, pruebo el siguiente...")
    raise RuntimeError(
        "No se pudo abrir ningun navegador (Chrome/Edge/Chromium). Detalles:\n  - "
        + "\n  - ".join(errores)
    )


async def _a_esta_logueado(page: Any) -> bool:
    """Sesion iniciada <=> dominio Alcampo + aparece "Mi cuenta" (o no aparece
    "Iniciar sesion" con el header ya renderizado). Señal confirmada en vivo."""
    try:
        if _DOMINIO not in (page.url or ""):
            return False
        for sel in _SEL_CUENTA:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                return True
        if await page.locator(_SEL_CESTA).count() == 0:
            return False
        for sel in _SEL_LOGIN_TRIGGER:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


async def _a_esperar_login(page: Any, espera_login_ms: int) -> bool:
    """Sondea el login tolerando navegaciones (SSO); exige 2 lecturas seguidas."""
    paso = 2000
    transcurrido = 0
    seguidas = 0
    while transcurrido < espera_login_ms:
        ok = await _a_esta_logueado(page)
        seguidas = seguidas + 1 if ok else 0
        if seguidas >= 2:
            return True
        try:
            await page.wait_for_timeout(paso)
        except Exception:  # noqa: BLE001
            return False
        transcurrido += paso
    return False


async def _a_ir_a_login(page: Any, timeout_ms: int, log: Callable[[str], None]) -> None:
    """Deja al usuario en la pantalla de login (URL directa o abriendola desde la home)."""
    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        try:
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            return
    await page.wait_for_timeout(1000)
    try:
        if await page.locator(_SEL_CAMPO_PASSWORD).first.is_visible() or await _a_esta_logueado(page):
            return
    except Exception:  # noqa: BLE001
        pass
    _sel, boton = await _a_primero_visible(page, _SEL_ABRIR_LOGIN)
    if boton is not None:
        try:
            await boton.click(timeout=timeout_ms)
            log("Abriendo el formulario de inicio de sesion...")
        except Exception:  # noqa: BLE001
            pass


async def _a_aria_cesta(page: Any) -> str:
    try:
        return await page.locator(_SEL_CESTA).first.get_attribute("aria-label") or ""
    except Exception:  # noqa: BLE001
        return ""


async def _a_leer_total_cesta(page: Any) -> str | None:
    import re

    m = re.search(r"([\d.,]+)\s*€", await _a_aria_cesta(page))
    return m.group(0) if m else None


async def _a_localizar_anadir(page: Any, nombre: str):
    """Boton de anadir del producto principal. Exige aria-label que empiece por
    'Añadir' (descarta el boton de la IMAGEN, que tambien lleva el nombre) y filtra
    por el NOMBRE del producto (descarta el carrusel de recomendados)."""
    nucleo = _norm(nombre)
    for base in _BASES_ANADIR:
        try:
            botones = page.locator(base)
            total = await botones.count()
            primero = None
            for i in range(min(total, 60)):
                b = botones.nth(i)
                try:
                    if not await b.is_visible():
                        continue
                    al = _norm(await b.get_attribute("aria-label") or "")
                except Exception:  # noqa: BLE001
                    continue
                if nucleo and nucleo in al:
                    return base, b
                if primero is None:
                    primero = b
            if primero is not None:
                return base, primero
        except Exception:  # noqa: BLE001
            continue
    return None, None


async def _a_localizar_por_selector(page: Any, selector: str, nombre: str):
    """Localiza, entre los botones que casan `selector`, el del producto `nombre`
    (por su aria-label) o el primero visible si no hay coincidencia exacta."""
    try:
        botones = page.locator(selector)
        total = await botones.count()
        nucleo = _norm(nombre)
        primero = None
        for i in range(min(total, 60)):
            b = botones.nth(i)
            try:
                if not await b.is_visible():
                    continue
                al = _norm(await b.get_attribute("aria-label") or "")
            except Exception:  # noqa: BLE001
                continue
            if nucleo and nucleo in al:
                return b
            if primero is None:
                primero = b
        return primero
    except Exception:  # noqa: BLE001
        return None


async def _a_localizar_incremento(page: Any, nombre: str):
    return await _a_localizar_por_selector(page, _SEL_INCREMENTO, nombre)


async def _a_localizar_decremento(page: Any, nombre: str):
    return await _a_localizar_por_selector(page, _SEL_DECREMENTO, nombre)


_JS_BOTONES = """
() => Array.from(document.querySelectorAll('button, [role=button]'))
  .filter(el => el.offsetParent !== null).slice(0, 60)
  .map(el => ({
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || '').trim().slice(0, 40),
    aria: el.getAttribute('aria-label') || '',
    testid: el.getAttribute('data-test') || el.getAttribute('data-synthetics') || '',
  }))
"""


async def _a_diagnostico_botones(page: Any) -> list[dict[str, str]]:
    try:
        return await page.evaluate(_JS_BOTONES) or []
    except Exception:  # noqa: BLE001
        return []


async def _a_sincronizar_cantidad(page: Any, it: _Linea, timeout_ms: int) -> int:
    """Reduce a 0 la cantidad ya en la cesta de `it` (clic en '-' hasta que
    reaparece el boton de anadir), para luego reponer la cantidad EXACTA pedida en
    vez de sumar sobre lo que hubiera (#54). Devuelve el nº de clics de reduccion
    aplicados (informativo)."""
    clics = 0
    for _ in range(60):  # cota de seguridad; el stepper normal no pasa de unas pocas unidades
        dec = await _a_localizar_decremento(page, it.nombre)
        if dec is None:
            break
        try:
            await dec.click(timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            break
        clics += 1
        try:
            await page.wait_for_timeout(300)  # deja que la SPA actualice el stepper
        except Exception:  # noqa: BLE001
            pass
    return clics


async def _a_procesar_linea(
    page: Any, it: _Linea, *, dry_run: bool, timeout_ms: int,
    sincronizar: bool = False, log: Callable[[str], None] = print,
) -> ResultadoLinea:
    url = _url_producto(it.producto_id, it.url)
    etiqueta = f"{it.nombre or it.producto_id} (x{it.unidades})"
    # goto con reintento (la SPA puede seguir navegando tras el SSO y abortar la carga).
    ultimo_error = ""
    for intento in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            ultimo_error = ""
            break
        except Exception as e:  # noqa: BLE001
            ultimo_error = str(e).splitlines()[0]
            if "interrupted by another navigation" in ultimo_error and intento < 2:
                await page.wait_for_timeout(1500)
                continue
            break
    if ultimo_error:
        log(f"  ✗ {etiqueta}: no cargo la ficha ({ultimo_error})")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, "ficha no cargo")

    # Espera por EVENTO a que aparezca el control (boton de anadir o stepper).
    try:
        await page.wait_for_selector(
            'button[data-synthetics="add-button"], ' + _SEL_INCREMENTO, timeout=15_000
        )
    except Exception:  # noqa: BLE001
        pass

    sel, boton = await _a_localizar_anadir(page, it.nombre)
    if boton is None:
        if await _a_localizar_incremento(page, it.nombre) is not None:
            if not sincronizar:
                log(f"  ✓ {etiqueta}: ya estaba en la cesta (sumando encima)")
                return ResultadoLinea(it.producto_id, it.nombre, it.unidades, True, "ya en la cesta")
            # Sincronizar (#54): vaciar esta linea y reponer la cantidad EXACTA, en
            # vez de sumar sobre lo que hubiera ya en el carrito.
            clics = await _a_sincronizar_cantidad(page, it, timeout_ms)
            sel, boton = await _a_localizar_anadir(page, it.nombre)
            if boton is None:
                log(f"  ✗ {etiqueta}: no reaparecio el boton de anadir tras vaciar ({clics} clics)")
                return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, "error sincronizando")
        else:
            log(f"  ✗ {etiqueta}: no encontre boton de anadir")
            return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, "sin boton de anadir")

    # ¿Agotado / deshabilitado? (aria-disabled o texto "Agotado").
    try:
        agotado = (
            await boton.get_attribute("aria-disabled") == "true"
            or "agotado" in _norm(await boton.inner_text() or "")
            or not await boton.is_enabled()
        )
    except Exception:  # noqa: BLE001
        agotado = False
    if agotado:
        log(f"  ⊘ {etiqueta}: AGOTADO / no disponible en Alcampo")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, "agotado")

    if dry_run:
        log(f"  ✓ {etiqueta}: boton de anadir OK [{sel}] (dry-run)")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, True, "dry-run")

    try:
        await boton.click(timeout=timeout_ms)
        # Espera a que aparezca el stepper de ESTE producto (confirma el +1). En
        # paralelo no vale mirar el total de la cesta (lo cambian otras pestañas).
        try:
            await page.wait_for_selector(_SEL_INCREMENTO, timeout=10_000)
        except Exception:  # noqa: BLE001
            pass
        anadidas = 1
        for _ in range(it.unidades - 1):
            inc = await _a_localizar_incremento(page, it.nombre)
            if inc is None:
                break
            try:
                await inc.click(timeout=timeout_ms)  # actionability de Playwright pauta el ritmo
            except Exception:  # noqa: BLE001
                break
            anadidas += 1
        ok = anadidas >= 1
        detalle = f"anadidas {anadidas}/{it.unidades} [{sel}]"
        log(f"  {'✓' if ok else '✗'} {etiqueta}: {detalle}")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, ok, detalle)
    except Exception as e:  # noqa: BLE001
        log(f"  ✗ {etiqueta}: fallo al anadir ({str(e).splitlines()[0]})")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, "error")


# --- orquestacion ------------------------------------------------------------

async def _a_vaciar_carrito(page: Any, timeout_ms: int, log: Callable[[str], None]) -> int:
    """Vacia la cesta por completo (#55): en /basket, pulsa "-" repetidamente sobre
    CUALQUIER producto visible hasta que no queda ninguno. Best-effort, acotado."""
    try:
        await page.goto(_URL_CESTA, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        return 0
    clics = 0
    for _ in range(500):  # cota de seguridad (cestas normales no llegan a esto)
        try:
            dec = page.locator(_SEL_DECREMENTO).first
            if await dec.count() == 0 or not await dec.is_visible():
                break
            await dec.click(timeout=timeout_ms)
            clics += 1
            await page.wait_for_timeout(250)
        except Exception:  # noqa: BLE001
            break
    return clics


async def _anadir_async(
    items: list[_Linea],
    *,
    dry_run: bool,
    headless: bool,
    timeout_ms: int,
    espera_login_ms: int,
    diagnostico: bool,
    mantener_abierto_ms: int,
    esperar_enter: bool,
    paralelo: int,
    sincronizar: bool,
    vaciar_antes: bool,
    log: Callable[[str], None],
) -> ResultadoCarrito:
    from playwright.async_api import async_playwright

    res = ResultadoCarrito(dry_run=dry_run)
    user_dir = _dir_navegador()
    async with async_playwright() as p:
        ctx = await _a_lanzar_contexto(p, user_dir, headless, log)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            def _on_request(req: Any) -> None:
                if req.method in ("POST", "PUT", "PATCH") and any(
                    f in req.url for f in _FRAGMENTOS_CARRITO
                ):
                    entrada: dict[str, Any] = {"metodo": req.method, "url": req.url}
                    try:
                        entrada["cuerpo"] = req.post_data
                    except Exception:  # noqa: BLE001
                        pass
                    res.endpoints_carrito.append(entrada)

            ctx.on("request", _on_request)

            # 1) Sesion (login manual del usuario; auto-deteccion sin ENTER).
            await _a_ir_a_login(page, timeout_ms, log)
            if await _a_esta_logueado(page):
                res.logueado = True
                log("Ya habia sesion iniciada. Continuo.")
            elif esperar_enter and sys.stdin is not None and sys.stdin.isatty():
                log("Inicia sesion en la ventana y pon tu codigo postal de entrega.")
                try:
                    input(">>> Cuando hayas iniciado sesion, pulsa ENTER para continuar... ")
                except EOFError:
                    pass
                res.logueado = True
            else:
                log(
                    "Inicia sesion en la ventana; continuo yo solo en cuanto lo detecte "
                    f"(hasta {espera_login_ms // 1000}s)..."
                )
                res.logueado = await _a_esperar_login(page, espera_login_ms)
                if res.logueado:
                    log("Sesion detectada. Continuo.")
                elif not dry_run:
                    log("No se detecto sesion. Aborto sin tocar el carrito.")
                    return res

            if res.logueado:
                try:
                    await page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass

            # Diagnostico opcional: vuelca los botones del primer producto.
            if diagnostico and items:
                tab = await ctx.new_page()
                try:
                    await tab.goto(_url_producto(items[0].producto_id, items[0].url),
                                   wait_until="domcontentloaded", timeout=timeout_ms)
                    await tab.wait_for_selector('button[data-synthetics="add-button"]',
                                                timeout=timeout_ms)
                    res.botones_diagnostico = await _a_diagnostico_botones(tab)
                    log(f"Diagnostico: {len(res.botones_diagnostico)} botones en {items[0].nombre}")
                except Exception as e:  # noqa: BLE001
                    log(f"Diagnostico fallido: {e}")
                finally:
                    await tab.close()

            # 1.5) Vaciar la cesta ANTES de anadir (#55), si se pidio.
            if vaciar_antes and not dry_run and res.logueado:
                vaciados = await _a_vaciar_carrito(page, timeout_ms, log)
                log(f"Cesta vaciada: {vaciados} unidades quitadas.")

            # 2) PARALELO: abrir una pestaña por producto y anadir TODOS a la vez.
            tope = paralelo if paralelo and paralelo > 0 else len(items)
            sem = asyncio.Semaphore(max(1, tope))
            log(
                f"Anadiendo {len(items)} productos en paralelo"
                + (f" (hasta {tope} a la vez)..." if tope < len(items) else " (todos a la vez)...")
            )

            async def _tarea(it: _Linea):
                async with sem:
                    tab = await ctx.new_page()
                    linea = await _a_procesar_linea(
                        tab, it, dry_run=dry_run, timeout_ms=timeout_ms,
                        sincronizar=sincronizar, log=log,
                    )
                    # Reintento inteligente (#60): solo para fallos TRANSITORIOS (red/
                    # navegacion), no para agotado/sin-boton (esos no mejoran reintentando).
                    if not linea.ok and linea.detalle in ("ficha no cargo", "error"):
                        log(f"  ↻ {it.nombre or it.producto_id}: reintento tras fallo transitorio...")
                        linea = await _a_procesar_linea(
                            tab, it, dry_run=dry_run, timeout_ms=timeout_ms,
                            sincronizar=sincronizar, log=log,
                        )
                    return tab, linea

            resultados = await asyncio.gather(*[_tarea(it) for it in items])
            tabs = [t for t, _ in resultados]
            res.lineas = [linea for _, linea in resultados]

            # 3) Abrir la cesta (pestaña inicial) y cerrar las de producto.
            if not dry_run:
                try:
                    await page.goto(_URL_CESTA, wait_until="domcontentloaded", timeout=timeout_ms)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    except Exception:  # noqa: BLE001
                        pass
                except Exception:  # noqa: BLE001
                    pass
                res.total_cesta = await _a_leer_total_cesta(page)
                if res.total_cesta:
                    log(f"Total de la cesta: {res.total_cesta}")
                try:
                    await page.bring_to_front()
                except Exception:  # noqa: BLE001
                    pass
            for tab in tabs:
                try:
                    await tab.close()
                except Exception:  # noqa: BLE001
                    pass
            if not dry_run:
                log("Cesta abierta con todos los productos; cerradas las pestañas de producto.")

            if mantener_abierto_ms > 0:
                try:
                    await page.wait_for_timeout(mantener_abierto_ms)
                except Exception:  # noqa: BLE001
                    pass
            elif not dry_run:
                log(
                    "Cesta lista en /basket. Te dejo el navegador ABIERTO para revisar y "
                    "pagar; cierra la ventana cuando termines."
                )
                try:
                    await page.wait_for_event("close", timeout=0)
                except Exception:  # noqa: BLE001
                    pass
        finally:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001
                pass
    return res


def anadir_al_carrito(
    lineas: Iterable[Any],
    *,
    dry_run: bool = True,
    headless: bool = False,
    timeout_ms: int = 30_000,
    espera_login_ms: int = 180_000,
    limite: int | None = None,
    diagnostico: bool = False,
    mantener_abierto_ms: int = 0,
    esperar_enter: bool = False,
    paralelo: int = _PARALELO_DEFECTO,
    sincronizar: bool = False,
    vaciar_antes: bool = False,
    log: Callable[[str], None] = print,
) -> ResultadoCarrito:
    """Abre Alcampo con sesion persistente y anade (en PARALELO) la compra.

    - `lineas`: LineaCompra (optimizacion.compra) o dicts con producto_id/nombre/url/unidades.
    - `dry_run=True`: solo comprueba el boton de anadir; NO toca el carrito.
    - `paralelo`: nº maximo de productos anadiendose a la vez (0 = todos a la vez).
    - `sincronizar` (#54): si un producto ya esta en la cesta, lo ajusta a la cantidad
      EXACTA pedida (vacia y repone) en vez de sumar por encima.
    - `vaciar_antes` (#55): vacia la cesta entera antes de empezar a anadir.
    - `headless=False`: ventana visible (necesaria para el login manual).
    """
    items = _normalizar_lineas(lineas)
    if limite is not None and limite > 0:
        items = items[:limite]
    if not items:
        log("No hay lineas de compra que anadir.")
        return ResultadoCarrito(dry_run=dry_run)
    return asyncio.run(
        _anadir_async(
            items,
            dry_run=dry_run,
            headless=headless,
            timeout_ms=timeout_ms,
            espera_login_ms=espera_login_ms,
            diagnostico=diagnostico,
            mantener_abierto_ms=mantener_abierto_ms,
            esperar_enter=esperar_enter,
            paralelo=paralelo,
            sincronizar=sincronizar,
            vaciar_antes=vaciar_antes,
            log=log,
        )
    )
