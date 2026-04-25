"""Scrape rod.kaidee.com (~10,916 listings).

Strategy: GET ``/c11-auto-car?p=N`` and pull listings out of the page's
``__NEXT_DATA__`` blob. Each page returns up to ~27 ads plus a totalCount.
We page until we've covered the reported total (or hit a hard ceiling).
"""
from __future__ import annotations

import json
import random
import re
import time

from . import _common as C

SOURCE = "kaidee"
LIST_URL = "https://rod.kaidee.com/c11-auto-car"
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>'
)
PER_PAGE = 27  # observed; kaidee's server-side count
HARD_PAGE_CAP = 600  # safety net so a runaway never goes infinite


def _fetch_page(p: int) -> dict:
    url = LIST_URL if p == 1 else f"{LIST_URL}?page={p}"
    html = C.http_get(url, headers={"Referer": LIST_URL})
    m = NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError(f"__NEXT_DATA__ missing on page {p}")
    return json.loads(m.group(1))


def _normalise(ad: dict) -> dict:
    """Map a kaidee ad object onto the shared `listings` schema."""
    attrs = {a.get("key") or a.get("name"): a.get("value")
             for a in (ad.get("attributes") or [])}
    year = C.parse_int(attrs.get("year") or attrs.get("Year"))
    make = attrs.get("brand") or attrs.get("Brand") or attrs.get("make")
    model = attrs.get("model") or attrs.get("Model")
    body = attrs.get("car_type") or attrs.get("body_type")
    images = ad.get("image") or {}
    if isinstance(images, dict):
        img = images.get("default") or images.get("url")
    else:
        img = images
    tracking = ad.get("tracking") or {}
    detail_id = (ad.get("id") or ad.get("legacyId") or tracking.get("id")
                 or tracking.get("ad_id"))
    if not detail_id:
        return {}
    location = ad.get("location") or ""
    if isinstance(location, dict):
        location = location.get("name") or location.get("province") or ""
    return {
        "cid": f"{SOURCE}:{detail_id}",
        "yr4": year,
        "amake": (make or "").upper() or None,
        "amodel": (model or "").upper() or None,
        "abody": body,
        "title": ad.get("title"),
        "namemmt": ad.get("title"),
        "prc": C.parse_int(ad.get("price")),
        "img": img,
        "url": f"https://rod.kaidee.com/product/{detail_id}",
        "location": location or None,
        "raw_json": json.dumps(ad, ensure_ascii=False, separators=(",", ":")),
    }


def run(conn, *, sleep_s: float = 2.0, note: str | None = None,
        max_pages: int | None = None) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    C.log(SOURCE, f"run #{run_id} starting "
                  f"(transport={'curl-cffi' if C.USE_CFFI else 'urllib'})")
    queries = 0
    seen_total = 0
    seen_unique: set[str] = set()
    try:
        first = _fetch_page(1)
        queries += 1
        page_props = first.get("props", {}).get("pageProps", {}) or {}
        total = (page_props.get("totalAds")
                 or page_props.get("adsCount")
                 or page_props.get("totalCount")
                 or page_props.get("count"))
        if not total:
            # Fall back to scanning the JSON for a plausible total.
            flat = json.dumps(page_props)
            m = re.search(r'"totalAds"\s*:\s*(\d+)', flat) \
                or re.search(r'"total"\s*:\s*(\d+)', flat)
            total = int(m.group(1)) if m else None
        target_pages = (
            min(max_pages, HARD_PAGE_CAP) if max_pages
            else min((total // PER_PAGE) + 2 if total else HARD_PAGE_CAP,
                     HARD_PAGE_CAP)
        )
        C.log(SOURCE, f"total~{total}, will fetch up to {target_pages} pages")

        def absorb(page_data: dict, page_num: int) -> int:
            ads = (page_data.get("props", {}).get("pageProps", {}).get("ads")
                   or [])
            rows = []
            for ad in ads:
                norm = _normalise(ad)
                if not norm.get("cid") or norm["cid"] in seen_unique:
                    continue
                seen_unique.add(norm["cid"])
                rows.append(norm)
            inserted = C.insert_rows(conn, rows, scraped_at, SOURCE, run_id)
            C.log(SOURCE, f"page {page_num}: {len(ads)} ads, "
                          f"{inserted} new (total unique={len(seen_unique)})")
            return len(ads)

        absorb(first, 1)
        for p in range(2, target_pages + 1):
            time.sleep(sleep_s + random.uniform(0, sleep_s * 0.4))
            try:
                data = _fetch_page(p)
                queries += 1
            except C.WAFBlocked:
                C.log(SOURCE, f"page {p} WAF block — sleeping 60s")
                time.sleep(60)
                try:
                    data = _fetch_page(p)
                    queries += 1
                except Exception as e:
                    C.log(SOURCE, f"page {p} retry FAILED: {e}")
                    continue
            except Exception as e:
                C.log(SOURCE, f"page {p} FAILED: {e}")
                continue
            n = absorb(data, p)
            if n == 0:
                C.log(SOURCE, f"page {p} empty, stopping")
                break
        seen_total = len(seen_unique)
        C.close_run(conn, run_id, queries=queries, cars_seen=seen_total,
                    cars_unique=seen_total)
        C.log(SOURCE, f"run #{run_id} OK — {seen_total} unique, {queries} queries")
    except Exception as e:
        C.close_run(conn, run_id, queries=queries, cars_seen=seen_total,
                    cars_unique=seen_total, status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
