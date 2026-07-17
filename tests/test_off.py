from __future__ import annotations

from pathlib import Path

from menu_app.off.matcher import mejor_match, texto_busqueda
from menu_app.off.off_client import OFFClient

# Candidatos con la forma real de la respuesta de OFF (recortada).
CANDIDATOS_LECHE = [
    {
        "code": "8410297012150",
        "product_name": "Leche Semi desnatada",
        "brands": "Central Lechera Asturiana",
        "nutriscore_grade": "b",
        "nova_group": 1,
        "allergens_tags": ["en:milk"],
    },
    {
        "code": "0000000000000",
        "product_name": "Galletas de chocolate",
        "brands": "Otra Marca",
        "nutriscore_grade": "e",
        "nova_group": 4,
        "allergens_tags": ["en:gluten", "en:milk"],
    },
]


def test_texto_busqueda_quita_ruido_de_formato():
    t = texto_busqueda("Leche semidesnatada 6 x 1 l", "Central Lechera Asturiana")
    assert "central lechera asturiana" in t
    assert "leche semidesnatada" in t
    assert "6 x 1 l" not in t  # el formato se elimina


def test_mejor_match_elige_el_correcto():
    datos = mejor_match(
        "Leche semidesnatada", "Central Lechera Asturiana", CANDIDATOS_LECHE
    )
    assert datos is not None
    assert datos.ean == "8410297012150"
    assert datos.nutri_score == "b"
    assert datos.nova == 1
    assert datos.alergenos == "milk"
    assert datos.match_score >= 82


def test_mejor_match_descarta_si_no_supera_umbral():
    # Producto sin nada que ver con los candidatos -> no debe emparejar.
    datos = mejor_match("Detergente lavavajillas limon", "MarcaX", CANDIDATOS_LECHE)
    assert datos is None


def test_mejor_match_sin_candidatos():
    assert mejor_match("Cualquier cosa", None, []) is None


def test_valores_unknown_se_vuelven_none():
    candidatos = [
        {
            "code": "123",
            "product_name": "Tomate triturado",
            "brands": "alcampo",
            "nutriscore_grade": "unknown",
            "nova_group": None,
            "allergens_tags": [],
        }
    ]
    datos = mejor_match("Tomate triturado", "ALCAMPO", candidatos)
    assert datos is not None
    assert datos.ean == "123"
    assert datos.nutri_score is None  # "unknown" -> None
    assert datos.nova is None
    assert datos.alergenos is None


def test_off_client_cachea_y_reintenta(httpx_mock, tmp_path: Path):
    # Primer intento 503 (se reintenta), segundo 200.
    httpx_mock.add_response(status_code=503, text="overloaded")
    httpx_mock.add_response(
        json={"products": [{"code": "1", "product_name": "X", "brands": "Y"}], "count": 1}
    )

    with OFFClient(
        cache_dir=tmp_path / "off", min_request_interval_seconds=0.0, jitter_seconds=0.0
    ) as off:
        r1 = off.buscar("algo")
        r2 = off.buscar("algo")  # desde cache, sin nueva peticion

    assert r1 == [{"code": "1", "product_name": "X", "brands": "Y"}]
    assert r2 == r1
    # 2 peticiones: el 503 + el 200. La segunda busqueda salio de cache.
    assert len(httpx_mock.get_requests()) == 2
