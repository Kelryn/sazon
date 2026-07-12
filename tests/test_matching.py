from __future__ import annotations

from pathlib import Path

import pytest

from menu_app.almacenamiento.db import get_connection, init_db
from menu_app.matching.matcher import IndiceProductos, MatcherLexico
from menu_app.matching.normalizar import clave_ingrediente, texto_producto
from menu_app.matching.repositorio import MatchingRepository


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("onion, chopped", "cebolla"),
        ("2 garlic cloves crushed", "ajo dientes"),  # 'cloves'->'dientes', 'crushed' fuera
        ("carrots, finely chopped (about 8 ounces; 225g)", "zanahoria"),
        ("dried bread crumbs", "seco pan rallado"),  # dried->seco, bread->pan, crumbs->pan rallado
        ("azucar", "azucar"),
        ("claras de huevo", "huevo"),  # claras/yemas -> huevo (Alcampo vende el huevo entero)
        ("uvas verdes para acompanar", "uvas verdes"),  # 'para'/'acompanar' fuera
        ("beef stock", "ternera caldo"),
        # Español de Latinoamerica -> España
        ("papas", "patata"),
        ("jitomate", "tomate"),
        ("zapallo", "calabaza"),
        ("banana", "platano"),
        # Colores que no cambian identidad se descartan (menos "verde")
        ("cebolla blanca", "cebolla"),
        ("tomate rojo", "tomate"),
        ("judias verdes", "judias verdes"),  # "verde" SI se conserva: otra hortaliza
        # Frases no descomponibles (deducidas del sentido de la receta)
        ("piernas con encuentro", "pollo"),
        ("platano verde", "platano"),  # 'verde' aqui = platano inmaduro
        ("habas verdes", "habas"),  # en Alcampo: habas finas
        ("aji ahumado", "chipotle"),
        # Sinonimos y formas de corte se limpian
        ("ajoporro", "puerro"),
        ("beterragas", "remolacha"),
        ("aji colorado molido", "aji rojo"),  # 'aji' se conserva; colorado->rojo, molido fuera
        ("apio picado en cuadritos", "apio"),
        ("apio rebanado muy delgado", "apio"),
        ("cabeza de brocoli", "brocoli"),
        ("barra de margarina", "margarina"),
        # Alternativas en español: se queda la primera opcion
        ("kion o jenjibre", "jengibre"),
    ],
)
def test_clave_ingrediente(entrada, esperado):
    assert clave_ingrediente(entrada) == esperado


def test_erratas_signos_se_limpian():
    # '¡' sustituye a una letra por error de la receta ("ace¡tunas" = aceitunas).
    assert clave_ingrediente("ace¡tunas") == "acetunas"


def test_texto_producto_quita_marca_y_formato():
    assert texto_producto("PRODUCTO ALCAMPO Ajo y perejil 35 g.", "PRODUCTO ALCAMPO") == "ajo perejil"
    assert texto_producto("BRILLANTE Arroz integral 400 g.", "BRILLANTE") == "arroz integral"


def test_texto_producto_quita_marca_mayusculas_sin_campo_marca():
    # La marca en MAYUSCULAS del principio se recorta aunque no venga en el campo
    # marca, dejando el alimento como palabra-cabeza (arreglo del desempate).
    assert texto_producto("AUCHAN Puerro en rodajas 1 kg", None).split()[0] == "puerro"
    assert texto_producto("SANTA TERESA Crema de puerro 400 ml", None).split()[0] == "crema"
    # Un nombre 100% en mayusculas NO se recorta (no perderiamos el alimento).
    assert "atun" in texto_producto("ATUN CLARO EN ACEITE", None)


def _indice() -> IndiceProductos:
    productos = [
        ("1", "PRODUCTO ALCAMPO Azúcar blanco 1 kg.", "PRODUCTO ALCAMPO"),
        ("2", "BRILLANTE Arroz integral 400 g.", "BRILLANTE"),
        ("3", "PRODUCTO ALCAMPO Cebolla al peso", "PRODUCTO ALCAMPO"),
        ("4", "DÍA Harina de trigo 1 kg.", "DÍA"),
    ]
    return IndiceProductos.construir(productos)


def test_matcher_lexico_empareja_correcto():
    matcher = MatcherLexico(_indice(), umbral=70)

    m = matcher.emparejar(clave_ingrediente("azucar"))
    assert m is not None and m.retailer_product_id == "1"

    m = matcher.emparejar(clave_ingrediente("onion, chopped"))
    assert m is not None and m.retailer_product_id == "3"  # cebolla


