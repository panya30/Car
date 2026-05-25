"""Walk existing rows in `listings` and enrich them via detail-page fetch.

Usage:

    python enrich_details.py --source toyotasure
    python enrich_details.py --source taladrod --limit 500 --sleep 4
    python enrich_details.py --source carcarrod --reenrich  # redo even if filled

Each source plugs in its own detail-page fetcher + enricher; this script
just iterates rows that haven't been enriched yet, fetches the detail
page, runs the enricher to mutate a dict, then UPDATEs the row in-place.
Idempotent — partial runs resume cleanly.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone

from db import connect, init
from scrapers import _common as C
from scrapers import carcarrod, kaidee, toyotasure  # noqa: F401


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# (detail_url_builder, enricher) per source. detail_url_builder takes the
# row (dict-like) and returns the URL to fetch (None if not fetchable).
def _taladrod_url(row):
    cid = row["cid"].split(":", 1)[-1] if ":" in row["cid"] else row["cid"]
    # The taladrod scraper stores raw cid (no prefix) for legacy rows.
    return f"https://www.taladrod.com/w40/iCar/CarDet.aspx?cid={cid}"


SOURCES = {
    "toyotasure": (lambda r: r["url"], toyotasure._enrich_detail),
    "carcarrod":  (lambda r: r["url"], carcarrod._enrich_detail),
    "taladrod":   (_taladrod_url, lambda row, html: _taladrod_enrich(row, html)),
}

# --- taladrod-specific enricher (Thai-labelled HTML) -----------------------
import re

TALADROD_RES = {
    "mileage_km":   re.compile(r"เลขไมล์\s*([\d,]+)\s*กม", re.S),
    "transmission": re.compile(r"เกียร์(ออโต้|ธรรมดา)", re.S),
    "color":        re.compile(r"สี[^<:]*[:\s]*([฀-๿\w]+)", re.S),
    "fuel":         re.compile(r"(เบนซิน|ดีเซล|ไฮบริด|ไฟฟ้า|LPG|NGV|CNG|EV|HEV|PHEV)"),
    "ireg":         re.compile(r"ทะเบียน\s*([^\s|<]+\s*[^\s|<]*)"),
    "body_type":    re.compile(r"ตัวถัง\s*[:\s]*([^<\s|]+)"),
}


def _taladrod_enrich(row: dict, html: str) -> None:
    for col, pat in TALADROD_RES.items():
        if row.get(col):
            continue
        m = pat.search(html)
        if not m:
            continue
        val = m.group(1).strip()
        if not val:
            continue
        if col == "mileage_km":
            row[col] = C.parse_int(val)
        else:
            row[col] = val
    # Also pull "ราคาป้ายแดง" (MSRP) into prvprc if not already set
    if not row.get("prvprc"):
        m = re.search(r"ราคาป้ายแดง[^|<]*\|?\s*([\d,]+)", html)
        if m:
            row["prvprc"] = m.group(1)


# --- driver ----------------------------------------------------------------

UPDATE_SQL = """
UPDATE listings SET
    yr4 = COALESCE(?, yr4),
    amake = COALESCE(?, amake),
    amodel = COALESCE(?, amodel),
    atrim = COALESCE(?, atrim),
    abody = COALESCE(?, abody),
    prc = COALESCE(?, prc),
    prvprc = COALESCE(?, prvprc),
    mileage_km = COALESCE(?, mileage_km),
    color = COALESCE(?, color),
    transmission = COALESCE(?, transmission),
    fuel = COALESCE(?, fuel),
    body_type = COALESCE(?, body_type),
    seller_name = COALESCE(?, seller_name),
    seller_type = COALESCE(?, seller_type),
    condition = COALESCE(?, condition),
    location = COALESCE(?, location),
    ireg = COALESCE(?, ireg),
    detail_fetched_at = ?
