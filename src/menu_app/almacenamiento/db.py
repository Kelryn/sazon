from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
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
        # Etiquetas separadas por coma (rapido, picante, niños...) para filtrar
        # recetas por afinidad (#46). NULL/"" = sin etiquetas.
        ("tags", "TEXT"),
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

-- Sinonimos del usuario (#22/#14): palabra -> reemplazo, aplicado al normalizar el
-- ingrediente antes de casar. Permite corregir el matching de forma reutilizable.
CREATE TABLE IF NOT EXISTS sinonimos_usuario (
    palabra   TEXT PRIMARY KEY,
    reemplazo TEXT NOT NULL,
    fecha     TEXT NOT NULL
);

-- Valoracion personal de recetas YA COCINADAS (Lote 12): un baremo (sabor,
-- frescura, se_repetiria...) por fila, 1-5 estrellas. Re-valorar (UPDATE) es
-- normal: pisa la fila anterior de ese mismo baremo, no acumula historial.
-- Sin FK a recetas: si se borra una receta, sus valoraciones quedan huerfanas
-- mas no deben impedir borrarla (mismo criterio que mapeo_ingr_producto).
CREATE TABLE IF NOT EXISTS valoraciones (
    receta_id TEXT NOT NULL,
    baremo    TEXT NOT NULL,
    estrellas INTEGER NOT NULL,
    fecha     TEXT NOT NULL,
    PRIMARY KEY (receta_id, baremo)
);

-- Detalle cualitativo de una valoracion (#Lote12): que ingrediente o que parte
-- del metodo de preparacion gusto especialmente, para el recomendador por
-- similitud. Se BORRA y se vuelve a insertar entera en cada guardado (no es un
-- historial acumulativo, es "lo que se destaca de la ultima valoracion").
CREATE TABLE IF NOT EXISTS valoracion_detalle (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    receta_id TEXT NOT NULL,
    tipo      TEXT NOT NULL,  -- 'ingrediente' | 'metodo'
    valor     TEXT NOT NULL,
    fecha     TEXT NOT NULL
);

-- Indices para acelerar joins/filtros del optimizador y la lista de la compra (#83).
-- (Los que dependen de columnas evolutivas —rol, es_batchcooking— se crean en init_db
-- DESPUES de _migrar_columnas, ver _INDICES_POST_MIGRACION.)
CREATE INDEX IF NOT EXISTS idx_mapeo_rid ON mapeo_ingr_producto (retailer_product_id);
CREATE INDEX IF NOT EXISTS idx_recetas_fuente ON recetas (fuente);
CREATE INDEX IF NOT EXISTS idx_valoracion_detalle_receta ON valoracion_detalle (receta_id);
"""

# Indices sobre columnas que se añaden por ALTER (_migrar_columnas): se crean despues.
_INDICES_POST_MIGRACION = (
    "CREATE INDEX IF NOT EXISTS idx_recetas_rol ON recetas (rol)",
    "CREATE INDEX IF NOT EXISTS idx_recetas_bc ON recetas (es_batchcooking)",
)

# Migraciones de esquema NO aditivas (#84): las versiones 1-5 solo añadieron
# columnas nuevas (NULL por defecto), ya cubierto de forma idempotente por
# _COLUMNAS_EVOLUTIVAS/_migrar_columnas de arriba y no necesitan entrada aqui.
# Este registro es el mecanismo para cambios que ESO no puede expresar (rellenar
# datos, tocar una tabla existente, borrar algo obsoleto...): cada entrada se
# ejecuta UNA sola vez, en orden, la primera vez que se abre una BD cuyo
# schema_version guardado es menor que esa clave.
_MIGRACIONES: dict[int, Callable[[sqlite3.Connection], None]] = {}


def _version_guardada(conn: sqlite3.Connection) -> int:
    fila = conn.execute(
        "SELECT valor FROM meta WHERE clave = 'schema_version'"
    ).fetchone()
    return int(fila["valor"]) if fila else 0


def _aplicar_migraciones(conn: sqlite3.Connection) -> None:
    actual = _version_guardada(conn)
    for version in sorted(v for v in _MIGRACIONES if v > actual):
        _MIGRACIONES[version](conn)


def _activar_wal(conn: sqlite3.Connection) -> None:
    """Activa journal_mode=WAL con reintentos.

    Cambiar de modo por primera vez en un fichero recien creado pide un lock
    exclusivo breve; si dos conexiones lo intentan a la vez (p.ej. una tarea de
    fondo arrancando justo cuando llega la primera peticion web), SQLite puede
    fallar al instante con "database is locked" SIN respetar `busy_timeout`
    para este PRAGMA en concreto (limitacion conocida, no es un bug nuestro).
    Reintenta con backoff corto en vez de tumbar el arranque."""
    espera = 0.05
    for intento in range(20):
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower() or intento == 19:
                raise
            time.sleep(espera)
            espera = min(0.5, espera * 1.5)


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL + busy_timeout: permite que un proceso lea/escriba mientras otro
    # (p.ej. el enriquecimiento en segundo plano) esta escribiendo, sin
    # "database is locked".
    _activar_wal(conn)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)  # crea 'meta' si falta, necesaria para leer la version
    _aplicar_migraciones(conn)
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
    """Añade columnas que falten (BD creada con una version anterior del esquema).

    Tolera la carrera entre dos `init_db()` concurrentes sobre el mismo fichero
    (p.ej. una tarea de fondo y la primera peticion web arrancando a la vez):
    si otra conexion ya añadio la columna entre el PRAGMA y el ALTER, ignora el
    "duplicate column name" en vez de tumbar el arranque."""
    for tabla, columnas in _COLUMNAS_EVOLUTIVAS.items():
        existentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({tabla})")}
        for columna, tipo in columnas:
            if columna not in existentes:
                try:
                    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        raise
