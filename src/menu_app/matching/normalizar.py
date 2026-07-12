"""Normaliza nombres de ingrediente y de producto a una forma comparable.

- Ingrediente: quita parentesis, se queda con la parte antes de la primera coma,
  elimina palabras de preparacion y de formato, y traduce EN->ES palabra a
  palabra. Resultado: una clave corta centrada en el alimento.
- Producto: quita la marca y el formato/tamaño ("35 g.", "6 x 1 l"...) y deja el
  nucleo descriptivo.
"""

from __future__ import annotations

import re
import unicodedata

from .glosario import STOP_PREPARACION, TRADUCCION_EN_ES

_PARENTESIS = re.compile(r"\([^)]*\)")
# "35 g.", "160 g", "1,5 l", "500ml", "6 x 1 l", "2 uds"...
_FORMATO = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*x\s*\d+(?:[.,]\d+)?\s*(?:g|gr|kg|ml|l|cl|litros?|gramos?)?\b"
    r"|\b\d+(?:[.,]\d+)?\s*(?:g|gr|kg|mg|ml|l|cl|litros?|gramos?|uds?|unidades|piezas)\b\.?",
    re.IGNORECASE,
)
_NO_ALFA = re.compile(r"[^a-z0-9ñ ]+")


def quitar_acentos(texto: str) -> str:
    sin = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sin.lower().strip()


# Stopwords ya sin acentos, porque el texto se compara siempre normalizado
# (si no, "acompañar" o "pequeño" nunca casarian con "acompanar"/"pequeno").
_STOP = frozenset(quitar_acentos(w) for w in STOP_PREPARACION)


def _tokens_utiles(texto: str) -> list[str]:
    texto = _NO_ALFA.sub(" ", texto)
    # Se descartan stopwords, numeros y tokens de una sola letra (ruido tipo "c/n",
    # "aceite c n"): ningun alimento se identifica por una unica letra.
    return [t for t in texto.split() if len(t) > 1 and t not in _STOP and not t.isdigit()]


# Alternativas "X o Y" / "X u Y": nos quedamos con la primera opcion (la principal).
# El "or" ingles NO se parte aqui: en "dry white or red wine" el sustantivo (wine)
# va al final; se deja pasar y lo resuelve el fuzzy con el token 'vino'.
_ALTERNATIVA = re.compile(r"\s+[ou]\s+")

# Erratas/artefactos de las recetas: signos que sustituyen a una letra.
_ERRATAS = str.maketrans({"¡": "", "¿": ""})

# Frases de ingrediente que no se pueden descomponer bien token a token: se
# reemplazan enteras por su forma canonica (deducidas del sentido de la receta).
# Clave sin acentos y en minusculas; ordenadas de mas larga a mas corta al aplicar.
_FRASES: dict[str, str] = {
    "piernas con encuentro": "pollo",  # corte de pollo (muslo+contramuslo)
    "pierna con encuentro": "pollo",
    "aji ahumado": "chipotle",  # el pimiento ahumado tipico es el chipotle
    "platano verde": "platano",  # 'verde' = platano inmaduro, no otra especie
    "banana verde": "platano",
    "platano macho": "platano",
    "habas verdes": "habas",  # en Alcampo: 'habas finas' (congelado)
    "haba verde": "habas",
    "bola de lomo": "cinta lomo",  # corte del lomo de cerdo
    "brazo de cerdo": "paleta cerdo",
    "anillos de calamar": "calamar",
    "anillas de calamar": "calamar",
    "tinta de calamar": "tinta calamar",
}
_FRASES_ORD = sorted(_FRASES, key=len, reverse=True)


def clave_ingrediente(nombre: str) -> str:
    """Ingrediente de receta -> clave de matching (limpia, en español)."""
    base = quitar_acentos(nombre).translate(_ERRATAS)
    base = _PARENTESIS.sub(" ", base)
    base = base.split(",")[0]  # "onion, chopped" -> "onion"
    base = _ALTERNATIVA.split(base)[0]  # "kion o jengibre" -> "kion"
    for frase in _FRASES_ORD:  # reemplazo de frases no descomponibles
        if frase in base:
            base = base.replace(frase, _FRASES[frase])
    tokens = _tokens_utiles(base)
    traducidos: list[str] = []
    for t in tokens:
        traducidos.extend(TRADUCCION_EN_ES.get(t, t).split())
    # Elimina duplicados consecutivos que a veces genera la traduccion multi-palabra.
    salida = [w for i, w in enumerate(traducidos) if i == 0 or w != traducidos[i - 1]]
    return " ".join(salida).strip()


def _quitar_marca_mayusculas(nombre: str) -> str:
    """Quita la marca en MAYUSCULAS del principio ('AUCHAN Puerro', 'SANTA TERESA
    Crema', 'PRODUCTO ALCAMPO Cebolla') dejando el alimento como palabra-cabeza.

    Solo se recorta si tras la ristra en mayusculas queda algun token con
    minusculas (el nombre real del alimento suele ir en Title Case). Asi los
    nombres 100% en mayusculas se dejan intactos (no perderiamos el alimento).
    """
    tokens = nombre.split()
    primer_min = next((j for j, t in enumerate(tokens) if any(c.islower() for c in t)), None)
    if primer_min and primer_min > 0:
        return " ".join(tokens[primer_min:])
    return nombre


def texto_producto(nombre: str, marca: str | None) -> str:
    """Nombre de producto -> texto indexable (sin marca ni formato)."""
    base = quitar_acentos(_quitar_marca_mayusculas(nombre))
    if marca:
        marca_norm = quitar_acentos(marca)
        if base.startswith(marca_norm):
            base = base[len(marca_norm):]
    base = _PARENTESIS.sub(" ", base)
    base = _FORMATO.sub(" ", base)
    tokens = _tokens_utiles(base)
    return " ".join(tokens).strip()
