"""Tests del desambiguador LLM sin tocar la API real (cliente anthropic simulado)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from menu_app.ia.cliente_claude import DesambiguadorClaude
from menu_app.ia.cliente_gemini import DesambiguadorGemini
from menu_app.matching.matcher import IndiceProductos, MatcherLexico


class _FakeMessages:
    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        valor = self._respuestas.pop(0)
        if isinstance(valor, Exception):
            raise valor
        # Simula la forma de la respuesta del SDK: content con un bloque text.
        bloque = SimpleNamespace(type="text", text=json.dumps({"elegido": valor}))
        return SimpleNamespace(stop_reason="end_turn", content=[bloque])


def _desambiguador(respuestas) -> DesambiguadorClaude:
    d = DesambiguadorClaude.__new__(DesambiguadorClaude)  # sin crear cliente real
    d.modelo = "claude-haiku-4-5"
    d._client = SimpleNamespace(messages=_FakeMessages(respuestas))
    return d


def test_elige_indice_valido():
    d = _desambiguador([1])
    idx = d.elegir("sal", ["Mantequilla sin sal", "Sal fina de mesa", "Ensalada"])
    assert idx == 1


def test_elegido_null_devuelve_none():
    d = _desambiguador([None])
    assert d.elegir("unicornio", ["Sal", "Azucar"]) is None


def test_indice_fuera_de_rango_se_ignora():
    d = _desambiguador([9])  # solo hay 2 candidatos
    assert d.elegir("sal", ["Sal", "Azucar"]) is None


def test_sin_candidatos_no_llama_al_modelo():
    fake = _FakeMessages([])
    d = DesambiguadorClaude.__new__(DesambiguadorClaude)
    d.modelo = "claude-haiku-4-5"
    d._client = SimpleNamespace(messages=fake)
    assert d.elegir("sal", []) is None
    assert fake.llamadas == []  # no se hizo ninguna peticion


def test_refusal_devuelve_none():
    d = DesambiguadorClaude.__new__(DesambiguadorClaude)
    d.modelo = "claude-haiku-4-5"
    d._client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **k: SimpleNamespace(stop_reason="refusal", content=[])
        )
    )
    assert d.elegir("sal", ["Sal"]) is None


# --- Desambiguador Gemini (cliente google-genai simulado) ---


class _FakeGeminiModels:
    def __init__(self, valores):
        self._valores = list(valores)

    def generate_content(self, **kwargs):
        valor = self._valores.pop(0)
        return SimpleNamespace(text=json.dumps({"elegido": valor}))


def _gemini(valores) -> DesambiguadorGemini:
    d = DesambiguadorGemini.__new__(DesambiguadorGemini)
    d.modelo = "gemini-2.5-flash"
    d._config = None
    d._client = SimpleNamespace(models=_FakeGeminiModels(valores))
    return d


def test_gemini_elige_indice_valido():
    d = _gemini([1])
    idx = d.elegir("sal", ["Mantequilla sin sal", "Sal fina de mesa", "Ensalada"])
    assert idx == 1


def test_gemini_centinela_menos_uno_es_none():
    d = _gemini([-1])  # -1 = ninguno corresponde
    assert d.elegir("unicornio", ["Sal", "Azucar"]) is None


def test_gemini_fuera_de_rango_es_none():
    d = _gemini([5])
    assert d.elegir("sal", ["Sal", "Azucar"]) is None


def test_gemini_sin_candidatos_no_llama():
    d = _gemini([])
    assert d.elegir("sal", []) is None


# --- Integracion matcher + desambiguador (con un desambiguador falso) ---


class _DesambiguadorFalso:
    """Elige siempre el candidato cuyo nombre contiene la palabra del ingrediente."""

    def elegir(self, ingrediente: str, candidatos: list[str]) -> int | None:
        for i, c in enumerate(candidatos):
            if ingrediente.split()[0] in c.lower():
                return i
        return None


def test_candidatos_topk_del_matcher():
    productos = [
        ("1", "PRODUCTO ALCAMPO Sal fina de mesa 1 kg.", "PRODUCTO ALCAMPO"),
        ("2", "HARMONY Mantequilla sin sal 250 g.", "HARMONY"),
        ("3", "PRODUCTO ALCAMPO Azucar blanco 1 kg.", "PRODUCTO ALCAMPO"),
    ]
    matcher = MatcherLexico(IndiceProductos.construir(productos))
    candidatos = matcher.candidatos("sal", k=5)
    assert len(candidatos) >= 2
    # El LLM falso elige el que contiene "sal" y no es la mantequilla.
    idx = _DesambiguadorFalso().elegir("sal", [c.producto_nombre.lower() for c in candidatos])
    assert idx is not None
    assert "sal fina" in candidatos[idx].producto_nombre.lower()
