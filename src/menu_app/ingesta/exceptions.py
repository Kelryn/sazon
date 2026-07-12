class AlcampoError(Exception):
    """Error base para todo lo relacionado con el cliente de Alcampo."""


class AlcampoBlockedError(AlcampoError):
    """La peticion fue bloqueada por el anti-bot (403, x-cache: Error from cloudfront).

    Visto en DISCOVERY.md seccion 3.2: afecta a endpoints que mutan estado o
    devuelven datos "no publicos" (detalle de producto, cambio de destino de
    entrega) cuando se llaman fuera del flujo real de la SPA. No se reintenta
    automaticamente -- reintentar no lo arregla, hace falta el fallback de
    Playwright (ver playwright_fallback.py).
    """


class AlcampoAPIError(AlcampoError):
    """Respuesta HTTP inesperada (no es 200, ni 403, ni un 5xx/429 reintentable)."""
