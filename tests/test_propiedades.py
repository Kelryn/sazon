"""Tests basados en propiedades con Hypothesis (Lote 9, #95).

En vez de fijar casos concretos, generan MUCHAS entradas aleatorias y
comprueban un invariante que debe cumplirse siempre — utiles para logica
combinatoria (reparto de dias) o de comparacion (versiones) donde un caso
suelto puede no detectar un borde mal manejado.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from menu_app.actualizaciones import es_mas_nueva
from menu_app.optimizacion.planes import _distribuir


@given(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
)
def test_version_nunca_es_mas_nueva_que_si_misma(a, b, c):
    v = f"{a}.{b}.{c}"
    assert not es_mas_nueva(v, v)


@given(
    st.integers(min_value=1, max_value=20),
    st.integers(min_value=1, max_value=20),
    st.integers(min_value=1, max_value=20),
)
def test_incrementar_el_patch_siempre_es_mas_nueva(mayor, menor, patch):
    v1 = f"{mayor}.{menor}.{patch}"
    v2 = f"{mayor}.{menor}.{patch + 1}"
    assert es_mas_nueva(v2, v1)
    assert not es_mas_nueva(v1, v2)


@given(
    st.dictionaries(
        st.text(alphabet="abcde", min_size=1, max_size=3),
        st.integers(min_value=1, max_value=4),
        max_size=4,
    ),
    st.integers(min_value=1, max_value=15),
)
def test_distribuir_coloca_cada_receta_las_veces_pedidas(cuentas, n_extra):
    # n suficientemente grande para que TODAS las apariciones quepan (si no,
    # _distribuir recorta silenciosamente y la propiedad no aplicaria).
    n = sum(cuentas.values()) + n_extra
    resultado = _distribuir(cuentas, n)

    assert len(resultado) == n
    for rid, k in cuentas.items():
        assert resultado.count(rid) == k