def test_matcher_descarta_bajo_umbral():
    matcher = MatcherLexico(_indice(), umbral=90)
    # "pescado" no se parece a ningun producto del indice -> sin match.
    assert matcher.emparejar("pescado azul") is None


# --- Reglas deterministas (negacion + palabra-cabeza), casos reales que fallaban ---


def _matcher(productos) -> MatcherLexico:
    return MatcherLexico(IndiceProductos.construir(productos), umbral=75)


def test_negacion_sin_sal():
    m = _matcher(
        [
            ("1", "HARMONY Pastilla de mantequilla sin sal 250 g.", "HARMONY"),
            ("2", "PRODUCTO ALCAMPO Sal fina de mesa 1 kg.", "PRODUCTO ALCAMPO"),
        ]
    )
    match = m.emparejar("sal")
    assert match is not None and match.retailer_product_id == "2"


def test_negacion_cero_por_ciento_azucar():
    m = _matcher(
        [
            ("1", "ALPRO Bebida avena 0% azúcar  caja 6x1 l.", "ALPRO"),
            ("2", "AZUCARERA Azúcar blanco 1 kg.", "AZUCARERA"),
        ]
    )
    match = m.emparejar("azucar")
    assert match is not None and match.retailer_product_id == "2"


def test_cabeza_aceite_oliva_no_anchoas():
    m = _matcher(
        [
            ("1", "CONSORCIO Anchoas en aceite de oliva virgen extra 90 g.", "CONSORCIO"),
            ("2", "MAESTROS DE HOJIBLANCA Aceite de oliva virgen extra 1 l.", "MAESTROS DE HOJIBLANCA"),
        ]
    )
    match = m.emparejar("aceite oliva virgen")
    assert match is not None and match.retailer_product_id == "2"


def test_cabeza_mantequilla_no_croissant():
    m = _matcher(
        [
            ("1", "Croissant de mantequilla 2 uds.120 g.", "PASTELERÍA"),
            ("2", "PRESIDENT Mantequilla en pastilla 250 g.", "PRESIDENT"),
        ]
    )
    match = m.emparejar("mantequilla")
    assert match is not None and match.retailer_product_id == "2"


def test_cabeza_caldo_de_pollo_no_empanada():
    m = _matcher(
        [
            ("1", "Empanada de pollo 1100 g.", "PANADERÍA"),
            ("2", "FRIAS NUTRICION Caldo de pollo 1 l.", "FRIAS NUTRICION"),
        ]
    )
    match = m.emparejar("pollo caldo")
    assert match is not None and match.retailer_product_id == "2"


def test_sin_lactosa_sigue_siendo_leche():
    # "sin lactosa" niega la lactosa, no la leche: debe seguir casando con leche.
    m = _matcher([("1", "PASCUAL Leche de vaca desnatada sin lactosa 1 l.", "PASCUAL")])
    match = m.emparejar("leche")
    assert match is not None and match.retailer_product_id == "1"


def test_todo_negado_queda_sin_match():
    # Si el UNICO candidato contiene el ingrediente solo negado -> sin match.
    m = _matcher([("1", "HARMONY Pastilla de mantequilla sin sal 250 g.", "HARMONY")])
    assert m.emparejar("sal") is None


@pytest.fixture
def repo(tmp_path: Path) -> MatchingRepository:
    conn = get_connection(tmp_path / "test.db")
    init_db(conn)
    return MatchingRepository(conn)


def test_upsert_mapeo_con_y_sin_match(repo):
    from menu_app.matching.matcher import Match

    repo.upsert_mapeo("azucar", "azucar", Match("1", "Azúcar", 95.0, "lexico"), "sin_match", "2026-07-09")
    repo.upsert_mapeo("unicornio", "unicornio", None, "sin_match", "2026-07-09")

    assert repo.contar_mapeos() == 2
    assert repo.contar_con_match() == 1


def test_upsert_mapeo_idempotente(repo):
    from menu_app.matching.matcher import Match

    repo.upsert_mapeo("azucar", "azucar", Match("1", "A", 90.0, "lexico"), "sin_match", "2026-07-09")
    repo.upsert_mapeo("azucar", "azucar", Match("2", "B", 92.0, "lexico"), "sin_match", "2026-07-10")

    assert repo.contar_mapeos() == 1  # no duplica
    fila = repo.conn.execute(
        "SELECT retailer_product_id FROM mapeo_ingr_producto WHERE ingrediente_norm='azucar'"
    ).fetchone()
    assert fila["retailer_product_id"] == "2"  # se queda el ultimo
