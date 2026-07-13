"""Automatizacion del carrito de Alcampo con Playwright (Via 2 del estudio).

Estrategia (ver ROADMAP.md D):
- **Sesion persistente**: se lanza Chromium con un `user_data_dir` propio bajo
  %LOCALAPPDATA%\\Sazon, para que el usuario inicie sesion UNA vez (a mano, en la
  ventana real de Alcampo) y la sesion se reutilice en ejecuciones posteriores.
  La app NUNCA ve ni guarda la contrasena.
- **Anadir por UI**: por cada linea de la compra se abre la ficha del producto y
  se pulsa "Anadir", subiendo la cantidad hasta las unidades pedidas. Es mas lento
  que la API pero resistente a cambios de endpoint y al anti-bot (lo dispara la
  propia web).
- **Captura del endpoint del carrito**: en paralelo se registran las peticiones
  POST/PUT/PATCH al carrito (trolley/basket) para poder disenar en el futuro la
  Via 1 (API directa con `httpx` reutilizando las cookies), mas eficiente.

DRY-RUN por defecto: navega y comprueba que cada ficha tiene el control de anadir,
SIN pulsarlo. Anadir de verdad exige `dry_run=False` (la CLI lo pide con --confirmar).

Requiere el extra opcional `playwright`:
    uv sync --extra playwright
    uv run playwright install chromium
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

BASE_URL = "https://www.compraonline.alcampo.es"
# Pagina de inicio de sesion (OSP). Si la ruta cambiara, el flujo cae a abrir el
# login desde la home pulsando el boton de cuenta.
LOGIN_URL = f"{BASE_URL}/login"

# UA de Chrome real (sin sufijo de bot): en el flujo del carrito queremos parecer
# el navegador del propio usuario. El anti-bot (CloudFront/Akamai) bloquea headless
# y contextos "limpios"; por eso se usa contexto PERSISTENTE + ventana + login real.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Reduce la huella de automatizacion (navigator.webdriver, etc.).
_ARGS_NAVEGADOR = ("--disable-blink-features=AutomationControlled",)

# Navegadores a probar, en orden: primero el Chrome/Edge YA instalado del usuario
# (mas fiable en modo ventana que el Chromium empaquetado, que en algunas maquinas
# Windows da "spawn UNKNOWN"/timeout al abrir con ventana); None = Chromium de
# Playwright como ultimo recurso.
_CANALES = ("chrome", "msedge", None)
# El primer arranque con ventana puede tardar (antivirus escaneando el .exe): damos
# margen amplio al lanzamiento para no fallar por timeout (30s por defecto).
_TIMEOUT_LANZAMIENTO_MS = 120_000

# Fragmentos de URL de las peticiones del carrito de la plataforma OSP (Ocado).
# Se vigilan para capturar la forma de la API (Via 1) sin reconstruirla a mano.
_FRAGMENTOS_CARRITO = ("/trolley", "/basket", "/cart")

# Selectores del boton "Anadir" (confirmado en vivo: el boton real es
# <button aria-label="Añadir {producto} al carrito">Añadir</button>). OJO: la ficha
# tiene MUCHOS botones "Añadir" (carrusel de productos recomendados), por eso lo
# ideal es apuntar por el NOMBRE del producto (ver _localizar_anadir); estos son el
# respaldo generico. El principal suele ser el primero del DOM.
_SEL_ANADIR = (
    'button[aria-label^="Añadir"][aria-label*="al carrito" i]',
    'button[aria-label*="Añadir" i][aria-label*="carrito" i]',
    'button[aria-label*="Añadir" i]',
    'button:has-text("Añadir")',
)
# Selectores del "+" para subir cantidad una vez anadido.
_SEL_INCREMENTO = (
    '[data-testid="increment"]',
    'button[aria-label*="Aumentar" i]',
    'button[aria-label*="Increase" i]',
    'button[aria-label*="más" i]',
    'button:has-text("+")',
)
# Disparadores para ABRIR el formulario de login desde la home (si la URL directa
# no muestra ya el formulario).
_SEL_ABRIR_LOGIN = (
    'a[href*="login" i]',
    'a[href*="identif" i]',
    'button:has-text("Iniciar sesión")',
    'a:has-text("Iniciar sesión")',
    'button:has-text("Identifícate")',
    'a:has-text("Identifícate")',
    'button:has-text("Mi cuenta")',
    'button[aria-label*="cuenta" i]',
)
# Campo de contrasena: si esta visible, ya estamos en la pantalla de login.
_SEL_CAMPO_PASSWORD = 'input[type="password"]'

# Disparador de "Iniciar sesion" (confirmado en vivo en el Chrome del usuario: es un
# boton/enlace por TEXTO, sin data-testid). Si es VISIBLE -> NO hay sesion.
_SEL_LOGIN_TRIGGER = (
    'button:has-text("Iniciar sesión")',
    'a[href="/login"]',
    'a:has-text("Iniciar sesión")',
)
# Enlace de la CESTA (siempre presente; su aria-label lleva el total: "Carrito X,XX €
# - Ir a la pagina del carrito"). Sirve para (1) saber que el header ya renderizo y
# (2) verificar que un producto se anadio (el total sube).
_SEL_CESTA = 'a[href="/basket"]'
_URL_CESTA = f"{BASE_URL}/basket"
_URL_PAGO = f"{BASE_URL}/checkout"
_DOMINIO = "compraonline.alcampo.es"


@dataclass
class ResultadoLinea:
    producto_id: str
    nombre: str
    unidades_pedidas: int
    ok: bool
    detalle: str  # que paso: selector usado, unidades anadidas, o el error


@dataclass
class ResultadoCarrito:
    dry_run: bool
    logueado: bool = False
    lineas: list[ResultadoLinea] = field(default_factory=list)
    endpoints_carrito: list[dict[str, Any]] = field(default_factory=list)
    # Diagnostico: botones visibles del primer producto (para afinar selectores).
    botones_diagnostico: list[dict[str, str]] = field(default_factory=list)
    total_cesta: str | None = None  # total leido de la cesta al terminar (ej. "12,34 €")

    @property
    def ok(self) -> bool:
        return bool(self.lineas) and all(l.ok for l in self.lineas)

    @property
    def n_ok(self) -> int:
        return sum(1 for l in self.lineas if l.ok)


def playwright_disponible() -> bool:
    """True si el extra `playwright` esta instalado y con Chromium disponible."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _lanzar_contexto(p: Any, user_dir: Path, headless: bool, log: Callable[[str], None]):
    """Lanza un contexto persistente probando Chrome, Edge y por ultimo el Chromium
    empaquetado. Devuelve el contexto o lanza el ultimo error con un mensaje claro."""
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
            ctx = p.chromium.launch_persistent_context(**opciones)
            log(f"Navegador: {canal or 'chromium (Playwright)'}.")
            return ctx
        except Exception as e:  # noqa: BLE001 - probamos el siguiente navegador
            nombre = canal or "chromium"
            errores.append(f"{nombre}: {str(e).splitlines()[0][:120]}")
            log(f"No pude abrir {nombre}, pruebo el siguiente...")
    raise RuntimeError(
        "No se pudo abrir ningun navegador (Chrome/Edge/Chromium). Detalles:\n  - "
        + "\n  - ".join(errores)
    )


