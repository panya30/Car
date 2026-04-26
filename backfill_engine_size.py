"""Extract engine displacement (liters) from every listing's title.

Thai used-car titles almost always include engine size in the form
"1.5", "2.0", "2.4", "(1.8)" — that one number is the strongest signal
for which trim a listing belongs to. We use it as the 4th component of
the cohort key so e.g. a Ford Ranger XL 2.2 doesn't get compared
against a Ranger Wildtrak 3.0.

Run::

    python backfill_engine_size.py            # update all listings
    python backfill_engine_size.py --refresh  # also overwrite already-set rows
"""
from __future__ import annotations

import argparse
import re
from db import connect, init


# Match a 0.0-6.9 decimal as a standalone token. Rejects year ranges
# ("ปี16-24", "20-26"), 4-digit years ("2024"), and lookups like "B2012".
ENGINE_RE = re.compile(r"(?<!\d)([0-6]\.\d)(?!\d)")
PLAUSIBLE_MIN = 0.6
PLAUSIBLE_MAX = 6.0


def extract_engine_size(*candidates: str | None) -> float | None:
    """Return the first plausible engine displacement found in any of the
    provided title-like fields, or None if none qualifies."""
    for text in candidates:
        if not text:
            continue
        for m in ENGINE_RE.finditer(text):
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if PLAUSIBLE_MIN <= v <= PLAUSIBLE_MAX:
                return v
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-extract even where engine_size is already set")
    args = ap.parse_args()
    init()
    conn = connect()
    where = "" if args.refresh else "WHERE engine_size IS NULL"
    rows = conn.execute(
        f"""SELECT cid, scraped_at, namemmt, title, atrim
            FROM listings {where}"""
    ).fetchall()
    print(f"to-process: {len(rows)}")

    n_set = 0
    for r in rows:
        size = extract_engine_size(r["namemmt"], r["title"], r["atrim"])
        if size is None:
            continue
        conn.execute(
            "UPDATE listings SET engine_size = ? WHERE cid = ? AND scraped_at = ?",
            (size, r["cid"], r["scraped_at"]),
        )
        n_set += 1
        if n_set % 5000 == 0:
            conn.commit()
            print(f"  {n_set}/{len(rows)} updated…")
    conn.commit()
    print(f"OK — set engine_size on {n_set:,} rows")


if __name__ == "__main__":
    main()
