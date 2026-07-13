from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 5

# Columnas añadidas despues de la creacion inicial de cada tabla. Si la tabla ya
# existe (BD de una version anterior), se agregan con ALTER TABLE de forma
# idempotente, para no perder los datos ya cargados.
_COLUMNAS_EVOLUTIVAS: dict[str, list[tuple[str, str]]] = {
    "productos": [
        ("energia_kcal_100g", "REAL"),
        ("grasas_100g", "REAL"),
        ("grasas_sat_100g", "REAL"),
        ("hidratos_100g", "REAL"),
        ("azucares_100g", "REAL"),
        ("proteinas_100g", "REAL"),
        ("sal_100g", "REAL"),
        ("fibra_100g", "REAL"),
        ("ingredientes", "TEXT"),
        ("origen", "TEXT"),
        ("base_nutricional", "TEXT"),
        ("fecha_enriquecimiento", "TEXT"),
        ("ean", "TEXT"),
        ("nutri_score", "TEXT"),
        ("nova", "INTEGER"),
        ("alergenos", "TEXT"),
        ("off_product_name", "TEXT"),
        ("off_match_score", "REAL"),
        ("fecha_off", "TEXT"),
        # Origen de la nutricion: 'bop' (dato real de Alcampo) | 'estimada' (tabla
        # de composicion USDA/BEDCA para frescos sin etiqueta).
        ("fuente_nutricion", "TEXT"),
        # 1 si la FIBRA (fibra_100g) se rellenó por estimacion (el resto de macros
        # puede ser real de 'bop'); la fibra apenas viene en la etiqueta de Alcampo.
        ("fibra_estimada", "INTEGER"),
    ],
    "receta_ingredientes": [
        ("cantidad_metrica", "REAL"),
        ("unidad_metrica", "TEXT"),
    ],
    "recetas": [
        # Apta para batchcooking (cocinar en tanda, aguanta/transporta bien y se
        # come recalentada). 1/0; NULL hasta clasificar (menu-app-clasificar-batchcooking).
        ("es_batchcooking", "INTEGER"),
        # Rol en el menu: 'principal' | 'postre' | 'desayuno' | 'guarnicion'.
        # NULL hasta clasificar (menu-app-clasificar-platos).
        ("rol", "TEXT"),
        # 1 si el usuario la marco como FAVORITA (se prioriza en el menu, sin
        # saltarse coste ni bandas de nutrientes). Recetas manuales: fuente='manual'.
        ("es_favorita", "INTEGER"),
        # Marcas del editor de recetas: apta como PLATO UNICO (cuenta para los dias
        # batchcooking) y pensada para CENA (aptitud de cena maxima).
        ("es_plato_unico", "INTEGER"),
        ("es_cena", "INTEGER"),
    ],
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productos (
    retailer_product_id TEXT PRIMARY KEY,
    nombre              TEXT NOT NULL,
    marca               TEXT,
    categoria           TEXT NOT NULL,
    subcategoria        TEXT,
    precio_eur          REAL,
    precio_por_unidad   REAL,
    unidad_medida       TEXT,
    formato             TEXT,
    cantidad_formato    REAL,
    unidad_formato      TEXT,
    cantidad_base_g_ml  REAL,
    tipo_medida         TEXT,
    disponible          INTEGER NOT NULL,
    en_oferta           INTEGER NOT NULL,
    precio_oferta       REAL,
    url_producto        TEXT NOT NULL,
    url_imagen          TEXT,
    apto_receta         INTEGER NOT NULL,
    fecha_extraccion    TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    -- Enriquecimiento nutricional (endpoint `bop`); NULL hasta enriquecer.
    energia_kcal_100g   REAL,
    grasas_100g         REAL,
    grasas_sat_100g     REAL,
    hidratos_100g       REAL,
    azucares_100g       REAL,
    proteinas_100g      REAL,
    sal_100g            REAL,
    fibra_100g          REAL,
    ingredientes        TEXT,
    origen              TEXT,
    base_nutricional    TEXT,
    fecha_enriquecimiento TEXT,
    -- Cruce con Open Food Facts (por nombre+marca); NULL hasta cruzar.
    ean                 TEXT,
    nutri_score         TEXT,
    nova                INTEGER,
    alergenos           TEXT,
    off_product_name    TEXT,
    off_match_score     REAL,
    fecha_off           TEXT
);

CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos (categoria, subcategoria);
CREATE INDEX IF NOT EXISTS idx_productos_apto ON productos (apto_receta);

-- Historico de precios: una fila cada vez que el precio de un producto cambia,
-- para el scraping incremental (solo deltas de precio) del plan original.
CREATE TABLE IF NOT EXISTS precios_historico (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    retailer_product_id TEXT NOT NULL,
    fecha               TEXT NOT NULL,
    precio_eur          REAL,
    FOREIGN KEY (retailer_product_id) REFERENCES productos (retailer_product_id)
);

CREATE INDEX IF NOT EXISTS idx_historico_producto
    ON precios_historico (retailer_product_id, fecha);

-- Recetas (Fase 3), extraidas de webs ES con recipe-scrapers.
CREATE TABLE IF NOT EXISTS recetas (
    id                TEXT PRIMARY KEY,
    url               TEXT NOT NULL UNIQUE,
    fuente            TEXT,
    titulo            TEXT NOT NULL,
    raciones          INTEGER,
    tiempo_total_min  INTEGER,
    categoria         TEXT,
    cocina            TEXT,
    rating            REAL,
    rating_count      INTEGER,
    imagen            TEXT,
    instrucciones     TEXT,
    fecha_ingesta     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receta_ingredientes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    receta_id          TEXT NOT NULL,
    orden              INTEGER NOT NULL,
    texto_original     TEXT NOT NULL,
    cantidad           REAL,
    unidad             TEXT,
    nombre             TEXT,
    nombre_normalizado TEXT,
    cantidad_metrica   REAL,
    unidad_metrica     TEXT,
    FOREIGN KEY (receta_id) REFERENCES recetas (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ing_receta ON receta_ingredientes (receta_id);
CREATE INDEX IF NOT EXISTS idx_ing_nombre ON receta_ingredientes (nombre_normalizado);

-- Planes de menu generados (Fase 6): un plan agrupa N semanas; cada fila es una
-- semana con su seleccion serializada (JSON) para poder navegar entre semanas y
-- construir la lista de la compra del plan completo.
CREATE TABLE IF NOT EXISTS planes (
    plan_id  TEXT NOT NULL,
    semana   INTEGER NOT NULL,       -- 1..N dentro del plan
    creado   TEXT NOT NULL,
    datos    TEXT NOT NULL,          -- JSON del menu de esa semana
    PRIMARY KEY (plan_id, semana)
);

-- Mapeo ingrediente de receta -> producto de Alcampo (Fase 4).
CREATE TABLE IF NOT EXISTS mapeo_ingr_producto (
    ingrediente_norm    TEXT PRIMARY KEY,   -- receta_ingredientes.nombre_normalizado
    clave_matching      TEXT,               -- ingrediente limpio+traducido usado para casar
    retailer_product_id TEXT,               -- producto casado (NULL si no hay match fiable)
    producto_nombre     TEXT,
    score               REAL,
    metodo              TEXT,               -- 'lexico' | 'embedding' | 'llm'
    fecha               TEXT NOT NULL
    -- Sin FK a productos: es una tabla derivada/cache; el rid es informativo y
    -- no debe bloquear si el catalogo se reextrae.
);

-- Indices para acelerar joins/filtros del optimizador y la lista de la compra (#83).
-- (Los que dependen de columnas evolutivas —rol, es_batchcooking— se crean en init_db
-- DESPUES de _migrar_columnas, ver _INDICES_POST_MIGRACION.)
CREATE INDEX IF NOT EXISTS idx_mapeo_rid ON mapeo_ingr_producto (retailer_product_id);
CREATE INDEX IF NOT EXISTS idx_recetas_fuente ON recetas (fuente);
"""

# Indices sobre columnas que se añaden por ALTER (_migrar_columnas): se crean despues.
_INDICES_POST_MIGRACION = (
    "CREATE INDEX IF NOT EXISTS idx_recetas_rol ON recetas (rol)",
    "CREATE INDEX IF NOT EXISTS idx_recetas_bc ON recetas (es_batchcooking)",
)


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL + busy_timeout: permite que un proceso lea/escriba mientras otro
    # (p.ej. el enriquecimiento en segundo plano) esta escribiendo, sin
    # "database is locked".
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    _migrar_columnas(conn)
    for sql in _INDICES_POST_MIGRACION:  # tras la migracion: columnas ya existen
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "INSERT INTO meta (clave, valor) VALUES ('schema_version', ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _migrar_columnas(conn: sqlite3.Connection) -> None:
    """Añade columnas que falten (BD creada con una version anterior del esquema)."""
    for tabla, columnas in _COLUMNAS_EVOLUTIVAS.items():
        existentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({tabla})")}
        for columna, tipo in columnas:
            if columna not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