def _dir_navegador() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    destino = Path(base) / "Sazon" / "navegador_alcampo"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _url_producto(producto_id: str, url: str | None) -> str:
    if url:
        return url
    return f"{BASE_URL}/products/producto/{producto_id}"


def _primero_visible(page: Any, selectores: Iterable[str]):
    """Devuelve (selector, locator) del primer selector con un elemento visible."""
    for sel in selectores:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return sel, loc
        except Exception:  # noqa: BLE001 - selector no valido en esta pagina
            continue
    return None, None


def _localizar_anadir(page: Any, nombre: str):
    """Localiza EL boton de anadir del producto principal, evitando los del carrusel
    de recomendados. Prioriza el que lleva el NOMBRE del producto en su aria-label
    (`Añadir {nombre} al carrito`); si no, cae al primer boton de anadir del DOM."""
    if nombre:
        try:
            loc = page.get_by_role("button", name=nombre).first
            if loc.count() > 0 and loc.is_visible():
                return "por-nombre", loc
        except Exception:  # noqa: BLE001 - nombre con caracteres raros, etc.
            pass
    return _primero_visible(page, _SEL_ANADIR)


def _esta_logueado(page: Any) -> bool:
    """Sesion iniciada <=> estamos en el dominio de Alcampo, el header ya renderizo
    (enlace de cesta presente) y NO se ve el disparador de "Iniciar sesion".
    Señal confirmada en vivo, sin conjeturas ni data-testids inexistentes."""
    try:
        if _DOMINIO not in (page.url or ""):
            return False  # aun en el SSO (my.site.com) u otra pagina
        if page.locator(_SEL_CESTA).count() == 0:
            return False  # header no renderizado todavia: evita falsos positivos
        for sel in _SEL_LOGIN_TRIGGER:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return False  # sigue mostrando "Iniciar sesion" -> no logueado
        return True
    except Exception:  # noqa: BLE001 - navegando; se reintenta fuera
        return False


