-- Catalyst Radar :: Batch 1
-- Fuente de verdad: SQLite sobre el Railway Volume.
-- El snapshot a GitHub sigue siendo respaldo, no fuente de verdad.

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,   -- hash determinista: source + external_id
    source          TEXT NOT NULL,      -- anilist | tmdb | manual
    external_id     TEXT NOT NULL,

    ip_name         TEXT NOT NULL,      -- nombre canonico para mostrar
    aliases         TEXT NOT NULL,      -- JSON array: romaji, kana, ingles, synonyms
    search_terms    TEXT NOT NULL,      -- JSON array: lo que consume el matcher del Batch 2

    event_type      TEXT NOT NULL,      -- film_release | season_premiere | anniversary
    event_date      TEXT,               -- ISO YYYY-MM-DD, NULL si solo hay year/quarter
    date_precision  TEXT NOT NULL,      -- exact | month | quarter | rumor
    region          TEXT,               -- JP, CN, KR, US, GLOBAL

    audience_proxy  INTEGER DEFAULT 0,  -- popularity / favourites de la fuente
    source_url      TEXT,

    first_seen_at   TEXT NOT NULL,
    last_changed_at TEXT NOT NULL,
    raw             TEXT,               -- payload original, para depurar sin re-pedir

    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_events_date      ON events (event_date);
CREATE INDEX IF NOT EXISTS idx_events_precision ON events (date_precision);
CREATE INDEX IF NOT EXISTS idx_events_audience  ON events (audience_proxy DESC);

-- Bitacora de cambios. Aqui vive la feature principal del modulo:
-- una transicion de date_precision hacia 'exact' ES el catalizador de anuncio de fecha.
CREATE TABLE IF NOT EXISTS event_changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL REFERENCES events (id),
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    changed_at  TEXT NOT NULL,
    is_catalyst INTEGER NOT NULL DEFAULT 0,  -- 1 si el cambio en si mismo es una senal
    notified    INTEGER NOT NULL DEFAULT 0   -- lo consume el Batch 4
);

CREATE INDEX IF NOT EXISTS idx_changes_catalyst ON event_changes (is_catalyst, notified);
CREATE INDEX IF NOT EXISTS idx_changes_event    ON event_changes (event_id, changed_at DESC);

-- Snapshots de candidatos para BACKTEST hacia adelante.
-- DexScreener solo da liquidez/precio ACTUAL; guardando una foto por corrida se
-- construye la serie temporal que permite validar el scorer: los tickers que
-- puntuaron alto, ¿de verdad se movieron despues de su evento?
CREATE TABLE IF NOT EXISTS token_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,        -- YYYY-MM-DD (una foto por dia)
    ts            TEXT NOT NULL,         -- ISO completo
    event_id      TEXT,                  -- referencia al evento (events.id)
    ip_name       TEXT,
    event_date    TEXT,
    days_until    INTEGER,
    score         INTEGER,
    conflict      INTEGER DEFAULT 0,
    token_symbol  TEXT,
    token_address TEXT NOT NULL,
    token_chain   TEXT,
    liq           REAL,
    vol24         REAL,
    price         REAL,
    UNIQUE (snapshot_date, event_id, token_address)  -- idempotente por dia
);

CREATE INDEX IF NOT EXISTS idx_snap_token ON token_snapshots (token_address, ts);
CREATE INDEX IF NOT EXISTS idx_snap_event ON token_snapshots (event_id, ts);

-- Registro de corridas, para saber si un scheduler se cayo en silencio.
CREATE TABLE IF NOT EXISTS ingest_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    n_seen      INTEGER DEFAULT 0,
    n_new       INTEGER DEFAULT 0,
    n_changed   INTEGER DEFAULT 0,
    error       TEXT
);
