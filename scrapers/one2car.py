"""Scrape one2car.com.

one2car sits behind Cloudflare's "managed challenge" — plain HTTP returns 403
with ``cf-mitigated: challenge`` no matter the User-Agent or TLS fingerprint.
The challenge is a JavaScript puzzle, so we need a real browser.

This module supports two transports:

  * ``transport="playwright"`` — uses Playwright + chromium (heaviest, most
    reliable). Install with::

        pip install --user --break-system-packages playwright
        python -m playwright install chromium

  * ``transport="cookie"`` — fastest path: you visit one2car.com once in a
    real browser, copy the ``cf_clearance`` cookie value, and pass it via
    the ``CF_CLEARANCE`` env var. The cookie typically lasts 30 min – 2 h.

Without either, the run records ``status='blocked'`` and exits gracefully.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

from . import _common as C

SOURCE = "one2car"
LIST_URL = "https://www.one2car.com/cars-for-sale"
HARD_PAGE_CAP = 1000


def _normalise(card: dict) -> dict:
    sid = card.get("id") or card.get("listing_id") or card.get("uid")
    return {
        "cid": f"{SOURCE}:{sid}",
        "title": card.get("title") or card.get("name"),
        "namemmt": card.get("title") or card.get("name"),
        "prc": C.parse_int(card.get("price")),
        "yr4": C.parse_int(card.get("year") or card.get("model_year")),
        "amake": (card.get("brand") or card.get("make") or "").upper() or None,
        "amodel": (card.get("model") or "").upper() or None,
        "url": card.get("url") or card.get("link"),
        "img": card.get("image") or card.get("primary_image"),
        "location": card.get("location") or card.get("city"),
        "raw_json": json.dumps(card, ensure_ascii=False, separators=(",", ":")),
    }


def _try_playwright(conn, run_id, scraped_at, sleep_s: float, max_pages: int):
    """Drive a real Chromium via Playwright."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return None  # not installed

    queries = 0
    seen: set[str] = set()
    rows_buffer: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/132.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
            extra_http_headers={"Accept-Language": "th,en;q=0.8"},
        )
        page = ctx.new_page()

        # Visit homepage first to clear CF challenge once, then list.
        page.goto("https://www.one2car.com/", timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=30_000)

        for p in range(1, max_pages + 1):
            url = LIST_URL if p == 1 else f"{LIST_URL}/page/{p}"
            try:
                page.goto(url, timeout=60_000)
                page.wait_for_load_state("networkidle", timeout=30_000)
                queries += 1
            except Exception as e:
                C.log(SOURCE, f"page {p} navigation FAILED: {e}")
                break

            # Two strategies: read __NEXT_DATA__ then fall back to data-test-id cards.
            next_data = page.eval_on_selector(
                "script#__NEXT_DATA__", "el => el.textContent",
            ) if page.locator("script#__NEXT_DATA__").count() else None
            cards: list[dict] = []
            if next_data:
                try:
                    data = json.loads(next_data)
                    flat = json.dumps(data)
                    # heuristic: any list containing dicts with both 'id' and 'price'.
                    def _walk(o):
                        if isinstance(o, dict):
                            for v in o.values():
                                yield from _walk(v)
                        elif isinstance(o, list):
                            if o and isinstance(o[0], dict) and "price" in o[0] and "id" in o[0]:
                                yield o
                            for v in o:
                                yield from _walk(v)
                    for lst in _walk(data):
                        for c in lst:
                            cards.append(c)
                        break
                except Exception as e:
                    C.log(SOURCE, f"page {p} __NEXT_DATA__ parse FAILED: {e}")

            new_this_page = 0
            for c in cards:
                row = _normalise(c)
                if not row.get("cid") or row["cid"] in seen:
                    continue
                seen.add(row["cid"])
                rows_buffer.append(row)
                new_this_page += 1
            C.log(SOURCE, f"page {p}: {len(cards)} cards, {new_this_page} new")
            if new_this_page == 0:
                break
            time.sleep(sleep_s + random.uniform(0, sleep_s * 0.4))

        browser.close()

    inserted = C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
    return queries, inserted


def _try_cookie(conn, run_id, scraped_at, sleep_s, max_pages):
    """Use a manually-supplied cf_clearance cookie via curl-cffi."""
    cf = os.environ.get("CF_CLEARANCE")
    if not cf:
        return None
    if not C.USE_CFFI:
        C.log(SOURCE, "CF_CLEARANCE set but curl-cffi unavailable; skipping")
        return None

    from curl_cffi import requests as r  # type: ignore
    s = r.Session()
    s.cookies.set("cf_clearance", cf, domain=".one2car.com")
    queries = 0
    seen: set[str] = set()
    rows_buffer: list[dict] = []

    for p in range(1, max_pages + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}/page/{p}"
        try:
            resp = s.get(
                url, impersonate="chrome131",
                headers=C.DEFAULT_HEADERS, timeout=30,
            )
            queries += 1
            if (resp.headers.get("cf-mitigated") or "").lower() == "challenge":
                C.log(SOURCE, f"page {p}: CF still challenging — cookie expired?")
                break
            html = resp.text
        except Exception as e:
            C.log(SOURCE, f"page {p} FAILED: {e}")
            break

        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html,
        )
        if not m:
            C.log(SOURCE, f"page {p}: no __NEXT_DATA__")
            break
        try:
            data = json.loads(m.group(1))
        except Exception as e:
            C.log(SOURCE, f"page {p} JSON err: {e}")
            break
        cards: list[dict] = []
        flat = json.dumps(data)
        # crude card detection — same heuristic as the playwright path.
        def _walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from _walk(v)
            elif isinstance(o, list):
                if o and isinstance(o[0], dict) and "price" in o[0] and "id" in o[0]:
                    yield o
                for v in o:
                    yield from _walk(v)
        for lst in _walk(data):
            for c in lst:
                cards.append(c)
            break
        new_this_page = 0
        for c in cards:
            row = _normalise(c)
            if not row.get("cid") or row["cid"] in seen:
                continue
            seen.add(row["cid"])
            rows_buffer.append(row)
            new_this_page += 1
        C.log(SOURCE, f"page {p}: {len(cards)} cards, {new_this_page} new")
        if new_this_page == 0:
            break
        time.sleep(sleep_s + random.uniform(0, sleep_s * 0.4))

    inserted = C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
    return queries, inserted


def run(conn, *, sleep_s: float = 2.0, note: str | None = None,
        max_pages: int | None = None) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    target = min(max_pages or HARD_PAGE_CAP, HARD_PAGE_CAP)
    C.log(SOURCE, f"run #{run_id} starting (target {target} pages)")

    try:
        result = _try_cookie(conn, run_id, scraped_at, sleep_s, target)
        if result is None:
            result = _try_playwright(conn, run_id, scraped_at, sleep_s, target)

        if result is None:
            C.log(SOURCE, "blocked: install Playwright or set CF_CLEARANCE "
                          "(see scrapers/one2car.py docstring).")
            C.close_run(conn, run_id, queries=0, cars_seen=0, cars_unique=0,
                        status="blocked",
                        error="Cloudflare challenge; need playwright or "
                              "CF_CLEARANCE cookie")
            return

        queries, inserted = result
        C.close_run(conn, run_id, queries=queries, cars_seen=inserted,
                    cars_unique=inserted)
        C.log(SOURCE, f"run #{run_id} OK — {inserted} unique, {queries} queries")
    except Exception as e:
        C.close_run(conn, run_id, queries=0, cars_seen=0, cars_unique=0,
                    status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
