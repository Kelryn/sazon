"""Tests del solver MILP, incluida la prueba clave: el suelo de proteina impide
que el menu la elimine por ser lo mas caro."""

from __future__ import annotations

from menu_app.optimizacion.nutrientes import BandaNutriente
from menu_app.optimizacion.solver import RecetaOpt, optimizar, optimizar_comida_cena


def _receta(id, coste, kcal, prot, pal=0.0):
    return RecetaOpt(
        id=id,
        titulo=id,
        coste_racion=coste,
        nutricion_racion={"energia_kcal": kcal, "proteinas": prot},
        palatabilidad=pal,
    )


def test_suelo_de_proteina_fuerza_proteina_aunque_sea_cara():
    # Dos recetas: una BARATA sin proteina, otra CARA con proteina.
    barata = _receta("pan", coste=0.30, kcal=500, prot=2.0)
    cara = _receta("pollo", coste=1.50, kcal=500, prot=40.0)
    bandas = [
        BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda"),
        BandaNutriente("proteinas", minimo=200, maximo=None, unidad="g", tipo="min"),
    ]
    # 10 comidas, 1 comensal.
    menu = optimizar([barata, cara], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10)

    assert menu.factible
    # Sin el suelo de proteina el solver pondria 10 de 'pan' (mas barato). Con el
    # suelo, DEBE incluir 'pollo' para llegar a >=200 g de proteina.
    assert menu.seleccion.get("pollo", 0) > 0
    assert menu.nutricion_total["proteinas"] >= 200


def _receta_prod(id, productos):
    r = RecetaOpt(
        id=id,
        titulo=id,
        coste_racion=1.0,
        nutricion_racion={"energia_kcal": 500, "proteinas": 20.0},
    )
    r.productos = frozenset(productos)
    return r


def test_racionalizacion_prefiere_recetas_que_comparten_productos():
    # Cuatro recetas equivalentes en coste/nutricion. p1 lo usan todas; p2 solo A y B;
    # p3 solo C y D. Elegir DOS recetas del mismo grupo (A+B o C+D) usa menos productos
    # distintos "poco comunes" que una pareja cruzada (A+C).
    A = _receta_prod("A", {"p1", "p2"})
    B = _receta_prod("B", {"p1", "p2"})
    C = _receta_prod("C", {"p1", "p3"})
    D = _receta_prod("D", {"p1", "p3"})
    bandas = [BandaNutriente("energia_kcal", minimo=500, maximo=1500, unidad="kcal", tipo="banda")]

    # dias=1 -> 1 comida + 1 cena = 2 huecos; max_repeticiones=1 -> dos recetas distintas.
    menu = optimizar_comida_cena(
        [A, B, C, D], bandas, dias=1, num_comensales=1, max_repeticiones=1,
        frac_espanola_min=0.0, peso_reutilizacion=1.0,
    )
    assert menu.factible
    elegidas = set(menu.seleccion)
    # La pareja optima comparte grupo: {A,B} o {C,D}, nunca una cruzada.
    assert elegidas in ({"A", "B"}, {"C", "D"}), elegidas


def test_sin_racionalizacion_no_crea_binarios_ni_penaliza():
    # Con peso_reutilizacion=0 (por defecto) el menu sigue siendo factible y no se
    # ve afectado por los productos.
    A = _receta_prod("A", {"p1", "p2"})
    C = _receta_prod("C", {"p3", "p4"})
    bandas = [BandaNutriente("energia_kcal", minimo=500, maximo=1500, unidad="kcal", tipo="banda")]
    menu = optimizar_comida_cena(
        [A, C], bandas, dias=1, num_comensales=1, max_repeticiones=2, frac_espanola_min=0.0
    )
    assert menu.factible


def test_sin_suelo_elige_lo_mas_barato():
    barata = _receta("pan", coste=0.30, kcal=500, prot=2.0)
    cara = _receta("pollo", coste=1.50, kcal=500, prot=40.0)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda")]
    menu = optimizar([barata, cara], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10)
    # Sin restriccion de proteina, todo 'pan' (lo barato) -> demuestra el problema
    # que el suelo resuelve.
    assert menu.seleccion.get("pan", 0) == 10
    assert "pollo" not in menu.seleccion


def test_techo_de_sal_limita():
    salada = RecetaOpt("salada", "salada", 0.20, {"energia_kcal": 500, "sal": 5.0})
    suave = RecetaOpt("suave", "suave", 0.50, {"energia_kcal": 500, "sal": 0.5})
    bandas = [
        BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda"),
        BandaNutriente("sal", minimo=None, maximo=10, unidad="g", tipo="max"),
    ]
    menu = optimizar([salada, suave], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10)
    assert menu.factible
    assert menu.nutricion_total["sal"] <= 10  # no se pasa de sal aunque la salada sea barata


