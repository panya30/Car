"""Cross-source listing matcher — find the same car listed on multiple sites.

Same VIN cars get listed on both Taladrod AND Kaidee with different prices,
sometimes weeks apart. Detecting these reveals:
  * arbitrage signal (one source priced 10%+ above another)
  * stale inventory (listing on multi-sources but neither sells = overpriced)
  * dealer footprint (which dealers post everywhere)

We don't have VINs, but we have a cheap-but-effective signature:

    sig = (make, model_canonical, year, price_bucket_50k, mileage_bucket_20k)

Two listings sharing this signature across sources are *probable* matches.
False-positive rate is acceptable because the action is human inspection,
not automated buying.

Output: writes a `matches` table:

    CREATE TABLE matches (
      group_id    TEXT,        -- the signature
      cid         TEXT,        -- listing
      source      TEXT,
      prc         INTEGER,
      mileage_km  INTEGER,
      url         TEXT,
      title       TEXT,
      yr4         INTEGER,
      delta_pct   REAL,        -- this price as % above group cheapest
      created_at  TEXT
    );

    CREATE TABLE match_groups (
      group_id    TEXT PRIMARY KEY,
      n_listings  INTEGER,
      n_sources   INTEGER,
      cheapest_prc INTEGER,
      dearest_prc  INTEGER,
      spread_pct  REAL,
      make TEXT, model TEXT, yr4 INTEGER,
      computed_at TEXT
    );
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone

from db import connect


SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    group_id    TEXT NOT NULL,
    cid         TEXT NOT NULL,
    source      TEXT NOT NULL,
    prc         INTEGER,
    mileage_km  INTEGER,
    url         TEXT,
    title       TEXT,
    yr4         INTEGER,
    delta_pct   REAL,
    created_at  TEXT,
    PRIMARY KEY (group_id, cid)
);

CREATE TABLE IF NOT EXISTS match_groups (
    group_id     TEXT PRIMARY KEY,
    n_listings   INTEGER,
    n_sources    INTEGER,
    cheapest_prc INTEGER,
    dearest_prc  INTEGER,
    spread_pct   REAL,
    make         TEXT,
    model        TEXT,
    yr4          INTEGER,
    computed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_matches_cid ON matches(cid);
CREATE INDEX IF NOT EXISTS idx_match_groups_spread ON match_groups(spread_pct DESC);
CREATE INDEX IF NOT EXISTS idx_match_groups_n_sources ON match_groups(n_sources DESC);
"""


def _model_canonical(s: str) -> str:
    """Normalise a model name so 'HILUX REVO' from kaidee matches 'HILUXREVO'
    from taladrod, etc. Strip whitespace, lowercase, remove punctuation."""
    if not s:
        return ""
    s = s.upper().strip()
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def _signature(make: str | None, model: str | None, yr4: int | None,
               prc: int | None, mileage_km: int | None) -> str | None:
    if not (make and model and yr4 and prc):
        return None
    mk = _model_canonical(make)
    md = _model_canonical(model)
    if not mk or not md:
        return None
    price_bucket = round(prc / 50_000)        # 50k baht bands
    mileage_bucket = (
        round(mileage_km / 20_000) if mileage_km else "?"
    )                                          # 20k km bands; '?' for missing
    return f"{mk}|{md}|{yr4}|p{price_bucket}|km{mileage_bucket}"


def rebuild(conn) -> dict:
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM matches")
    conn.execute("DELETE FROM match_groups")

    rows = conn.execute("""
        WITH latest AS (
          SELECT cid, MAX(scraped_at) AS ts FROM listings GROUP BY cid
        )
        SELECT l.cid, l.source, l.prc, l.yr4, l.amake, l.amodel,
               l.mileage_km, l.url, l.title, l.namemmt
        FROM listings l
        JOIN latest lt ON lt.cid = l.cid AND lt.ts = l.scraped_at
        WHERE l.prc IS NOT NULL AND l.amake IS NOT NULL AND l.amodel IS NOT NULL
              AND l.yr4 IS NOT NULL
    """).fetchall()

    groups: dict[str, list[dict]] = {}
    for r in rows:
        sig = _signature(
            r["amake"], r["amodel"], r["yr4"], r["prc"], r["mileage_km"],
        )
        if not sig:
            continue
        groups.setdefault(sig, []).append({
            "cid": r["cid"], "source": r["source"], "prc": r["prc"],
            "yr4": r["yr4"], "mileage_km": r["mileage_km"],
            "url": r["url"], "title": r["title"] or r["namemmt"],
            "make": r["amake"], "model": r["amodel"],
        })

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_groups = 0
    n_listings_in_matches = 0
    cross_source_groups = 0

    for sig, lst in groups.items():
        sources = {l["source"] for l in lst}
        # Only keep groups that span >=2 sources (true cross-source) or
        # >=3 listings within one source (potential dealer flips).
        if len(sources) < 2 and len(lst) < 3:
            continue
        prices = [l["prc"] for l in lst]
        cheapest = min(prices)
        dearest = max(prices)
        spread = (dearest - cheapest) / cheapest * 100 if cheapest else 0
        first = lst[0]
        conn.execute(
            """INSERT INTO match_groups
               (group_id, n_listings, n_sources, cheapest_prc, dearest_prc,
                spread_pct, make, model, yr4, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sig, len(lst), len(sources), cheapest, dearest, spread,
                first["make"].upper(), first["model"].upper(), first["yr4"],
                now,
            ),
        )
        for l in lst:
            delta = (l["prc"] - cheapest) / cheapest * 100 if cheapest else 0
            conn.execute(
                """INSERT INTO matches
                   (group_id, cid, source, prc, mileage_km, url, title,
                    yr4, delta_pct, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sig, l["cid"], l["source"], l["prc"], l["mileage_km"],
                    l["url"], l["title"], l["yr4"], delta, now,
                ),
            )
        n_groups += 1
        n_listings_in_matches += len(lst)
        if len(sources) >= 2:
            cross_source_groups += 1

    conn.commit()
    return {
        "groups": n_groups,
        "cross_source_groups": cross_source_groups,
        "listings_matched": n_listings_in_matches,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20,
                    help="show top N spreads after rebuild")
    args = ap.parse_args()

    conn = connect()
    summary = rebuild(conn)
    print(f"matched: {summary}")

    print(f"\n=== top {args.top} cross-source spreads ===")
    for r in conn.execute(f"""
        SELECT make, model, yr4, n_listings, n_sources,
               cheapest_prc, dearest_prc, spread_pct
        FROM match_groups
        WHERE n_sources >= 2
        ORDER BY spread_pct DESC
        LIMIT ?
    """, (args.top,)):
        d = dict(r)
        print(f"  {d['yr4']} {d['make']:<10} {d['model']:<14} "
              f"n={d['n_listings']:<2} src={d['n_sources']} "
              f"฿{d['cheapest_prc']:,} → ฿{d['dearest_prc']:,} "
              f"({d['spread_pct']:.0f}% spread)")


if __name__ == "__main__":
    main()