def _leer_total_cesta(page: Any) -> str | None:
    """Total de la cesta desde el aria-label del enlace /basket ('Carrito 12,34 €...')."""
    try:
        aria = page.locator(_SEL_CESTA).first.get_attribute("aria-label") or ""
        import re

        m = re.search(r"([\d.,]+)\s*€", aria)
        return m.group(0) if m else None
    except Exception:  # noqa: BLE001
        return None


def _ir_a_login(page: Any, timeout_ms: int, log: Callable[[str], None]) -> None:
    """Deja al usuario en la pantalla de inicio de sesion: prueba la URL directa y,
    si no aparece el campo de contrasena, abre el login desde la home."""
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            return
    page.wait_for_timeout(1200)
    # Si ya se ve el campo de contrasena o ya hay sesion, no hay nada mas que hacer.
    try:
        if page.locator(_SEL_CAMPO_PASSWORD).first.is_visible() or _esta_logueado(page):
            return
    except Exception:  # noqa: BLE001
        pass
    # Si no, intenta abrir el formulario desde la home.
    if page.url.rstrip("/") != LOGIN_URL:
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
    _sel, boton = _primero_visible(page, _SEL_ABRIR_LOGIN)
    if boton is not None:
        try:
            boton.click(timeout=timeout_ms)
            log("Abriendo el formulario de inicio de sesion...")
        except Exception:  # noqa: BLE001
            pass


def _esperar_login(page: Any, espera_login_ms: int, log: Callable[[str], None]) -> bool:
    """Sondea si el usuario ha iniciado sesion, TOLERANDO navegaciones y recargas
    (al hacer login la SPA recarga y destruye el contexto de ejecucion, lo que hacia
    fallar a wait_for_selector). Nunca lanza: devuelve True si detecta sesion, o False
    si se agota el tiempo o la ventana se cierra."""
    paso = 2000
    transcurrido = 0
    seguidas = 0  # exige 2 lecturas seguidas para evitar falsos positivos al cargar
    while transcurrido < espera_login_ms:
        ok = False
        try:
            ok = _esta_logueado(page)
        except Exception:  # noqa: BLE001 - la pagina puede estar navegando; reintenta
            ok = False
        seguidas = seguidas + 1 if ok else 0
        if seguidas >= 2:
            return True
        try:
            page.wait_for_timeout(paso)
        except Exception:  # noqa: BLE001 - ventana cerrada u otro problema: salimos
            return False
        transcurrido += paso
    return False


