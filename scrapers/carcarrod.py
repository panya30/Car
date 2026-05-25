"""Scrape carcarrod.com (WordPress + Vehica plugin).

Carcarrod has only ~100 cars total. Their pagination URL parameter is a
no-op — every page renders the full list. So we hit ``/search/`` once,
parse all the cards, and (optionally) fetch each detail page for
mileage / colour / transmission.

List card structure (`vehica-car-card-v2`):
  * outer wrapper: ``<div data-id="69389" class="vehica-car-card ...">``
  * link:          ``<a class="vehica-car-card-link" href="/listing/{slug}/">``
  * title:         ``<a class="vehica-car-card__name" title="…">…</a>``
  * price:         ``<div class="vehica-car-card__price">฿1,079,000</div>``
  * info pills:    ``<div class="vehica-car-card__info__single">2025</div>``,
                   ``<div class="vehica-car-card__info__single">11,000 กิโลเมตร</div>``
  * image:         ``<img data-srcset="… 335w, … 670w, …" alt="…">``

Detail page (``/listing/{slug}/``) renders a ``vehica-grid`` block per
attribute: ``ปี``, ``สี``, ``เลขไมล์``, ``ระบบเกียร์``, ``ระบบเชื้อเพลิง``,
``ตัวถัง``, etc., each rendered as label-then-value within an outer grid.
"""
from __future__ import annotations

import json
import random
import re
import time

from . import _common as C

SOURCE = "carcarrod"
LIST_URL = "https://carcarrod.com/search/"

