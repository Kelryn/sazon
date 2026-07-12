"""Factoria e interfaz comun del desambiguador (independiente del proveedor).

Asi el resto del codigo (matching, y mas adelante el motor de Fase 5) no depende
de si por debajo hay Gemini o Claude: solo llama a `elegir(...)`.
"""

from __future__ import annotations

from typing import Protocol


class Desambiguador(Protocol):
    modelo: str

    def elegir(self, ingrediente: str, candidatos: list[str]) -> int | None: ...


def modelo_por_defecto(proveedor: str) -> str:
    if proveedor == "gemini":
        from .cliente_gemini import MODELO_POR_DEFECTO

        return MODELO_POR_DEFECTO
    from .cliente_claude import MODELO_POR_DEFECTO

    return MODELO_POR_DEFECTO


def crear_desambiguador(proveedor: str, api_key: str, modelo: str | None = None) -> Desambiguador:
    modelo = modelo or modelo_por_defecto(proveedor)
    if proveedor == "gemini":
        from .cliente_gemini import DesambiguadorGemini

        return DesambiguadorGemini(api_key=api_key, modelo=modelo)
    if proveedor in ("anthropic", "claude"):
        from .cliente_claude import DesambiguadorClaude

        return DesambiguadorClaude(api_key=api_key, modelo=modelo)
    raise ValueError(f"Proveedor de LLM no soportado: {proveedor!r}")
