"""Re-extract deep fields from existing kaidee rows' raw_json.

Kaidee's list-page payload already carries autoInfo (mileage, fuel,
transmission, carType, dealership, submodel, color hint in imageAlt) — we
just weren't pulling it. Run this once after upgrading scrapers/kaidee.py
to backfill historical rows without re-fetching anything.
"""
from __future__ import annotations

import json

from db import connect
from scrapers.kaidee import _normalise


def main():
    conn = connect()
    rows = conn.execute(
        """SELECT cid, scraped_at, raw_json
           FROM listings
           WHERE source = 'kaidee' AND raw_json IS NOT NULL"""
    ).fetchall()
    print(f"to-reparse: {len(rows)}")

    updated = 0
    for r in rows:
        try:
            ad = json.loads(r["raw_json"])
        except Exception:
            continue
        norm = _normalise(ad)
        if not norm:
            continue
        conn.execute(
            """UPDATE listings SET
                 yr4 = COALESCE(?, yr4),
                 amake = COALESCE(?, amake),
                 amodel = COALESCE(?, amodel),
                 abody = COALESCE(?, abody),
                 atrim = COALESCE(?, atrim),
                 mileage_km = COALESCE(?, mileage_km),
                 color = COALESCE(?, color),
                 transmission = COALESCE(?, transmission),
                 fuel = COALESCE(?, fuel),
                 body_type = COALESCE(?, body_type),
                 seller_name = COALESCE(?, seller_name),
                 seller_type = COALESCE(?, seller_type),
                 condition = COALESCE(?, condition),
                 location = COALESCE(?, location),
                 url = COALESCE(?, url)
               WHERE cid = ? AND scraped_at = ?""",
            (
                norm.get("yr4"), norm.get("amake"), norm.get("amodel"),
                norm.get("abody"), norm.get("atrim"),
                norm.get("mileage_km"), norm.get("color"),
                norm.get("transmission"), norm.get("fuel"),
                norm.get("body_type"),
                norm.get("seller_name"), norm.get("seller_type"),
                norm.get("condition"), norm.get("location"),
                norm.get("url"),
                r["cid"], r["scraped_at"],
            ),
        )
        updated += 1
        if updated % 1000 == 0:
            conn.commit()
            print(f"  {updated} rows reparsed…")
    conn.commit()
    print(f"OK — reparsed {updated} rows")


if __name__ == "__main__":
    main()