# Match each card from its data-id wrapper to the next data-id wrapper
# (or the end of the inventory section).
CARD_RE = re.compile(
    r'<div\s+id="vehica-car-(\d+)"\s+data-id="\d+"\s+class="vehica-car-card[^"]*"[^>]*>'
    r'(.*?)'
    r'(?=<div\s+id="vehica-car-\d+"\s+data-id|<div\s+class="vehica-pagination|</main)',
    re.S,
)
LINK_RE  = re.compile(r'<a\s+class="vehica-car-card-link"\s+href="([^"]+)"')
NAME_RE  = re.compile(
    r'<a[^>]*class="vehica-car-card__name"[^>]*title="([^"]*)"[^>]*>'
    r'\s*([^<]+?)\s*</a>',
    re.S,
)
PRICE_RE = re.compile(r'class="vehica-car-card__price"[^>]*>\s*฿?([\d,]+)\s*</')
INFO_RE  = re.compile(
    r'class="vehica-car-card__info__single"[^>]*>\s*([^<]+?)\s*</div>',
    re.S,
)
IMG_SRCSET_RE = re.compile(r'data-srcset="([^"]+)"')
IMG_ALT_RE = re.compile(r'<img[^>]+alt="([^"]+)"')
KM_RE = re.compile(r"([\d,]+)\s*(?:กิโลเมตร|km)", re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Detail-page fields. Each row is a `vehica-grid` row with label text
# preceding the value text in the same flow. We use a label-anchored
# look-around regex.
DETAIL_FIELD_RES: dict[str, re.Pattern[str]] = {
    "year":         re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*ปี\s*:?\s*(?:<[^>]+>\s*)*([\d]{4})', re.S),
    "color":        re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*สี\s*:?\s*(?:<[^>]+>\s*)*([^<]{1,40}?)\s*<', re.S),
    "mileage_km":   re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*เลขไมล์\s*:?\s*(?:<[^>]+>\s*)*([\d,]+)\s*(?:กิโลเมตร|km)', re.S | re.I),
    "transmission": re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*ระบบเกียร์\s*:?\s*(?:<[^>]+>\s*)*([^<]{1,40}?)\s*<', re.S),
    "fuel":         re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*(?:ระบบเชื้อเพลิง|เชื้อเพลิง|พลังงาน)\s*:?\s*(?:<[^>]+>\s*)*([^<]{1,40}?)\s*<', re.S),
    "body_type":    re.compile(r'class="vehica-grid"[^>]*>\s*(?:<[^>]+>\s*)*(?:ตัวถัง|ประเภทรถ)\s*:?\s*(?:<[^>]+>\s*)*([^<]{1,40}?)\s*<', re.S),
}

HARD_CARD_CAP = 500


def _largest_image(srcset: str) -> str | None:
    """Pick the largest URL from a srcset string."""
    candidates = []
    for piece in srcset.split(","):
        piece = piece.strip()
        m = re.match(r"(\S+)\s+(\d+)w", piece)
        if m:
            candidates.append((int(m.group(2)), m.group(1)))
    return max(candidates)[1] if candidates else None


def _parse_card(cid: str, body: str) -> dict | None:
    link = LINK_RE.search(body)
    name = NAME_RE.search(body)
    price = PRICE_RE.search(body)
    infos = [m.strip() for m in INFO_RE.findall(body)]
    img_src = None
    srcset = IMG_SRCSET_RE.search(body)
    if srcset:
        img_src = _largest_image(srcset.group(1).replace("&amp;", "&"))
    if not img_src:
        # fall back to alt-only image on lazy-load placeholder
        img_alt = IMG_ALT_RE.search(body)
        if img_alt:
            pass  # alt available but no usable URL

    title = (name.group(1) if name else (name.group(2) if name else None)) or None
    if name:
        title = name.group(1) or name.group(2)
    year = None
    mileage_km = None
    for s in infos:
        if not year:
            ym = YEAR_RE.search(s)
            if ym:
                year = int(ym.group(0))
                continue
        if not mileage_km:
            km = KM_RE.search(s)
            if km:
                mileage_km = C.parse_int(km.group(1))
    if year is None and title:
        ym = YEAR_RE.search(title)
        if ym:
            year = int(ym.group(0))

    # Make/model: title looks like "2021 BMW 320d M-SPORT" or "TANK 300 ตัว Top4x4".
    parts = (title or "").split()
    make = None
    model = None
    if year and parts and parts[0].isdigit() and len(parts) > 1:
        make = parts[1].upper()
        if len(parts) > 2:
            model = parts[2].upper()
    elif parts:
        make = parts[0].upper()
        if len(parts) > 1:
            model = parts[1].upper()

    return {
        "cid": f"{SOURCE}:{cid}",
        "title": title,
        "namemmt": title,
        "prc": C.parse_int(price.group(1)) if price else None,
        "yr4": year,
        "amake": make,
        "amodel": model,
        "mileage_km": mileage_km,
        "img": img_src,
        "url": link.group(1) if link else None,
        "raw_json": json.dumps(
            {"id": cid, "title": title,
             "price": price.group(1) if price else None,
             "infos": infos,
             "url": link.group(1) if link else None,
             "img": img_src},
            ensure_ascii=False, separators=(",", ":"),
        ),
    }


def _enrich_detail(row: dict, html: str) -> None:
    """Pull mileage / color / transmission / fuel / body_type from the
    detail page. Idempotent — only fills fields that aren't already set.
    """
    for key, pat in DETAIL_FIELD_RES.items():
        if row.get(key):
            continue
        m = pat.search(html)
        if not m:
            continue
        val = m.group(1).strip()
        if not val:
            continue
        if key == "mileage_km":
            row[key] = C.parse_int(val)
        elif key == "year":
            row["yr4"] = row.get("yr4") or C.parse_int(val)
        else:
            row[key] = val


def run(conn, *, sleep_s: float = 1.5, note: str | None = None,
        max_pages: int | None = None, fetch_details: bool = True) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    C.log(SOURCE, f"run #{run_id} starting "
                  f"(transport={'curl-cffi' if C.USE_CFFI else 'urllib'}, "
                  f"details={fetch_details})")
    queries = 0
    seen: set[str] = set()
    rows_buffer: list[dict] = []

    try:
        html = C.http_get(LIST_URL)
        queries += 1

        for cid, body in CARD_RE.findall(html)[:HARD_CARD_CAP]:
            full_cid = f"{SOURCE}:{cid}"
            if full_cid in seen:
                continue
            row = _parse_card(cid, body)
            if not row:
                continue
            seen.add(full_cid)
            rows_buffer.append(row)
        C.log(SOURCE, f"list page: {len(rows_buffer)} cards parsed")

        if fetch_details and rows_buffer:
            C.log(SOURCE, f"fetching {len(rows_buffer)} detail pages…")
            for i, row in enumerate(rows_buffer, 1):
                if not row.get("url"):
                    continue
                time.sleep(sleep_s + random.uniform(0, sleep_s * 0.4))
                try:
                    detail = C.http_get(row["url"])
                    queries += 1
                    _enrich_detail(row, detail)
                    row["detail_fetched_at"] = scraped_at
                except Exception as e:
                    C.log(SOURCE, f"  detail {i}/{len(rows_buffer)} FAILED: {e}")
                    continue
                if i % 10 == 0:
                    C.log(SOURCE, f"  detail {i}/{len(rows_buffer)}")
                    # flush partial progress so a later crash doesn't lose work
                    C.insert_rows(conn, rows_buffer[:i], scraped_at, SOURCE, run_id)

        inserted = C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
        C.close_run(conn, run_id, queries=queries, cars_seen=inserted,
                    cars_unique=inserted)
        C.log(SOURCE, f"run #{run_id} OK — {inserted} unique, {queries} queries")
    except Exception as e:
        if rows_buffer:
            C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
        C.close_run(conn, run_id, queries=queries, cars_seen=len(seen),
                    cars_unique=len(seen), status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
