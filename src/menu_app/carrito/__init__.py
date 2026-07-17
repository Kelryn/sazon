"""Prototipo: enviar la compra del plan al carrito de compraonline.alcampo.es.

Ver ROADMAP.md seccion D. La sesion/credenciales son SIEMPRE del usuario: el
login se hace a mano en el navegador que abre Playwright (nunca guardamos la
contrasena). Por defecto va en DRY-RUN (no toca el carrito); anadir de verdad
requiere el visto bueno explicito del usuario (--confirmar en la CLI).
"""

from __future__ import annotations

from .alcampo import (
    ResultadoCarrito,
    ResultadoLinea,
    anadir_al_carrito,
    chromium_instalado,
    instalar_chromium,
    playwright_disponible,
)

__all__ = [
    "ResultadoCarrito",
    "ResultadoLinea",
    "anadir_al_carrito",
    "chromium_instalado",
    "instalar_chromium",
    "playwright_disponible",
]