WHERE cid = ? AND scraped_at = ?
"""


def _row_to_update(row, scraped_at):
    return (
        row.get("yr4"), row.get("amake"), row.get("amodel"), row.get("atrim"),
        row.get("abody"),
        row.get("prc"), row.get("prvprc"),
        row.get("mileage_km"), row.get("color"), row.get("transmission"),
        row.get("fuel"), row.get("body_type"),
        row.get("seller_name"), row.get("seller_type"),
        row.get("condition"), row.get("location"), row.get("ireg"),
        scraped_at,
        row["cid"], row["scraped_at_orig"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=sorted(SOURCES.keys()))
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of rows to enrich this run")
    ap.add_argument("--sleep", type=float, default=2.5,
                    help="seconds between requests")
    ap.add_argument("--order-by", default="cid",
                    choices=["cid", "views_desc", "year_desc", "price_desc"],
                    help="row priority order")
    ap.add_argument("--waf-cooldown", type=float, default=120,
                    help="seconds to sleep after a WAF challenge")
    ap.add_argument("--waf-giveup", type=int, default=20,
                    help="abort after this many consecutive WAF blocks")
    ap.add_argument("--reenrich", action="store_true",
                    help="enrich rows even if detail_fetched_at is set")
    ap.add_argument("--latest-only", action="store_true", default=True,
                    help="only enrich rows from each cid's latest scrape (default)")
    args = ap.parse_args()

    url_fn, enricher = SOURCES[args.source]
    init()
    conn = connect()
    # Auto-commit each UPDATE so we don't hold a long write lock when
    # another enricher process is running in parallel.
    conn.isolation_level = None
    conn.execute("PRAGMA wal_autocheckpoint=200")

    # Pick the latest snapshot per cid for this source. Skip rows that
    # already have a detail_fetched_at (unless --reenrich).
    where_unenriched = "" if args.reenrich else "AND l.detail_fetched_at IS NULL"
    order_clause = {
        "cid":         "l.cid",
        "views_desc":  "l.ipgvw DESC NULLS LAST, l.cid",
        "year_desc":   "l.yr4 DESC NULLS LAST, l.cid",
        "price_desc":  "l.prc DESC NULLS LAST, l.cid",
    }[args.order_by]
    sql = f"""
        WITH latest AS (
          SELECT cid, MAX(scraped_at) AS ts
          FROM listings WHERE source = ? GROUP BY cid
        )
        SELECT l.cid, l.scraped_at, l.url, l.yr4, l.amake, l.amodel,
               l.atrim, l.abody, l.prc, l.prvprc, l.ipgvw,
               l.mileage_km, l.color, l.transmission, l.fuel,
               l.body_type, l.seller_name, l.seller_type, l.condition,
               l.location, l.ireg
        FROM listings l
        JOIN latest lt ON lt.cid = l.cid AND lt.ts = l.scraped_at
        WHERE l.source = ? {where_unenriched}
        ORDER BY {order_clause}
    """
    if args.limit:
        sql += f" LIMIT {args.limit}"
    rows = conn.execute(sql, (args.source, args.source)).fetchall()
    print(f"[{args.source}] {len(rows)} rows to enrich "
          f"(transport={'curl-cffi' if C.USE_CFFI else 'urllib'})")

    now = _now()
    enriched = 0
    failed = 0
    consecutive_waf = 0
    for i, r in enumerate(rows, 1):
        row = dict(r)
        row["scraped_at_orig"] = row.pop("scraped_at")
        url = url_fn(row)
        if not url:
            continue
        try:
            html = C.http_get(url)
            consecutive_waf = 0
        except C.WAFBlocked:
            consecutive_waf += 1
            failed += 1
            cooldown = args.waf_cooldown * min(consecutive_waf, 4)
            print(f"  [{i}/{len(rows)}] {row['cid']} WAF #{consecutive_waf}; "
                  f"sleeping {cooldown:.0f}s", flush=True)
            if consecutive_waf >= args.waf_giveup:
                print(f"  giving up after {consecutive_waf} consecutive WAF "
                      f"challenges", flush=True)
                break
            time.sleep(cooldown)
            try:
                html = C.http_get(url)
                consecutive_waf = 0
            except Exception as e2:
                print(f"  [{i}/{len(rows)}] {row['cid']} retry FAILED: {e2}", flush=True)
                continue
        except Exception as e:
            failed += 1
            if failed <= 5 or failed % 25 == 0:
                print(f"  [{i}/{len(rows)}] {row['cid']} fetch FAILED: {e}", flush=True)
            time.sleep(args.sleep + random.uniform(0, args.sleep * 0.4))
            continue
        try:
            enricher(row, html)
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {row['cid']} enrich FAILED: {e}")
            continue
        conn.execute(UPDATE_SQL, _row_to_update(row, now))
        enriched += 1
        if enriched % 25 == 0:
            print(f"  {enriched}/{len(rows)} enriched (failed={failed})", flush=True)
        time.sleep(args.sleep + random.uniform(0, args.sleep * 0.3))
    conn.close()
    print(f"DONE — enriched {enriched}, failed {failed}, skipped {len(rows)-enriched-failed}")


if __name__ == "__main__":
    main()