# JS que vuelca los botones VISIBLES de la ficha con sus atributos: sirve para
# identificar el control real de "Anadir"/"+" cuando los selectores no casan.
_JS_BOTONES = """
() => Array.from(document.querySelectorAll('button, [role=button], a[href*="trolley"]'))
  .filter(el => el.offsetParent !== null)
  .slice(0, 60)
  .map(el => ({
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || '').trim().slice(0, 40),
    aria: el.getAttribute('aria-label') || '',
    testid: el.getAttribute('data-testid') || '',
    cls: (el.className || '').toString().slice(0, 60),
  }))
"""


def diagnostico_botones(page: Any) -> list[dict[str, str]]:
    """Lista los botones visibles de la pagina actual (para afinar selectores)."""
    try:
        return page.evaluate(_JS_BOTONES) or []
    except Exception:  # noqa: BLE001
        return []


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
    log: Callable[[str], None] = print,
) -> ResultadoCarrito:
    """Abre Alcampo con sesion persistente y anade (o comprueba, en dry-run) la compra.

    - `lineas`: iterable de LineaCompra (o dicts con producto_id/nombre/url/unidades).
    - `dry_run=True` (por defecto): solo comprueba que cada ficha tiene boton de
      anadir; NO toca el carrito.
    - `headless=False`: ventana visible (necesaria para el login manual la 1a vez).
    - `espera_login_ms`: cuanto espera a que el usuario inicie sesion si aun no lo esta.
    """
    from playwright.sync_api import sync_playwright

    items = _normalizar_lineas(lineas)
    if limite is not None and limite > 0:
        items = items[:limite]
    res = ResultadoCarrito(dry_run=dry_run)
    if not items:
        log("No hay lineas de compra que anadir.")
        return res

    user_dir = _dir_navegador()
    with sync_playwright() as p:
        ctx = _lanzar_contexto(p, user_dir, headless, log)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # Captura de peticiones al carrito (para disenar la Via 1/API mas adelante).
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

            page.on("request", _on_request)

            # 1) Sesion. La inicia el usuario a mano (nunca guardamos la contrasena).
            # Le llevamos directo al formulario de login para que no tenga que buscarlo.
            _ir_a_login(page, timeout_ms, log)
            if _esta_logueado(page):
                res.logueado = True
                log("Ya habia sesion iniciada. Continuo.")
            elif esperar_enter and sys.stdin is not None and sys.stdin.isatty():
                # Opcional: el usuario confirma con ENTER (para casos raros de deteccion).
                log("Inicia sesion en la ventana y pon tu codigo postal de entrega.")
                try:
                    input(">>> Cuando hayas iniciado sesion, pulsa ENTER aqui para continuar... ")
                except EOFError:
                    pass
                res.logueado = True
            else:
                # Auto-deteccion FIABLE (sin ENTER): detecto cuando desaparece el boton
                # "Iniciar sesion" y vuelves al dominio de Alcampo tras el SSO.
                log(
                    "Inicia sesion en la ventana y pon tu codigo postal de entrega; "
                    f"continuo yo solo en cuanto lo detecte (hasta {espera_login_ms // 1000}s)..."
                )
                res.logueado = _esperar_login(page, espera_login_ms, log)
                if res.logueado:
                    log("Sesion detectada. Continuo.")
                elif not dry_run:
                    log("No se detecto sesion. Aborto sin tocar el carrito.")
                    return res

            # Tras el login (SSO con redirecciones): espera a que la pagina se asiente
            # antes de navegar, para no chocar con una navegacion en curso.
            if res.logueado:
                try:
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass

            # 2) Por cada linea: abrir ficha y anadir (o comprobar en dry-run).
            for idx, it in enumerate(items):
                if diagnostico and idx == 0:
                    url = _url_producto(it.producto_id, it.url)
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                        page.wait_for_timeout(1500)  # deja que la SPA pinte los botones
                        res.botones_diagnostico = diagnostico_botones(page)
                        log(f"Diagnostico: {len(res.botones_diagnostico)} botones visibles en {it.nombre}")
                    except Exception as e:  # noqa: BLE001
                        log(f"Diagnostico fallido: {e}")
                res.lineas.append(
                    _procesar_linea(page, it, dry_run=dry_run, timeout_ms=timeout_ms, log=log)
                )

            # 3) Cierre: si hemos anadido de verdad, llevamos a la CESTA y dejamos el
            # navegador abierto para que el usuario revise y pague (no cerramos solos).
            if not dry_run:
                try:
                    page.goto(_URL_CESTA, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(1500)
                except Exception:  # noqa: BLE001
                    pass
                res.total_cesta = _leer_total_cesta(page)
                if res.total_cesta:
                    log(f"Total de la cesta: {res.total_cesta}")

            if mantener_abierto_ms > 0:
                log(f"Dejo la ventana abierta {mantener_abierto_ms // 1000}s...")
                try:
                    page.wait_for_timeout(mantener_abierto_ms)
                except Exception:  # noqa: BLE001
                    pass
            elif not dry_run:
                log(
                    "Cesta lista en /basket. Te dejo el navegador ABIERTO para que revises "
                    "y completes el pago; cierra la ventana cuando termines."
                )
                try:
                    page.wait_for_event("close", timeout=0)  # espera a que cierres la ventana
                except Exception:  # noqa: BLE001
                    pass
        finally:
            try:
                ctx.close()
            except Exception:  # noqa: BLE001 - ya cerrado por el usuario
                pass

    return res


def _procesar_linea(
    page: Any, it: _Linea, *, dry_run: bool, timeout_ms: int, log: Callable[[str], None]
) -> ResultadoLinea:
    url = _url_producto(it.producto_id, it.url)
    etiqueta = f"{it.nombre or it.producto_id} (x{it.unidades})"
    # goto con reintento: al volver del SSO la SPA puede seguir navegando y abortar
    # la carga ("interrupted by another navigation"); reintentamos tras asentarse.
    ultimo_error = ""
    for intento in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            ultimo_error = ""
            break
        except Exception as e:  # noqa: BLE001
            ultimo_error = str(e).splitlines()[0]
            if "interrupted by another navigation" in ultimo_error and intento < 2:
                page.wait_for_timeout(2000)
                continue
            break
    if ultimo_error:
        log(f"  ✗ {etiqueta}: no cargo la ficha ({ultimo_error})")
        return ResultadoLinea(
            it.producto_id, it.nombre, it.unidades, False, f"ficha no cargo: {ultimo_error}"
        )

    # Deja que la SPA pinte el boton de anadir tras cargar la ficha.
    page.wait_for_timeout(1200)
    sel, boton = _localizar_anadir(page, it.nombre)
    if boton is None:
        log(f"  ✗ {etiqueta}: no encontre boton de anadir")
        return ResultadoLinea(
            it.producto_id, it.nombre, it.unidades, False, "sin boton de anadir"
        )

    if dry_run:
        log(f"  ✓ {etiqueta}: boton de anadir OK [{sel}] (dry-run, no se anade)")
        return ResultadoLinea(
            it.producto_id, it.nombre, it.unidades, True, f"dry-run; boton [{sel}]"
        )

    try:
        boton.click(timeout=timeout_ms)
        anadidas = 1
        # Subir a las unidades pedidas con el "+".
        for _ in range(it.unidades - 1):
            isel, inc = _primero_visible(page, _SEL_INCREMENTO)
            if inc is None:
                break
            inc.click(timeout=timeout_ms)
            anadidas += 1
        detalle = f"anadidas {anadidas}/{it.unidades} [{sel}]"
        ok = anadidas >= 1
        log(f"  {'✓' if ok else '✗'} {etiqueta}: {detalle}")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, ok, detalle)
    except Exception as e:  # noqa: BLE001
        log(f"  ✗ {etiqueta}: fallo al anadir ({e})")
        return ResultadoLinea(it.producto_id, it.nombre, it.unidades, False, f"error: {e}")