def test_infactible_devuelve_motivo():
    # Suelo de proteina imposible de alcanzar con las recetas dadas.
    pobre = _receta("pan", coste=0.30, kcal=500, prot=1.0)
    bandas = [
        BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda"),
        BandaNutriente("proteinas", minimo=9999, maximo=None, unidad="g", tipo="min"),
    ]
    menu = optimizar([pobre], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10)
    assert not menu.factible


def test_minimo_recetas_espanolas():
    esp = RecetaOpt("esp", "esp", 1.0, {"energia_kcal": 500, "proteinas": 20.0}, es_espanola=True)
    ext = RecetaOpt("ext", "ext", 0.20, {"energia_kcal": 500, "proteinas": 20.0}, es_espanola=False)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda")]
    # La extranjera es mucho mas barata; sin la regla, el menu seria todo 'ext'.
    menu = optimizar(
        [esp, ext], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0.5,
    )
    assert menu.factible
    assert menu.seleccion.get("esp", 0) >= 5  # >=50% españolas pese a ser mas caras


def test_suelo_blando_no_bloquea_pero_reporta_deficit():
    # Una receta sin apenas fibra; el suelo de fibra es inalcanzable.
    r = _receta("arroz", coste=0.5, kcal=500, prot=20.0)
    r.nutricion_racion["fibra"] = 1.0
    bandas = [
        BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda"),
        BandaNutriente("fibra", minimo=350, maximo=None, unidad="g", tipo="min"),
    ]
    menu = optimizar(
        [r], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, suelos_blandos=frozenset({"fibra"}),
    )
    # Con la fibra como suelo BLANDO, hay menu (no bloquea) pero se reporta el deficit.
    assert menu.factible
    assert "fibra" in (menu.deficit_blando or {})
    assert menu.deficit_blando["fibra"] > 300


def test_fibra_como_suelo_duro_si_bloquea():
    r = _receta("arroz", coste=0.5, kcal=500, prot=20.0)
    r.nutricion_racion["fibra"] = 1.0
    bandas = [
        BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda"),
        BandaNutriente("fibra", minimo=350, maximo=None, unidad="g", tipo="min"),
    ]
    # Sin marcarla como blanda, el suelo de fibra vuelve a bloquear.
    menu = optimizar(
        [r], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, suelos_blandos=frozenset(),
    )
    assert not menu.factible


def _banda_energia():
    return [BandaNutriente("energia_kcal", minimo=4500, maximo=6000, unidad="kcal", tipo="banda")]


def test_bandas_por_comida_reparten_energia():
    # Una receta ligera (barata) y otra energetica. Sin banda por franja, el solver
    # llenaria la comida con lo barato; la banda de energia de la CENA fuerza a que
    # la cena tenga su parte de energia.
    ligera = RecetaOpt("lig", "lig", 0.3, {"energia_kcal": 300, "proteinas": 20.0})
    fuerte = RecetaOpt("fue", "fue", 0.5, {"energia_kcal": 800, "proteinas": 20.0})
    banda_dia = [BandaNutriente("energia_kcal", minimo=4000, maximo=9000, unidad="kcal", tipo="banda")]
    b_cena = [BandaNutriente("energia_kcal", minimo=2500, maximo=4000, unidad="kcal", tipo="banda")]
    menu = optimizar_comida_cena(
        [ligera, fuerte], banda_dia, dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_variedad=0, bandas_cena=b_cena,
    )
    assert menu.factible
    e_cena = sum(
        {"lig": 300, "fue": 800}[rid] * x for rid, x in (menu.raciones_cena or {}).items()
    )
    assert e_cena >= 2400  # la cena cumple (aprox) su suelo de energia


def test_comida_cena_reparte_franjas():
    r = _receta("guiso", coste=1.0, kcal=500, prot=20.0)
    menu = optimizar_comida_cena(
        [r], _banda_energia(), dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0,
    )
    assert menu.factible
    # 5 comidas + 5 cenas.
    assert sum(menu.seleccion_comida.values()) == 5
    assert sum(menu.seleccion_cena.values()) == 5


