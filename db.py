import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "cars.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    cid        TEXT    NOT NULL,
    scraped_at TEXT    NOT NULL,
    source     TEXT    NOT NULL DEFAULT 'taladrod',
    run_id     INTEGER,
    yr4        INTEGER,
    mk         INTEGER,
    md         INTEGER,
    bd         INTEGER,
    ta         INTEGER,
    amake      TEXT,
    amodel     TEXT,
    abody      TEXT,
    atrim      TEXT,
    namemmt    TEXT,
    title      TEXT,
    prc        INTEGER,
    sbaht      TEXT,
    prvprc     TEXT,
    pcdisc     INTEGER,
    dpmt       TEXT,
    cbt        TEXT,
    isnew      TEXT,
    issold     TEXT,
    ishot      TEXT,
    isdp       TEXT,
    isvo       TEXT,
    isdprc     TEXT,
    upd        TEXT,
    ipgvw      INTEGER,
    ireg       TEXT,
    img        TEXT,
    url        TEXT,
    location   TEXT,
    raw_json   TEXT,
    PRIMARY KEY (cid, scraped_at)
);

CREATE INDEX IF NOT EXISTS idx_listings_cid     ON listings(cid);
CREATE INDEX IF NOT EXISTS idx_listings_scraped ON listings(scraped_at);
CREATE INDEX IF NOT EXISTS idx_listings_source  ON listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_make    ON listings(amake);
CREATE INDEX IF NOT EXISTS idx_listings_year    ON listings(yr4);
CREATE INDEX IF NOT EXISTS idx_listings_price   ON listings(prc);
CREATE INDEX IF NOT EXISTS idx_listings_run     ON listings(run_id);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL DEFAULT 'taladrod',
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    queries_run  INTEGER DEFAULT 0,
    cars_seen    INTEGER DEFAULT 0,
    cars_unique  INTEGER DEFAULT 0,
    status       TEXT,
    error        TEXT,
    note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_source ON scrape_runs(source);

CREATE TABLE IF NOT EXISTS makes (
    mk         TEXT PRIMARY KEY,
    name       TEXT,
    first_seen TEXT,
    last_seen  TEXT,
    last_count INTEGER
);

CREATE TABLE IF NOT EXISTS models (
    mk         TEXT NOT NULL,
    md         TEXT NOT NULL,
    name       TEXT,
    first_seen TEXT,
    last_seen  TEXT,
    PRIMARY KEY (mk, md)
);

CREATE VIEW IF NOT EXISTS latest_listings AS
SELECT l.*
FROM listings l
JOIN (SELECT MAX(scraped_at) AS ts FROM listings) m
  ON l.scraped_at = m.ts;

CREATE VIEW IF NOT EXISTS listings_named AS
SELECT
    l.*,
    COALESCE(NULLIF(l.amake, ''),  mk_t.name)  AS make_name,
    COALESCE(NULLIF(l.amodel, ''), md_t.name)  AS model_name
FROM listings l
LEFT JOIN makes  mk_t ON CAST(mk_t.mk AS INTEGER) = l.mk
LEFT JOIN models md_t ON CAST(md_t.mk AS INTEGER) = l.mk
                     AND CAST(md_t.md AS INTEGER) = l.md;
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def init():
    """Create schema, then add columns idempotently for already-existing DBs."""
    conn = connect()
    conn.executescript(SCHEMA)
    # Online migrations: ALTER TABLE ADD COLUMN is metadata-only and safe even
    # while a writer is open, since SQLite stores added columns as virtual
    # NULLs/defaults for existing rows.
    listing_cols = _columns(conn, "listings")
    for col, ddl in [
        ("source",   "TEXT NOT NULL DEFAULT 'taladrod'"),
        ("url",      "TEXT"),
        ("location", "TEXT"),
    ]:
        if col not in listing_cols:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {ddl}")
    run_cols = _columns(conn, "scrape_runs")
    if "source" not in run_cols:
        conn.execute("ALTER TABLE scrape_runs ADD COLUMN source TEXT NOT NULL DEFAULT 'taladrod'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init()
    print(f"DB ready: {DB_PATH}")
