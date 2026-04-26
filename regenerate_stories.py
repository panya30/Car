"""Regenerate every cohort's Story Unit and persist to the cached_stories table.

Pipeline step that runs after each scrape pass. The UI's /stories page
reads from this table (fast, deterministic) instead of recomputing on every
request. Also enqueues alerts for newly-detected anomalies.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from db import connect, init
import story_unit as su


def cohort_key(make: str, model: str, year: int) -> str:
    return f"{make.upper()}|{model.upper()}|{year}"


def discover_cohorts(conn, *, min_listings: int = 25) -> list[tuple[str, str, int]]:
    """Find every (make, model, year) cohort that has enough listings to
    compute meaningful percentile statistics."""
    rows = conn.execute("""
        WITH latest AS (
          SELECT cid, MAX(scraped_at) AS ts FROM listings GROUP BY cid
        ),
        data AS (
          SELECT l.* FROM listings l
          JOIN latest lt ON lt.cid = l.cid AND lt.ts = l.scraped_at
          WHERE l.prc > 50000 AND l.amake IS NOT NULL
            AND l.amodel IS NOT NULL AND l.yr4 IS NOT NULL
        )
        SELECT UPPER(amake) AS make, UPPER(amodel) AS model, yr4, COUNT(*) AS n
        FROM data
        GROUP BY UPPER(amake), UPPER(amodel), yr4
        HAVING COUNT(*) >= ?
        ORDER BY n DESC
    """, (min_listings,)).fetchall()
    return [(r["make"], r["model"], r["yr4"]) for r in rows]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def regenerate(conn, *, min_listings: int = 25,
               max_cohorts: int | None = None) -> dict:
    """Recompute every cohort's story; INSERT/REPLACE into cached_stories.

    Returns counts: cohorts processed, stories written, anomalies queued.
    """
    cohorts = discover_cohorts(conn, min_listings=min_listings)
    if max_cohorts:
        cohorts = cohorts[:max_cohorts]

    now = now_iso()
    n_written = 0
    n_anomaly = 0
    new_alerts: list[tuple] = []

    for make, model, year in cohorts:
        rows = su.fetch_cohort(conn, make, model, year)
        if len(rows) < min_listings:
            continue
        s = su.compute_stats(rows)
        result = su.find_best_deal(rows, s)
        if not result:
            continue
        deal, classification = result
        discount = (s.median_prc - deal.prc) / s.median_prc * 100
        km_gap = (
            (s.median_km - deal.mileage_km) / s.median_km * 100
            if (deal.mileage_km and s.median_km) else None
        )
        ck = cohort_key(make, model, year)
        # Compact JSON payload — UI rebuilds drivers/counterpoints if it wants
        story_payload = {
            "cohort": {"make": make, "model": model, "year": year},
            "stats": {
                "n": s.n, "n_sources": s.n_sources,
                "median_prc": s.median_prc, "p10_prc": s.p10_prc,
                "p25_prc": s.p25_prc, "p75_prc": s.p75_prc, "p90_prc": s.p90_prc,
                "median_km": s.median_km, "p25_km": s.p25_km, "p75_km": s.p75_km,
                "topColors": [{"value": v, "n": n} for v, n in s.color_top],
                "topFuels":  [{"value": v, "n": n} for v, n in s.fuel_top],
            },
            "deal": {
                "cid": deal.cid, "source": deal.source, "prc": deal.prc,
                "yr4": deal.yr4, "title": deal.title, "url": deal.url,
                "img": deal.img, "mileage_km": deal.mileage_km,
                "color": deal.color, "fuel": deal.fuel,
                "transmission": deal.transmission, "body_type": deal.body_type,
                "seller_name": deal.seller_name, "location": deal.location,
            },
            "classification": classification,
            "discount_pct": discount,
            "km_gap_pct": km_gap,
        }
        conn.execute(
            """INSERT INTO cached_stories
               (cohort_key, make, model, yr4, classification, cid, source,
                discount_pct, km_gap_pct, story_json, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(cohort_key) DO UPDATE SET
                 classification=excluded.classification,
                 cid=excluded.cid, source=excluded.source,
                 discount_pct=excluded.discount_pct, km_gap_pct=excluded.km_gap_pct,
                 story_json=excluded.story_json, generated_at=excluded.generated_at""",
            (ck, make, model, year, classification, deal.cid, deal.source,
             discount, km_gap, json.dumps(story_payload, ensure_ascii=False),
             now),
        )
        n_written += 1
        if classification == "anomaly":
            n_anomaly += 1
            new_alerts.append((
                "anomaly", deal.cid, ck, "warn",
                f"⚠️ {year} {make} {model} priced {discount:.0f}% below median with "
                f"{km_gap:.0f}% mileage gap",
                f"This is the rollback / flood-rebrand signature in the Thai used-car "
                f"market. Verify or walk away.",
                json.dumps(story_payload, ensure_ascii=False),
                now,
            ))
        elif classification == "deal" and discount > 18:
            new_alerts.append((
                "deal", deal.cid, ck, "info",
                f"🟢 {year} {make} {model} — {discount:.0f}% below median",
                f"Top-quartile deal in the {ck} cohort. Anchor at "
                f"฿{int(deal.prc * 0.93):,}.",
                json.dumps(story_payload, ensure_ascii=False),
                now,
            ))

    # Insert alerts, but skip duplicates: same cid + kind already alerted
    # within the last 7 days. (Avoids re-alerting on every scrape.)
    skipped = 0
    for alert in new_alerts:
        kind, cid = alert[0], alert[1]
        existing = conn.execute(
            """SELECT 1 FROM alerts
               WHERE cid = ? AND kind = ?
                 AND datetime(created_at) > datetime('now', '-7 days')""",
            (cid, kind),
        ).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO alerts
               (kind, cid, cohort_key, severity, title, detail, payload_json,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            alert,
        )

    conn.commit()
    return {
        "cohorts": len(cohorts),
        "stories_written": n_written,
        "anomalies_seen": n_anomaly,
        "alerts_queued": len(new_alerts) - skipped,
        "alerts_skipped_duplicate": skipped,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-listings", type=int, default=25)
    ap.add_argument("--max-cohorts", type=int, default=None)
    args = ap.parse_args()
    init()
    conn = connect()
    summary = regenerate(
        conn, min_listings=args.min_listings, max_cohorts=args.max_cohorts,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
