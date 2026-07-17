"""Cocinar con lo que hay en la despensa — #97.

Premia recetas que usan ingredientes que el usuario YA tiene (la misma lista
`despensa` que ya se usa para no comprarlos de nuevo en la lista de la compra,
ver optimizacion/compra.py). No es una restriccion dura: una receta sin
ingredientes de despensa sigue pudiendo entrar, solo no recibe el bonus.
"""

from __future__ import annotations


def puntua_despensa(ingredientes_norm, despensa_norm: frozenset[str]) -> float:
    """Fraccion 0..1 de los ingredientes de la receta que estan en la despensa.
    0 si la receta no tiene ingredientes o la despensa esta vacia."""
    if not despensa_norm or not ingredientes_norm:
        return 0.0
    total = 0
    en_despensa = 0
    for ing in ingredientes_norm:
        total += 1
        if any(d in ing for d in despensa_norm):
            en_despensa += 1
    return en_despensa / total if total else 0.0
