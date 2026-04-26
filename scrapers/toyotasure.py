"""Scrape toyotasure.com — Toyota's Thai certified-pre-owned listings.

Strategy: every list page embeds a JSON-LD ItemList with up to ~30 entries
per page. The detail URL contains the source id (``...-{id}``). For now we
only ingest the list view — title, URL, position. Detail pages have richer
data (year/price/colour) but require N extra requests; add a follow-up pass
later if needed.
"""
from __future__ import annotations

import json
import random
import re
import time

from . import _common as C

SOURCE = "toyotasure"
LIST_URL = "https://www.toyotasure.com/home/used-car"
LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>([^<]+)</script>',
    re.S,
)
DETAIL_ID_RE = re.compile(r"/home/product/[^/]+-(\d+)$")
PRICE_RE = re.compile(r'(?:฿|baht|บาท)\s*([\d,]+)|"price"\s*:\s*"?(\d+)"?', re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
HARD_PAGE_CAP = 200


def _fetch_page(p: int) -> str:
    url = LIST_URL if p == 1 else f"{LIST_URL}?page={p}"
    return C.http_get(url, headers={"Referer": LIST_URL})


def _list_items(html: str) -> list[dict]:
    for snippet in LD_RE.findall(html):
        try:
            obj = json.loads(snippet)
        except Exception:
            continue
        if obj.get("@type") == "ItemList":
            return obj.get("itemListElement") or []
    return []


def _normalise(item: dict) -> dict | None:
    url = item.get("url") or ""
    m = DETAIL_ID_RE.search(url)
    if not m:
        return None
    sid = m.group(1)
    name = item.get("name") or ""
    year_match = YEAR_RE.search(name)
    return {
        "cid": f"{SOURCE}:{sid}",
        "title": name,
        "namemmt": name,
        "yr4": int(year_match.group(0)) if year_match else None,
        "amake": "TOYOTA",
        "url": url,
        "raw_json": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
    }


# Toyota Sure detail pages are React Server Components — the data lands
# inside ``self.__next_f.push([1, "..."])`` chunks. We concatenate every
# chunk and pull values by JSON-key.
RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')

DETAIL_KEYS = {
    "yr4":          ("Year",),
    "amake":        ("Brand",),
    "amodel":       ("Model",),
    "atrim":        ("Grade", "Variant"),
    "color":        ("Color",),
    "transmission": ("Transmission", "Gear"),
    "fuel":         ("Fuel",),
    "body_type":    ("CarType", "BodyType"),
    "mileage_km":   ("Mileage",),
    "condition":    ("FloodingCondition",),
    "seller_name":  ("DealerDisplayName", "BranchDisplayName"),
    "location":     ("Province",),
}
PRICE_KEYS = ("ResellingPrice", "PromotionPrice", "ResellingPriceWithVAT", "CashPrice")


def _decode_rsc_blob(html: str) -> str:
    parts = RSC_CHUNK_RE.findall(html)
    return "".join(
        s.replace('\\n', '\n').replace('\\"', '"')
         .replace('\\u003c', '<').replace('\\u003e', '>')
        for s in parts
    )


def _extract_key(blob: str, *keys: str) -> str | None:
    for k in keys:
        m = re.search(rf'"{k}"\s*:\s*"([^"]+)"', blob)
        if m:
            return m.group(1).strip()
        m = re.search(rf'"{k}"\s*:\s*(\d+(?:\.\d+)?)', blob)
        if m:
            return m.group(1)
    return None


def _enrich_detail(row: dict, html: str) -> None:
    """Pull every detail field we can from a Toyota Sure detail page."""
    blob = _decode_rsc_blob(html)
    for col, keys in DETAIL_KEYS.items():
        if row.get(col):
            continue
        val = _extract_key(blob, *keys)
        if not val:
            continue
        if col in ("yr4", "mileage_km"):
            row[col] = C.parse_int(val)
        elif col == "amake" or col == "amodel":
            row[col] = val.upper()
        else:
            row[col] = val
    if not row.get("prc"):
        for k in PRICE_KEYS:
            v = _extract_key(blob, k)
            if v:
                row["prc"] = C.parse_int(v)
                break


def run(conn, *, sleep_s: float = 1.5, note: str | None = None,
        max_pages: int | None = None, fetch_details: bool = True) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    C.log(SOURCE, f"run #{run_id} starting "
                  f"(transport={'curl-cffi' if C.USE_CFFI else 'urllib'})")
    queries = 0
    seen: set[str] = set()
    rows_buffer: list[dict] = []
    target = max_pages or HARD_PAGE_CAP
    try:
        for p in range(1, target + 1):
            try:
                html = _fetch_page(p)
                queries += 1
            except C.WAFBlocked:
                C.log(SOURCE, f"page {p} CF challenge, sleeping 60s")
                time.sleep(60)
                try:
                    html = _fetch_page(p)
                    queries += 1
                except Exception as e:
                    C.log(SOURCE, f"page {p} retry FAILED: {e}")
                    break
            except Exception as e:
                C.log(SOURCE, f"page {p} FAILED: {e}")
                break

            items = _list_items(html)
            if not items:
                C.log(SOURCE, f"page {p}: no items, stopping")
                break
            new_this_page = 0
            for item in items:
                row = _normalise(item)
                if not row or row["cid"] in seen:
                    continue
                seen.add(row["cid"])
                rows_buffer.append(row)
                new_this_page += 1
            C.log(SOURCE, f"page {p}: {len(items)} listed, "
                          f"{new_this_page} new (total={len(seen)})")
            if new_this_page == 0:
                break
            time.sleep(sleep_s + random.uniform(0, sleep_s * 0.3))

        # Optional detail enrichment for price/year accuracy.
        if fetch_details and rows_buffer:
            C.log(SOURCE, f"enriching {len(rows_buffer)} detail pages…")
            for i, row in enumerate(rows_buffer, 1):
                if i % 25 == 0:
                    C.log(SOURCE, f"  detail {i}/{len(rows_buffer)}")
                try:
                    detail_html = C.http_get(row["url"], headers={"Referer": LIST_URL})
                    queries += 1
                    _enrich_detail(row, detail_html)
                except C.WAFBlocked:
                    C.log(SOURCE, f"  detail {i} CF challenge, sleeping 60s")
                    time.sleep(60)
                except Exception as e:
                    C.log(SOURCE, f"  detail {i} FAILED: {e}")
                time.sleep(sleep_s + random.uniform(0, sleep_s * 0.3))

        inserted = C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
        C.close_run(conn, run_id, queries=queries, cars_seen=inserted,
                    cars_unique=inserted)
        C.log(SOURCE, f"run #{run_id} OK — {inserted} unique, {queries} queries")
    except Exception as e:
        C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
        C.close_run(conn, run_id, queries=queries, cars_seen=len(seen),
                    cars_unique=len(seen), status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
