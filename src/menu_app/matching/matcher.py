"""Matching lexico DETERMINISTA ingrediente->producto con RapidFuzz.

Unica etapa de matching del embudo (decision del usuario: motor sin APIs de IA).
Sobre el nombre ya normalizado (limpio y traducido a español, ver normalizar.py)
busca el producto apto mas parecido por similitud de tokens, y corrige los
falsos positivos tipicos del texto con dos reglas deterministas:

1. FILTRO DE NEGACION: si el ingrediente solo aparece en el nombre del producto
   precedido de "sin", "0%", "bajo en"..., el producto NO es ese ingrediente
   ("mantequilla SIN SAL" no es sal; "bebida 0% AZUCAR" no es azucar). Se
   comprueba sobre el nombre crudo porque la normalizacion elimina esas
   particulas.
2. PALABRA-CABEZA: los nombres de supermercado empiezan por el tipo de producto
   ("Sal fina de mesa", "Aceite de oliva virgen extra"). Entre candidatos con
   solapamiento parecido, se prefiere el que EMPIEZA por un token del
   ingrediente ("Caldo de pollo" gana a "Empanada de pollo" para 'pollo caldo').
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from .normalizar import quitar_acentos, texto_producto

UMBRAL_LEXICO = 80.0
# Con miles de productos hay MUCHOS empates a score maximo para ingredientes de
# una palabra ("sal" aparece en decenas de nombres): el pool debe ser amplio para
# que el producto verdadero entre y las reglas (negacion, cabeza) puedan elegirlo.
_TOP_CANDIDATOS = 60
_MARGEN_DESEMPATE = 8.0

# Particulas que, delante del token, indican AUSENCIA del ingrediente en el
# producto. Se evalua sobre el nombre crudo sin acentos (minusculas).
_NEGACION_RE = re.compile(
    r"(?:\bsin|\b0\s*%?|\bbajo\s+en|\bbaja\s+en|\breducido\s+en|\breducida\s+en|\blight\s+en)\s*$"
)


def _token_negado(token: str, texto_crudo: str) -> bool:
    """True si TODAS las apariciones del token van precedidas de una negacion."""
    ocurrencias = list(re.finditer(rf"\b{re.escape(token)}\b", texto_crudo))
    if not ocurrencias:
        return False
    return all(_NEGACION_RE.search(texto_crudo[: m.start()]) for m in ocurrencias)


@dataclass
class Match:
    retailer_product_id: str
    producto_nombre: str
    score: float
    metodo: str


# Marcas propias de Alcampo (marca blanca): mas baratas a igualdad de producto (#16).
_MARCAS_BLANCAS = ("alcampo", "auchan", "producto alcampo", "cultivamos lo bueno")


def _es_marca_blanca(marca: str | None, nombre: str) -> bool:
    texto = f"{marca or ''} {nombre or ''}".lower()
    return any(m in texto for m in _MARCAS_BLANCAS)


def _stem(token: str) -> str:
    """Stem MUY ligero para casar singular/plural en español (acelga~acelgas,
    limon~limones, huevo~huevos). Solo quita el plural, no el genero."""
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


@dataclass
class IndiceProductos:
    """Indice de productos aptos, listo para buscar por texto normalizado."""

    rids: list[str]
    nombres: list[str]
    textos: list[str]  # texto_producto normalizado, mismo orden
    crudos: list[str] = field(default_factory=list)  # nombre sin acentos, para negaciones
    tokens: list[list[str]] = field(default_factory=list)  # tokens (stem) por producto, en orden
    invertido: dict[str, set[int]] = field(default_factory=dict)  # token stem -> idxs producto
    precios: list[float] = field(default_factory=list)  # precio_por_unidad (inf si None)
    es_blanca: list[bool] = field(default_factory=list)  # marca blanca (Alcampo/Auchan)

    @classmethod
    def construir(cls, productos: list[tuple]) -> "IndiceProductos":
        rids, nombres, textos, crudos, tokens = [], [], [], [], []
        precios: list[float] = []
        es_blanca: list[bool] = []
        invertido: dict[str, set[int]] = {}
        for prod in productos:
            rid, nombre, marca = prod[0], prod[1], prod[2]
            precio = prod[3] if len(prod) > 3 else None
            texto = texto_producto(nombre, marca)
            if not texto:
                continue
            idx = len(rids)
            rids.append(rid)
            nombres.append(nombre)
            textos.append(texto)
            crudos.append(quitar_acentos(nombre))
            precios.append(float(precio) if precio is not None else float("inf"))
            es_blanca.append(_es_marca_blanca(marca, nombre))
            toks = [_stem(t) for t in texto.split()]
            tokens.append(toks)
            for t in set(toks):
                invertido.setdefault(t, set()).add(idx)
        return cls(rids, nombres, textos, crudos, tokens, invertido, precios, es_blanca)

    def __len__(self) -> int:
        return len(self.rids)


class MatcherLexico:
    def __init__(self, indice: IndiceProductos, umbral: float = UMBRAL_LEXICO) -> None:
        self.indice = indice
        self.umbral = umbral

    def _es_negado(self, tokens_clave: set[str], idx: int) -> bool:
        """True si el producto solo contiene el ingrediente en forma negada."""
        crudo = self.indice.crudos[idx]
        presentes = [t for t in tokens_clave if re.search(rf"\b{re.escape(t)}\b", crudo)]
        if not presentes:
            return False
        return all(_token_negado(t, crudo) for t in presentes)

    def emparejar(self, clave: str) -> Match | None:
        if not clave or not self.indice.textos:
            return None
        tokens_clave = set(clave.split())
        stems = [_stem(t) for t in clave.split()]
        if not stems:
            return None

        # 1) COBERTURA POR TOKENS (via indice invertido): candidatos = productos que
        #    contienen algun token (stem) del ingrediente. Robusto a plural/formato
        #    y no depende del umbral fuzzy, que hunde a los ingredientes de 1 palabra.
        candidatos: set[int] = set()
        for s in stems:
            candidatos |= self.indice.invertido.get(s, set())

        mejor = self._elegir_por_cobertura(stems, tokens_clave, candidatos)
        if mejor is not None:
            idx, score = mejor
            return Match(self.indice.rids[idx], self.indice.nombres[idx], round(score, 1), "lexico")

        # 2) Respaldo fuzzy (token_set_ratio) para grafias distintas que el stem no
        #    cubre (p.ej. cuando faltan sinonimos en el glosario).
        cands = process.extract(
            clave, self.indice.textos, scorer=fuzz.token_set_ratio, limit=_TOP_CANDIDATOS
        )
        validos = [(s, i) for (_t, s, i) in cands if not self._es_negado(tokens_clave, i)]
        if not validos or validos[0][0] < self.umbral:
            return None
        top = validos[0][0]
        cercanos = [(s, i) for (s, i) in validos if s >= top - _MARGEN_DESEMPATE]
        con_cabeza = [
            (s, i) for (s, i) in cercanos if self.indice.textos[i].split()[0] in tokens_clave
        ]
        pool = con_cabeza or cercanos
        idx = max(pool, key=lambda p: fuzz.token_sort_ratio(clave, self.indice.textos[p[1]]))[1]
        return Match(self.indice.rids[idx], self.indice.nombres[idx], round(top, 1), "lexico")

    def _elegir_por_cobertura(
        self, stems: list[str], tokens_clave: set[str], candidatos: set[int]
    ) -> tuple[int, float] | None:
        """Entre los productos candidatos, exige que TODOS los tokens del ingrediente
        esten presentes (cobertura plena) y elige el mas 'alimento base': el que
        empieza por el token del ingrediente y tiene el nombre mas corto."""
        stems_set = set(stems)
        plenos: list[tuple[int, float]] = []
        for idx in candidatos:
            if self._es_negado(tokens_clave, idx):
                continue
            prod_stems = self.indice.tokens[idx]
            prod_set = set(prod_stems)
            if not stems_set <= prod_set:  # faltan tokens del ingrediente
                continue
            # Puntuacion: penaliza tokens de mas del producto (mas corto = mas puro).
            extra = len(prod_stems) - len(stems)
            cabeza = 1 if prod_stems and prod_stems[0] in stems_set else 0
            # score alto y comparable al fuzzy: 100 - penalizacion por verbosidad.
            score = 100.0 - min(30, extra * 4) + cabeza * 5
            plenos.append((idx, score, extra, cabeza))
        if not plenos:
            return None
        # Mejor: primero palabra-cabeza y menos tokens extra (pureza); a IGUALDAD de
        # pureza, marca blanca (#16) y luego el mas barato (#15), y por ultimo nombre
        # corto. Asi entre productos equivalentes se elige el que mas ahorra.
        def _clave(p):
            idx = p[0]
            precio = self.indice.precios[idx] if self.indice.precios else float("inf")
            blanca = self.indice.es_blanca[idx] if self.indice.es_blanca else False
            return (-p[3], p[2], 0 if blanca else 1, precio, len(self.indice.nombres[idx]))

        mejor = min(plenos, key=_clave)
        return mejor[0], mejor[1]

    def candidatos(self, clave: str, k: int = 8) -> list[Match]:
        """Top-K candidatos por token_set_ratio (para inspeccion o etapas opcionales)."""
        if not clave or not self.indice.textos:
            return []
        candidatos = process.extract(
            clave, self.indice.textos, scorer=fuzz.token_set_ratio, limit=k
        )
        return [
            Match(
                retailer_product_id=self.indice.rids[idx],
                producto_nombre=self.indice.nombres[idx],
                score=round(float(score), 1),
                metodo="lexico",
            )
            for _texto, score, idx in candidatos
        ]
