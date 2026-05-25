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


def cohort_key(make: str, model: str, year: int,
               engine_size: float | None = None) -> str:
    es_part = f"|{engine_size:.1f}" if engine_size else "|?"
    return f"{make.upper()}|{model.upper()}|{year}{es_part}"


def discover_cohorts(
    conn, *, min_listings: int = 15,
) -> list[tuple[str, str, int, float | None]]:
    """Find every (make, model, year, engine_size) cohort with enough
    listings to compute meaningful percentile statistics. Cohorts where
    engine_size is missing fall through as None — handled separately at
    the caller (typically excluded so we don't mix trims)."""
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
        SELECT UPPER(amake) AS make, UPPER(amodel) AS model, yr4,
               engine_size, COUNT(*) AS n
        FROM data
        GROUP BY UPPER(amake), UPPER(amodel), yr4, engine_size
        HAVING COUNT(*) >= ? AND engine_size IS NOT NULL
        ORDER BY n DESC
    """, (min_listings,)).fetchall()
    return [(r["make"], r["model"], r["yr4"], r["engine_size"]) for r in rows]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def regenerate(conn, *, min_listings: int = 15,
               max_cohorts: int | None = None,
               polish: bool = False, polish_top: int = 12) -> dict:
    """Recompute every cohort's story; INSERT/REPLACE into cached_stories.

    Cohorts now key on (make, model, year, engine_size) so a Ford Ranger
    XL 2.2 doesn't get compared against a Ranger Wildtrak 3.0. Listings
    where engine_size is missing are skipped — better to omit than to
    surface a misleading "DEAL".

    Returns counts: cohorts processed, stories written, anomalies queued.
    """
    cohorts = discover_cohorts(conn, min_listings=min_listings)
    if max_cohorts:
        cohorts = cohorts[:max_cohorts]
    # Wipe the cache so removed cohorts (e.g. mixed-trim ones from before
    # the engine_size split) don't linger as zombie entries.
    conn.execute("DELETE FROM cached_stories")

    now = now_iso()
    n_written = 0
    n_anomaly = 0
    new_alerts: list[tuple] = []

    for make, model, year, engine_size in cohorts:
        rows = su.fetch_cohort(conn, make, model, year, engine_size=engine_size)
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
        ck = cohort_key(make, model, year, engine_size)
        # Compact JSON payload — UI rebuilds drivers/counterpoints if it wants
        story_payload = {
            "cohort": {
                "make": make, "model": model, "year": year,
                "engine_size": engine_size,
            },
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
            es_label = f" {engine_size:.1f}L" if engine_size else ""
            new_alerts.append((
                "anomaly", deal.cid, ck, "warn",
                f"⚠️ {year} {make} {model}{es_label} priced {discount:.0f}% below "
                f"median with {km_gap:.0f}% mileage gap",
                f"This is the rollback / flood-rebrand signature in the Thai used-car "
                f"market. Verify or walk away.",
                json.dumps(story_payload, ensure_ascii=False),
                now,
            ))
        elif classification == "deal" and discount > 18:
            es_label = f" {engine_size:.1f}L" if engine_size else ""
            new_alerts.append((
                "deal", deal.cid, ck, "info",
                f"🟢 {year} {make} {model}{es_label} — {discount:.0f}% below median",
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

    # --- optional LLM polish for the top-N stories ---------------------
    n_polished = 0
    polish_skipped = ""
    if polish:
        import os, llm_polish
        if not os.environ.get("OPENAI_API_KEY"):
            polish_skipped = "OPENAI_API_KEY not set"
        else:
            top = conn.execute("""
                SELECT cohort_key, story_json
                FROM cached_stories
                WHERE llm_polished IS NULL
                ORDER BY
                  CASE classification
                    WHEN 'anomaly' THEN 0
                    WHEN 'deal'    THEN 1
                    ELSE 2 END,
                  ABS(discount_pct) DESC
                LIMIT ?
            """, (polish_top,)).fetchall()
            for r in top:
                try:
                    skeleton = _payload_to_markdown(json.loads(r["story_json"]))
                    polished = llm_polish.polish_story(skeleton)
                except Exception as e:
                    print(f"  polish err {r['cohort_key']}: {e}")
                    continue
                conn.execute(
                    "UPDATE cached_stories SET llm_polished = ? WHERE cohort_key = ?",
                    (polished, r["cohort_key"]),
                )
                n_polished += 1
            conn.commit()

    return {
        "cohorts": len(cohorts),
        "stories_written": n_written,
        "anomalies_seen": n_anomaly,
        "alerts_queued": len(new_alerts) - skipped,
        "alerts_skipped_duplicate": skipped,
        "stories_polished": n_polished,
        "polish_note": polish_skipped or ("polished top " + str(polish_top) if polish else "skipped"),
    }


def _payload_to_markdown(p: dict) -> str:
    """Render the cached payload back into the Story Unit markdown that
    llm_polish.SYSTEM_PROMPT was tuned against."""
    deal = p.get("deal", {})
    stats = p.get("stats", {})
    cohort = p.get("cohort", {})
    cls = p.get("classification", "fair")
    discount = p.get("discount_pct") or 0
    engine = cohort.get("engine_size")
    title = (deal.get("title")
             or f"{cohort.get('year')} {cohort.get('make')} {cohort.get('model')}")
    badges = {
        "anomaly":    "🚩 **ANOMALY — verify before deposit**",
        "deal":       "🟢 **DEAL — top-25% value**",
        "fair":       "🟡 **FAIR — priced near cohort median**",
        "overpriced": "🔴 **OVERPRICED — above cohort median**",
    }

    def km_cell(v):
        return f"{int(v):,} km" if v else "—"

    def prc_cell(v):
        return f"฿{int(v or 0):,}"

    es_label = f" {engine:.1f}L" if engine else ""
    src = (deal.get("source") or "").upper()
    cid = deal.get("cid")
    deal_prc = int(deal.get("prc") or 0)
    median = int(stats.get("median_prc") or 0)

    lines = [
        f"# {title}",
        "",
        f"**[{src}]**  ·  cid `{cid}`",
        "",
        badges.get(cls, ""),
        "",
        "## 1. Hook",
        "",
        f"**{cohort.get('year')} {cohort.get('make')} {cohort.get('model')}{es_label}** "
        f"listed at **฿{deal_prc:,}** — **{discount:.0f}%** below the cohort "
        f"median of **฿{median:,}**.",
        "",
        "## 2. Context",
        "",
        f"Cohort: {cohort.get('make')} {cohort.get('model')} {cohort.get('year')}"
        f"{es_label}, {stats.get('n')} listings across "
        f"{stats.get('n_sources')} source(s).",
        "",
        "| Percentile | Price | Mileage |",
        "|---:|---:|---:|",
        f"| P10 | {prc_cell(stats.get('p10_prc'))} | — |",
        f"| P25 | {prc_cell(stats.get('p25_prc'))} | {km_cell(stats.get('p25_km'))} |",
        f"| **P50** | **{prc_cell(stats.get('median_prc'))}** | "
        f"**{km_cell(stats.get('median_km'))}** |",
        f"| P75 | {prc_cell(stats.get('p75_prc'))} | {km_cell(stats.get('p75_km'))} |",
        f"| P90 | {prc_cell(stats.get('p90_prc'))} | — |",
        "",
        "## 3. Drivers",
        "",
    ]
    if deal.get("mileage_km") and stats.get("median_km"):
        lines.append(
            f"- Mileage: **{int(deal['mileage_km']):,} km** vs cohort median "
            f"**{int(stats['median_km']):,} km**"
        )
    if deal.get("color"):       lines.append(f"- Color: **{deal['color']}**")
    if deal.get("transmission"): lines.append(f"- Transmission: {deal['transmission']}")
    if deal.get("fuel"):        lines.append(f"- Fuel: {deal['fuel']}")
    if deal.get("location"):    lines.append(f"- Location: {deal['location']}")
    if deal.get("seller_name"): lines.append(f"- Seller: {deal['seller_name']}")

    walk_away = int(stats.get("p25_prc") or 0)
    headroom = median - deal_prc
    lines += [
        "",
        "## 4. Counterpoints",
        "",
        "- Always commission an independent inspection before deposit "
        "(Thai market: flood + odometer rollback risk).",
        "",
        "## 5. Action",
        "",
        f"- Anchor offer: ฿{int(deal_prc * 0.93):,}",
        f"- Walk-away above: ฿{walk_away:,}",
        f"- Headroom to median: ฿{headroom:,}",
        "",
        "## 6. Track",
        "",
        f"- Watch CID `{cid}` — alert on price drops or sale.",
        f"- Track cohort weekly to validate the P50 estimate of ฿{median:,}.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-listings", type=int, default=15)
    ap.add_argument("--max-cohorts", type=int, default=None)
    ap.add_argument("--polish", action="store_true",
                    help="LLM-polish the top-N stories")
    ap.add_argument("--polish-top", type=int, default=12)
    args = ap.parse_args()
    init()
    conn = connect()
    summary = regenerate(
        conn,
        min_listings=args.min_listings,
        max_cohorts=args.max_cohorts,
        polish=args.polish,
        polish_top=args.polish_top,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