def test_cena_prefiere_ligera_y_sencilla():
    pesada = RecetaOpt("pesada", "pesada", 1.0, {"energia_kcal": 500, "proteinas": 20.0}, aptitud_cena=0.0)
    ligera = RecetaOpt("ligera", "ligera", 1.0, {"energia_kcal": 500, "proteinas": 20.0}, aptitud_cena=1.0)
    menu = optimizar_comida_cena(
        [pesada, ligera], _banda_energia(), dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_cena_ligera_simple=5.0,
    )
    assert menu.factible
    # A igual coste/nutrientes, la cena elige la ligera+sencilla.
    assert menu.seleccion_cena.get("ligera", 0) >= menu.seleccion_cena.get("pesada", 0)


def test_variedad_penaliza_repetir_familia():
    # 3 recetas de la familia "salmorejo" (baratas) y una "guiso" (algo mas cara).
    salm = [
        RecetaOpt(f"s{i}", f"Salmorejo {i}", 0.5, {"energia_kcal": 500, "proteinas": 20.0},
                  familia="salmorejo")
        for i in range(3)
    ]
    guiso = RecetaOpt("g", "Guiso", 0.9, {"energia_kcal": 500, "proteinas": 20.0}, familia="guiso")
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=6000, unidad="kcal", tipo="banda")]
    # Sin penalizacion de variedad: todo salmorejo (lo barato).
    sin = optimizar_comida_cena(
        salm + [guiso], bandas, dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_variedad=0,
    )
    salm_ids = {"s0", "s1", "s2"}
    n_salm_sin = sum(n for rid, n in sin.seleccion.items() if rid in salm_ids)
    # Con penalizacion fuerte y max 2 por familia: entra el guiso para no repetir tanto.
    con = optimizar_comida_cena(
        salm + [guiso], bandas, dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, peso_variedad=50, max_familia_libre=2,
    )
    n_salm_con = sum(n for rid, n in con.seleccion.items() if rid in salm_ids)
    assert con.factible and n_salm_con < n_salm_sin
    assert con.seleccion.get("g", 0) > 0  # la variedad mete el guiso


def test_dias_batchcooking_mixtos():
    # 3 dias batchcooking y 2 libres: exactamente 3 comidas del catalogo en tanda.
    bc = RecetaOpt("guiso", "guiso", 2.0, {"energia_kcal": 500, "proteinas": 20.0},
                   es_batchcooking=True)
    libre = RecetaOpt("plancha", "plancha", 0.5, {"energia_kcal": 500, "proteinas": 20.0},
                      es_batchcooking=False)
    menu = optimizar_comida_cena(
        [bc, libre], _banda_energia(), dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, dias_batchcooking=3,
    )
    assert menu.factible
    # Las 3 comidas batchcooking son del guiso (la plancha no puede ocuparlas)...
    assert menu.seleccion_comida_bc == {"guiso": 3}
    # ...y las 2 libres eligen lo barato (plancha).
    assert menu.seleccion_comida.get("plancha", 0) == 2
    assert sum(menu.seleccion_comida.values()) == 5


def test_batchcooking_solo_afecta_a_las_comidas():
    bc = RecetaOpt("guiso", "guiso", 1.0, {"energia_kcal": 500, "proteinas": 20.0},
                   es_batchcooking=True, aptitud_cena=0.1)
    no_bc = RecetaOpt("ensalada", "ensalada", 1.0, {"energia_kcal": 500, "proteinas": 20.0},
                      es_batchcooking=False, aptitud_cena=1.0)
    menu = optimizar_comida_cena(
        [bc, no_bc], _banda_energia(), dias=5, num_comensales=1, max_repeticiones=10,
        frac_espanola_min=0, solo_batchcooking_comida=True, peso_cena_ligera_simple=5.0,
    )
    assert menu.factible
    # Las COMIDAS solo pueden usar recetas batchcooking...
    assert "ensalada" not in menu.seleccion_comida
    assert menu.seleccion_comida.get("guiso", 0) == 5
    # ...pero las CENAS pueden usar la no-batchcooking (ligera).
    assert menu.seleccion_cena.get("ensalada", 0) > 0


def test_palatabilidad_desempata():
    # Mismo coste y nutrientes; una mejor valorada.
    a = _receta("a", coste=1.0, kcal=500, prot=20.0, pal=0.2)
    b = _receta("b", coste=1.0, kcal=500, prot=20.0, pal=0.9)
    bandas = [BandaNutriente("energia_kcal", minimo=4500, maximo=5500, unidad="kcal", tipo="banda")]
    menu = optimizar(
        [a, b], bandas, n_comidas=10, num_comensales=1, max_repeticiones=10, peso_palatabilidad=1.0
    )
    assert menu.seleccion.get("b", 0) >= menu.seleccion.get("a", 0)
