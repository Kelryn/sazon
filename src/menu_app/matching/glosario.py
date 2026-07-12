"""Glosario EN->ES de alimentos y listas de palabras a descartar.

El glosario traduce (a nivel de palabra) los ingredientes de recetas en ingles
al español, para poder casarlos con el catalogo de Alcampo (en español). No
pretende ser exhaustivo: cubre los ingredientes de cocina mas habituales; lo que
no este aqui se deja como esta (y el fuzzy o, mas adelante, el LLM lo resuelven).

Las listas de "ruido" quitan palabras de preparacion ("chopped", "picado"),
formato y relleno que estorban al emparejar por el nombre del alimento.
"""

from __future__ import annotations

# EN -> ES a nivel de palabra (clave sin acentos, en minusculas).
TRADUCCION_EN_ES: dict[str, str] = {
    # Basicos
    "salt": "sal", "pepper": "pimienta", "sugar": "azucar", "flour": "harina",
    "water": "agua", "oil": "aceite", "butter": "mantequilla", "milk": "leche",
    "egg": "huevo", "eggs": "huevos", "cheese": "queso", "cream": "nata",
    "bread": "pan", "breadcrumbs": "pan rallado", "crumbs": "pan rallado",
    "rice": "arroz", "pasta": "pasta", "noodles": "fideos",
    # Carnes y pescados
    "beef": "ternera", "pork": "cerdo", "chicken": "pollo", "turkey": "pavo",
    "lamb": "cordero", "sausage": "salchicha", "sausages": "salchicha",
    "bacon": "bacon", "ham": "jamon", "mince": "picada", "meatloaf": "pastel de carne",
    "fish": "pescado", "salmon": "salmon", "tuna": "atun", "cod": "bacalao",
    "prawns": "gambas", "shrimp": "gambas",
    # Verduras
    "onion": "cebolla", "onions": "cebolla", "garlic": "ajo", "tomato": "tomate",
    "tomatoes": "tomate", "carrot": "zanahoria", "carrots": "zanahoria",
    "potato": "patata", "potatoes": "patata", "celery": "apio", "pepper bell": "pimiento",
    "peppers": "pimiento", "spinach": "espinacas", "lettuce": "lechuga",
    "mushroom": "champiñon", "mushrooms": "champiñones", "courgette": "calabacin",
    "zucchini": "calabacin", "aubergine": "berenjena", "eggplant": "berenjena",
    "cucumber": "pepino", "leek": "puerro", "peas": "guisantes", "corn": "maiz",
    "beans": "judias", "cabbage": "col", "pumpkin": "calabaza",
    # Legumbres / cereales
    "lentils": "lentejas", "chickpeas": "garbanzos", "oats": "avena", "quinoa": "quinoa",
    # Frutas
    "apple": "manzana", "banana": "platano", "lemon": "limon", "orange": "naranja",
    "strawberry": "fresa", "strawberries": "fresas", "peach": "melocoton",
    "grapes": "uvas", "avocado": "aguacate",
    # Lacteos / reposteria
    "yogurt": "yogur", "yoghurt": "yogur", "chocolate": "chocolate", "cocoa": "cacao",
    "vanilla": "vainilla", "honey": "miel", "almonds": "almendras", "walnuts": "nueces",
    "cinnamon": "canela", "baking": "levadura", "yeast": "levadura",
    # Condimentos / hierbas
    "parsley": "perejil", "basil": "albahaca", "oregano": "oregano", "rosemary": "romero",
    "thyme": "tomillo", "bay": "laurel", "coriander": "cilantro", "cilantro": "cilantro",
    "cumin": "comino", "paprika": "pimenton", "ginger": "jengibre", "nutmeg": "nuez moscada",
    "fennel": "hinojo", "mustard": "mostaza", "vinegar": "vinagre", "wine": "vino",
    "stock": "caldo", "broth": "caldo", "sauce": "salsa", "curry": "curry",
    "mayonnaise": "mayonesa", "mayo": "mayonesa",
    # Descriptores utiles de alimento (no de preparacion)
    "olive": "oliva", "sunflower": "girasol", "white": "blanco", "red": "rojo",
    "black": "negro", "green": "verde", "brown": "integral", "whole": "entero",
    "heavy": "para montar", "double": "para montar", "sweet": "dulce", "dried": "seco",
    "fresh": "fresco", "ground": "molido", "grated": "rallado", "smoked": "ahumado",
    "boneless": "sin hueso", "skinless": "sin piel", "extra": "extra", "virgin": "virgen",
    "italian": "italiana", "leaves": "hojas", "seeds": "semillas", "clove": "diente",
    "cloves": "dientes",
    # Ampliacion tras revisar los "sin match" reales
    "greek": "griego", "seasoning": "condimento", "puree": "pure", "parmesan": "parmesano",
    "parmigiano": "parmesano", "pancetta": "panceta", "chilli": "guindilla", "chili": "guindilla",
    "sage": "salvia", "liver": "higado", "livers": "higado", "plum": "pera", "tin": "lata",
    "tins": "lata", "packet": "sobre", "packets": "sobre", "rasher": "loncha", "rashers": "loncha",
    "lasagna": "lasaña", "lasagne": "lasaña", "spice": "especias", "gelatin": "gelatina",
    "gelatine": "gelatina", "powdered": "en polvo", "unsalted": "sin sal", "streaky": "veteado",
    "celery": "apio", "wholemeal": "integral", "caster": "", "icing": "glas",
    # --- Español de Latinoamerica -> español de España (el crawl trajo muchas
    # recetas latinoamericanas; hay que casarlas con el catalogo de Alcampo). ---
    "papa": "patata", "papas": "patata", "jitomate": "tomate", "jitomates": "tomate",
    "zapallo": "calabaza", "poro": "puerro", "choclo": "maiz", "elote": "maiz",
    "palta": "aguacate", "banana": "platano", "bananas": "platano", "guineo": "platano",
    "ajonjoli": "sesamo", "sillao": "soja", "durazno": "melocoton", "duraznos": "melocoton",
    "frutilla": "fresa", "frutillas": "fresas", "camote": "boniato", "arveja": "guisantes",
    "arvejas": "guisantes", "poroto": "alubias", "porotos": "alubias", "frijol": "alubias",
    "frijoles": "alubias", "betarraga": "remolacha", "betabel": "remolacha",
    "morron": "pimiento", "morrones": "pimiento", "cebollin": "cebolleta",
    "cebollines": "cebolleta", "damasco": "albaricoque", "durazno ": "melocoton",
    "manies": "cacahuetes", "mani": "cacahuete", "pomelo": "pomelo", "chuno": "fecula",
    "res": "ternera", "cerdo": "cerdo", "pavo": "pavo",
    # Partes del huevo -> huevo (Alcampo vende el huevo entero).
    "clara": "huevo", "claras": "huevo", "yema": "huevo", "yemas": "huevo",
    # Sinonimos y variantes regionales adicionales (revision de "sin match").
    "maicena": "maizena", "maizena": "maizena", "jugo": "zumo",
    "catsup": "ketchup", "ketchup": "ketchup", "alverja": "guisantes",
    "alverjas": "guisantes", "arveja": "guisantes", "arvejas": "guisantes",
    "auyama": "calabaza", "choclos": "maiz", "mazorca": "maiz", "mazorcas": "maiz",
    "calabacitas": "calabacin", "ejote": "judia verde", "ejotes": "judias verdes",
    "cebollin": "cebolleta", "cebollines": "cebolleta", "cebolleta": "cebolleta",
    "leudante": "", "levadura": "levadura", "gaseosa": "",
    "panela": "azucar", "papelon": "azucar",
    "kion": "jengibre", "jenjibre": "jengibre", "gallina": "pollo",
    "codito": "macarrones", "coditos": "macarrones", "arverja": "guisantes",
    "arverjas": "guisantes", "endulzante": "edulcorante", "durazno": "melocoton",
    "damascos": "albaricoque", "zumo": "zumo", "maracuya": "maracuya",
    "poro": "puerro", "poros": "puerro",
    "chiles": "guindilla", "chile": "guindilla", "pimenton": "pimenton",
    "agar": "gelatina", "margarina": "margarina", "achiote": "",
    # Revision con ejemplos del usuario:
    "colorado": "rojo", "colorada": "rojo", "ajoporro": "puerro",
    "ajoporros": "puerro", "beterraga": "remolacha", "beterragas": "remolacha",
    "encuentro": "pollo", "bistec": "filete", "bictec": "filete",
    # 'aji' se conserva (Alcampo vende GOYA Aji amarillo/panca): asi casan los
    # especificos. 'ajies' -> 'aji' (singular) para unificar el plural.
    "ajies": "aji",
}

