"""Desambiguador de matching con Gemini (Google), la etapa final del embudo Fase 4.

Misma tarea e interfaz que el desambiguador de Claude: dado un ingrediente y una
lista de productos candidatos, elige el correcto o indica que ninguno sirve. Se
usa Gemini porque tiene una capa gratuita en Google AI Studio.

Se pide salida JSON con response_schema (structured output). Para evitar
problemas con esquemas 'nullable', se usa -1 como valor centinela de "ninguno".
"""

from __future__ import annotations

import json
import logging
import time

from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

_MAX_REINTENTOS = 4

MODELO_POR_DEFECTO = "gemini-2.5-flash-lite"

_SYSTEM = (
    "Eres un experto en la compra de supermercado. Recibes un INGREDIENTE de una "
    "receta y una lista numerada de PRODUCTOS candidatos de un supermercado. "
    "Elige el producto que hay que comprar para ese ingrediente, o indica que "
    "ninguno sirve.\n"
    "Reglas:\n"
    "- Prefiere el producto que ES ese ingrediente en su forma basica (para "
    "'sal' elige la sal de mesa, NO 'mantequilla sin sal' aunque contenga la "
    "palabra 'sal'; para 'aceite de oliva' elige el aceite, NO unas anchoas en "
    "aceite de oliva).\n"
    "- Evita platos preparados, snacks o productos que solo mencionan el "
    "ingrediente como parte de otra cosa.\n"
    "- Devuelve el indice (empezando en 0) del producto elegido, o -1 si ninguno "
    "corresponde de forma razonable."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "elegido": {
            "type": "integer",
            "description": "indice 0-based del producto elegido, o -1 si ninguno corresponde",
        }
    },
    "required": ["elegido"],
}


class DesambiguadorGemini:
    def __init__(self, api_key: str, modelo: str = MODELO_POR_DEFECTO) -> None:
        self._client = genai.Client(api_key=api_key)
        self.modelo = modelo
        self._config = types.GenerateContentConfig(
            system_instruction=_SYSTEM,
            temperature=0.0,
            max_output_tokens=512,
            response_mime_type="application/json",
            response_schema=_SCHEMA,
            # Los modelos 'flash' 2.5 razonan por defecto y se comen los tokens de
            # salida (dejando el JSON truncado). Para esta tarea de eleccion no hace
            # falta: lo desactivamos.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            # Sin function calling automatico: no lo usamos y evita reintentos
            # internos del SDK que multiplican las llamadas contra el limite.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def elegir(self, ingrediente: str, candidatos: list[str]) -> int | None:
        if not candidatos:
            return None
        lista = "\n".join(f"{i}. {nombre}" for i, nombre in enumerate(candidatos))
        contenido = f"INGREDIENTE: {ingrediente}\n\nPRODUCTOS:\n{lista}"

        resp = self._generar_con_reintento(contenido)
        texto = getattr(resp, "text", None)
        if not texto:
            return None
        try:
            elegido = json.loads(texto).get("elegido")
        except (json.JSONDecodeError, AttributeError):
            return None
        if isinstance(elegido, int) and 0 <= elegido < len(candidatos):
            return elegido
        return None  # -1 (ninguno) o valor fuera de rango

    def _generar_con_reintento(self, contenido: str):
        """Reintenta con backoff si la capa gratuita limita (429/RESOURCE_EXHAUSTED)."""
        for intento in range(_MAX_REINTENTOS):
            try:
                return self._client.models.generate_content(
                    model=self.modelo, contents=contenido, config=self._config
                )
            except errors.ClientError as e:
                if getattr(e, "code", None) == 429 and intento < _MAX_REINTENTOS - 1:
                    espera = 5 * (2**intento)
                    logger.info("Limite de Gemini (429); espero %ds y reintento", espera)
                    time.sleep(espera)
                    continue
                raise
