"""Desambiguador de matching con Claude (etapa final del embudo de la Fase 4).

Dado un ingrediente de receta y una lista corta de productos candidatos (los que
genera el matcher lexico), Claude elige el que de verdad corresponde al
ingrediente, o indica que ninguno sirve. Resuelve los casos que el texto no
puede: "sal" -> la sal de mesa, no "mantequilla sin sal".

Modelo por defecto: Haiku 4.5 (`claude-haiku-4-5`), el que el usuario eligio en
el prompt original para "tareas masivas". Configurable en config.yaml. Usa
structured outputs para una respuesta JSON fiable y prompt caching del system.
"""

from __future__ import annotations

import json
import logging

import anthropic

logger = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "claude-haiku-4-5"

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
    "- Si ningun candidato corresponde de forma razonable, responde null.\n"
    "Responde SOLO con el indice (empezando en 0) del producto elegido, o null."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "elegido": {
            "type": ["integer", "null"],
            "description": "indice 0-based del producto elegido, o null si ninguno corresponde",
        }
    },
    "required": ["elegido"],
    "additionalProperties": False,
}


class DesambiguadorClaude:
    def __init__(self, api_key: str, modelo: str = MODELO_POR_DEFECTO) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self.modelo = modelo

    def elegir(self, ingrediente: str, candidatos: list[str]) -> int | None:
        """Devuelve el indice del candidato elegido, o None si ninguno."""
        if not candidatos:
            return None
        lista = "\n".join(f"{i}. {nombre}" for i, nombre in enumerate(candidatos))
        user = f"INGREDIENTE: {ingrediente}\n\nPRODUCTOS:\n{lista}"

        resp = self._client.messages.create(
            model=self.modelo,
            max_tokens=200,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
        if resp.stop_reason == "refusal":
            logger.warning("Claude rehuso desambiguar %r", ingrediente)
            return None

        texto = next((b.text for b in resp.content if b.type == "text"), None)
        if not texto:
            return None
        try:
            elegido = json.loads(texto).get("elegido")
        except json.JSONDecodeError:
            return None
        if isinstance(elegido, int) and 0 <= elegido < len(candidatos):
            return elegido
        return None
