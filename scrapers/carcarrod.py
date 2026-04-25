"""Scrape carcarrod.com (WordPress + Vehica plugin).

Strategy: pages live at ``/search/page/N/``. Each page renders a list of
``vehica-car-card`` blocks containing:
  * ``:car-id="69389"`` — the WP post ID we use as ``cid``
  * ``href="/listing/{slug}/"`` — detail URL
  * a ``vehica-car-card__price`` span — price in baht
  * a ``vehica-car-card__title`` h3 — title
  * Vehica fields rendered as inline spans (year, mileage, fuel, …).

We extract from the rendered HTML; no headless browser needed.
"""
from __future__ import annotations

import json
import random
import re
import time

from . import _common as C

SOURCE = "carcarrod"
LIST_URL = "https://carcarrod.com/search/"
PAGE_URL = "https://carcarrod.com/search/page/{p}/"

CAR_BLOCK_RE = re.compile(
    r'<div class="vehica-car-card[^"]*"[^>]*>(.*?)(?=<div class="vehica-car-card[^"]*"|<div class="vehica-pagination|</main>)',
    re.S,
)
CAR_ID_RE = re.compile(r':car-id="(\d+)"')
LINK_RE = re.compile(r'href="(https?://carcarrod\.com/listing/[^"]+)"')
TITLE_RE = re.compile(
    r'<h\d[^>]*class="[^"]*vehica-car-card__title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
    re.I,
)
PRICE_RE = re.compile(
    r'class="[^"]*vehica-car-card__price[^"]*"[^>]*>(.*?)</', re.S,
)
PRICE_NUM_RE = re.compile(r"([\d,]+)")
IMG_RE = re.compile(r'<img[^>]+(?:src|data-src|data-lazy-src)="([^"]+)"')
ATTR_RE = re.compile(
    r'<span[^>]*class="[^"]*vehica-car-card__attribute__name[^"]*"[^>]*>'
    r'\s*([^<]+?)\s*</span>\s*<span[^>]*class="[^"]*vehica-car-card__attribute__value[^"]*"[^>]*>'
    r'\s*([^<]+?)\s*</span>',
    re.S,
)
PAGE_COUNT_RE = re.compile(
    r'class="page-numbers"[^>]*>\s*(\d+)\s*</a>'
)
TOTAL_RE = re.compile(r'(\d{1,3}(?:,\d{3})+|\d{3,})\s*(?:results|matches|รายการ|listings)', re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
HARD_PAGE_CAP = 500


def _fetch_page(p: int) -> str:
    url = LIST_URL if p == 1 else PAGE_URL.format(p=p)
    return C.http_get(url, headers={"Referer": LIST_URL})


def _normalise(block: str) -> dict | None:
    cid_m = CAR_ID_RE.search(block)
    if not cid_m:
        return None
    cid = cid_m.group(1)
    link = (LINK_RE.search(block) or [None, None])[1] or None
    title = (TITLE_RE.search(block) or [None, None])[1] or None
    price = None
    pm = PRICE_RE.search(block)
    if pm:
        nm = PRICE_NUM_RE.search(pm.group(1))
        if nm:
            price = C.parse_int(nm.group(1))
    img = (IMG_RE.search(block) or [None, None])[1] or None
    attrs = {k.strip(): v.strip() for k, v in ATTR_RE.findall(block)}
    year = None
    for k, v in attrs.items():
        if k in ("Year", "ปี", "ปีรถ"):
            year = C.parse_int(v)
            break
    if year is None and title:
        ym = YEAR_RE.search(title)
        if ym:
            year = int(ym.group(0))
    make = attrs.get("Make") or attrs.get("ยี่ห้อ")
    model = attrs.get("Model") or attrs.get("รุ่น")
    return {
        "cid": f"{SOURCE}:{cid}",
        "title": title,
        "namemmt": title,
        "prc": price,
        "yr4": year,
        "amake": (make or "").upper() or None,
        "amodel": (model or "").upper() or None,
        "img": img,
        "url": link,
        "raw_json": json.dumps(
            {"id": cid, "title": title, "price": price, "year": year,
             "url": link, "img": img, "attrs": attrs},
            ensure_ascii=False, separators=(",", ":"),
        ),
    }


def _max_page(html: str) -> int:
    pages = [int(x) for x in PAGE_COUNT_RE.findall(html)]
    return max(pages) if pages else 1


def run(conn, *, sleep_s: float = 2.0, note: str | None = None,
        max_pages: int | None = None) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    C.log(SOURCE, f"run #{run_id} starting "
                  f"(transport={'curl-cffi' if C.USE_CFFI else 'urllib'})")
    queries = 0
    seen: set[str] = set()
    try:
        first = _fetch_page(1)
        queries += 1
        last_page = _max_page(first)
        target = min(max_pages or last_page, HARD_PAGE_CAP)
        C.log(SOURCE, f"detected last_page={last_page}, will fetch {target}")

        def absorb(html: str, page_num: int) -> int:
            blocks = CAR_BLOCK_RE.findall(html)
            rows = []
            for blk in blocks:
                row = _normalise(blk)
                if not row or row["cid"] in seen:
                    continue
                seen.add(row["cid"])
                rows.append(row)
            inserted = C.insert_rows(conn, rows, scraped_at, SOURCE, run_id)
            C.log(SOURCE, f"page {page_num}: {len(blocks)} blocks, "
                          f"{inserted} new (total={len(seen)})")
            return len(blocks)

        absorb(first, 1)
        for p in range(2, target + 1):
            time.sleep(sleep_s + random.uniform(0, sleep_s * 0.4))
            try:
                html = _fetch_page(p)
                queries += 1
            except C.WAFBlocked:
                C.log(SOURCE, f"page {p} WAF, sleeping 60s")
                time.sleep(60)
                try:
                    html = _fetch_page(p)
                    queries += 1
                except Exception as e:
                    C.log(SOURCE, f"page {p} retry FAILED: {e}")
                    continue
            except Exception as e:
                C.log(SOURCE, f"page {p} FAILED: {e}")
                continue
            if absorb(html, p) == 0:
                C.log(SOURCE, f"page {p} empty; stopping")
                break

        C.close_run(conn, run_id, queries=queries, cars_seen=len(seen),
                    cars_unique=len(seen))
        C.log(SOURCE, f"run #{run_id} OK — {len(seen)} unique, {queries} queries")
    except Exception as e:
        C.close_run(conn, run_id, queries=queries, cars_seen=len(seen),
                    cars_unique=len(seen), status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