# Palabras de preparacion / relleno que se eliminan del nombre del ingrediente
# (no aportan a identificar el alimento). ES + EN, sin acentos, en minusculas.
STOP_PREPARACION: frozenset[str] = frozenset(
    {
        # EN preparacion
        "chopped", "minced", "crushed", "diced", "sliced", "grated", "shredded",
        "finely", "coarsely", "roughly", "freshly", "peeled", "picked", "trimmed",
        "beaten", "melted", "softened", "cooked", "raw", "boiled", "roasted", "toasted",
        "divided", "plus", "extra", "to", "serve", "serving", "taste", "optional",
        "large", "medium", "small", "about", "approximately", "such", "as", "or",
        "homemade", "store", "bought", "low", "sodium", "free", "range", "quality",
        "good", "into", "cut", "pieces", "piece", "at", "room", "temperature", "for",
        "garnish", "needed", "and", "the", "a", "an", "of", "with", "in", "on",
        "kosher", "prepared", "thinly", "deseeded", "sticks", "stick", "ribs", "rib",
        "works", "well", "note", "see", "preferably", "boat", "tikka", "shoulder",
        "chuck", "fat", "canned", "cans", "can", "packets", "packet", "thick", "thin",
        # ES preparacion
        "picado", "picada", "picados", "picadas", "cortado", "cortada", "cortados",
        "troceado", "troceada", "rallado", "rallada", "molido", "molida", "cocido",
        "cocida", "cocidos", "cocidas", "cocinado", "cocinada", "cocinados",
        "cocinadas", "crudo", "cruda", "fresco", "fresca", "frescos",
        "seco", "seca", "pelado", "pelada", "laminado", "laminada", "finamente",
        "opcional", "gusto", "acompañar", "decorar", "necesaria", "cantidad", "trozos",
        "trozo", "hermoso", "grande", "pequeño", "mediano", "aprox", "aproximadamente",
        "para", "de", "la", "el", "los", "las", "con", "sin", "y", "o", "un", "una",
        "al", "en",
        # ES estados/adjetivos que estorban al casar con el catalogo (anadidos tras
        # revisar los "sin match" reales: cebolla blanca/morada, tomate maduro...).
        "maduro", "madura", "maduros", "maduras", "morado", "morada", "morados",
        "moradas", "larga", "largo", "largas", "largos", "leudante", "comun", "comunes",
        "derretido", "derretida", "derretidos", "derretidas", "esencia", "freir",
        "templado", "templada", "tibio", "tibia", "caliente", "fria", "frio", "frias",
        "frios", "verdeo", "mediana", "medianas", "pellizco", "punado", "chorrito",
        "hojuelas", "batido", "batida", "hermosa", "gordo", "gorda", "limpio", "limpia",
        "grueso", "gruesa", "entera", "entero", "enteras", "enteros",
        # Colores que no cambian la identidad para casar con el supermercado
        # (cebolla blanca/roja, tomate rojo). "verde" NO se incluye: "judias
        # verdes" es otra hortaliza distinta de las "judias" secas.
        "blanco", "blanca", "blancos", "blancas", "rojo", "roja", "rojos", "rojas",
        # Palabras de preparacion/descriptor extra (revision de "sin match" reales).
        "ralladura", "extracto", "esencia", "olor", "abejas", "ave", "grano", "granos",
        "rama", "ramas", "cascara", "cascaras", "hojuela", "suficiente", "anillas",
        "anilla", "mediano", "medianos", "tierna", "tierno", "tiernas", "tiernos",
        "cabezona", "cabezonas", "chica", "chico", "chicas", "chicos", "sancochado",
        "sancochada", "sancochados", "sancochadas", "hervida", "hervido", "hervidas",
        "hervidos", "china", "chinas", "preparada", "preparado", "molida", "molido",
        "molidas", "molidos", "picada", "picado", "picadas", "picados", "trozo",
        "trozos", "pedazo", "pedazos", "pieza", "piezas", "diente", "dientes",
        "cucharada", "cucharadas", "cucharadita", "cucharaditas", "pizca", "punado",
        "manojo", "manojos", "lata", "latas", "bote", "botes", "paquete", "paquetes",
        "taza", "tazas", "vaso", "vasos", "copa", "copas", "chorro", "chorros",
        "gotas", "gota", "sobre", "sobres", "unidad", "unidades", "kg", "gr", "gramos",
        "litro", "litros", "ml", "cl", "agria", "agrio", "neutro", "neutra",
        "frescas", "pequena", "pequenas", "pequeno", "pequenos", "grandes",
        "pellizcos", "cubo", "cubos",
        "untar", "sarten", "colores", "media", "medio",
        "morada", "morado", "moradas", "morados", "cabezona",
        "dulce", "dulces", "salado", "salada", "salados", "saladas", "cocinada",
        "cocinado", "cocinadas", "cocinados", "asado", "asada", "asados", "asadas",
        "grande", "hermoso", "hermosa", "generoso", "generosa", "colmada", "colmado",
        "rasa", "raso", "opcional", "opcionales", "gusto", "necesario", "necesaria",
        # Unidades de volumen escritas (cc, centimetros cubicos) y variedades de
        # chile/aji (se casan a guindilla generica tras quitar la variedad).
        "centimetros", "cubicos", "cc", "cucharas", "cuchara", "chorrito",
        "serrano", "serranos", "guajillo", "guajillos",
        "ancho", "anchos", "morita", "moritas", "jalapeno", "jalapenos", "poblano",
        "poblanos", "habanero", "habaneros", "pasilla", "arbol",
        "panka", "limo", "rocoto", "desgranada", "desgranadas", "desgranado",
        "enlatada", "enlatadas", "enlatado", "enlatados", "aerosol", "engrasar",
        "montada", "montado", "batir", "soletilla", "coccion", "aromatica",
        "aromaticas", "seco", "seca", "secos", "secas",
        # Formas de corte / troceado y otros descriptores (ejemplos del usuario).
        "cuadritos", "cuadrados", "cuadrado", "cuadrada", "cuadradas", "tiritas",
        "tira", "tiras", "rebanado", "rebanada", "rebanadas", "rebanados", "delgado",
        "delgada", "delgados", "delgadas", "cabeza", "cabezas", "pepitas", "pepita",
        "licuado", "licuada", "licuados", "licuadas", "muy", "fino", "fina", "finos",
        "finas", "barra", "barras", "brocheta", "brochetas", "madera", "palillo",
        "palillos", "bola", "bolas", "trozo", "trozos", "cuadrito", "juliana",
        "bastones", "baston", "laminas", "lamina", "gajos", "gajo", "aros", "aro",
        "bolsa", "bolsas", "ramita", "ramitas", "ramo", "puno", "cuncho",
    }
)
