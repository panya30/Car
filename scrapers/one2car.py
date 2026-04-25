"""Scrape one2car.com via Playwright + stealth.

one2car sits behind Cloudflare's "managed challenge". Empirically:

  * The homepage and a handful of bare URLs (e.g. ``/cars-for-sale`` and
    ``/รถ-สำหรับ-ขาย/body-{Sedan|SUV|...}?page_size=12&page_number=1``)
    pass the challenge automatically once a fingerprint cookie is seeded
    by visiting the homepage first.
  * Every URL that carries ``page_number=2..N`` triggers a fresh CF
    challenge that headless Chromium cannot solve without user interaction
    (clicking a Turnstile widget).

So this scraper is a *best-effort* harvester: it walks the entry pages of
every body-type category and scrapes page 1 of each, plus the bare
``/cars-for-sale`` page. That yields ~120-150 unique cars per pass — a
small slice of one2car's full inventory but enough for cross-source price
comparisons. Full coverage requires either:

  * an interactive (headful) Playwright session where you click Turnstile,
  * a 3rd-party CF solver service (2Captcha / ScraperAPI / Bright Data),
  * or a fresh ``cf_clearance`` cookie scoped to the paginated URL space
    (``CF_CLEARANCE`` env var path, kept for future use).

Install once::

    pip install --user --break-system-packages playwright playwright-stealth
    python -m playwright install chromium
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from . import _common as C

SOURCE = "one2car"
HOMEPAGE = "https://www.one2car.com/"
BARE_LIST_URL = "https://www.one2car.com/cars-for-sale"

# URL-encoded "/รถ-สำหรับ-ขาย/" (the canonical Thai search prefix one2car uses)
SEARCH_PREFIX = (
    "https://www.one2car.com/"
    + urllib.parse.quote("รถ-สำหรับ-ขาย", safe="")
    + "/"
)
BODY_TYPES = ["Sedan", "SUV", "Pickup", "Hatchback", "Van", "Wagon",
              "Coupe", "Convertible"]

ID_RE = re.compile(r"/for-sale/[^/]+/(\d+)")
PRICE_RE = re.compile(r"\(([\d,]+)\s*บาท\)")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _seed_browser():
    """Launch chromium with stealth patches; return (pw, browser, ctx, page).

    Caller closes the browser. Stealth alone doesn't beat CF on paginated
    URLs, but combined with a homepage warm-up it lets us reach every
    body-type entry page without challenge.
    """
    from playwright.sync_api import sync_playwright  # type: ignore
    try:
        from playwright_stealth import Stealth  # type: ignore
        stealth = Stealth()
    except Exception:
        stealth = None

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/132.0.0.0 Safari/537.36"
        ),
        locale="th-TH",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "th,en;q=0.8"},
    )
    if stealth:
        stealth.apply_stealth_sync(ctx)
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    page = ctx.new_page()
    return pw, browser, ctx, page


def _navigate_through_cf(page, url: str, timeout: float = 30.0) -> bool:
    """Open a URL and wait for the CF "รอสักครู่" title to flip away.

    Returns True if the page loaded normal content within the timeout,
    False if Cloudflare is still challenging us.
    """
    page.goto(url, timeout=int(timeout * 1000), wait_until="domcontentloaded")
    deadline = time.time() + timeout
    while time.time() < deadline:
        title = page.title()
        if not title.startswith("รอสัก") and "moment" not in title.lower():
            return True
        time.sleep(1)
    return False


def _read_listing_cards(page) -> list[dict]:
    """Pull every listing card (both DOM variants) into plain dicts.

    one2car uses two card markups:
      * ``article.card`` on /cars-for-sale (homepage-style preview)
      * ``article.listing--card`` on /รถ-สำหรับ-ขาย/body-* (real catalog)

    Both expose the same critical info via ``data-listing-id`` /
    ``data-default-line-text`` / ``data-display-title`` / ``data-url``.
    """
    return page.eval_on_selector_all(
        "article.listing--card, article.card",
        """els => els.map(el => {
            const lid = el.getAttribute('data-listing-id');
            const title = el.getAttribute('data-display-title')
                       || el.getAttribute('data-title')
                       || (el.querySelector('h3.card__title a, .listing__title a')?.textContent || '').trim();
            const lineText = el.getAttribute('data-default-line-text') || '';
            const url = el.getAttribute('data-url')
                     || (el.querySelector('a.card__thumbnail, a.listing__thumbnail')?.href)
                     || (el.querySelector('h3.card__title a, .listing__title a')?.href);
            const img = el.querySelector('img');
            const priceEl = el.querySelector('.listing__price, .card__price');
            const priceText = priceEl ? priceEl.textContent.trim() : '';
            return {
                listingId: lid,
                title: title,
                lineText: lineText,
                priceText: priceText,
                url: url,
                img: img ? (img.getAttribute('data-src') || img.src) : null,
            };
        })""",
    )


def _normalise(card: dict) -> dict | None:
    url = card.get("url") or ""
    lid = card.get("listingId")
    if not lid:
        m = ID_RE.search(url)
        if not m:
            return None
        lid = m.group(1)
    title = (card.get("title") or "").strip()
    # Price: prefer the ``data-default-line-text`` substring "(199,000 บาท)"
    # because it's plain text; fall back to the visible price element.
    price = None
    line = card.get("lineText") or ""
    m = PRICE_RE.search(line)
    if not m:
        m = re.search(r"([\d,]+)", card.get("priceText") or "")
    if m:
        price = C.parse_int(m.group(1))
    year = None
    ym = YEAR_RE.search(title)
    if ym:
        year = int(ym.group(0))
    parts = title.split()
    make = None
    if year and parts and parts[0] == str(year) and len(parts) > 1:
        make = parts[1].upper()
    return {
        "cid": f"{SOURCE}:{lid}",
        "title": title,
        "namemmt": title,
        "prc": price,
        "yr4": year,
        "amake": make,
        "url": url,
        "img": card.get("img"),
        "raw_json": json.dumps(card, ensure_ascii=False, separators=(",", ":")),
    }


def _harvest(conn, run_id: int, scraped_at: str, sleep_s: float) -> tuple[int, int]:
    pw, browser, ctx, page = _seed_browser()
    queries = 0
    seen: set[str] = set()
    rows_buffer: list[dict] = []
    blocked = 0

    def absorb(label: str) -> int:
        cards = _read_listing_cards(page)
        new = 0
        for c in cards:
            row = _normalise(c)
            if not row or row["cid"] in seen:
                continue
            seen.add(row["cid"])
            rows_buffer.append(row)
            new += 1
        C.log(SOURCE, f"{label}: {len(cards)} cards, {new} new (total={len(seen)})")
        return new

    try:
        # --- Warm up CF cookie via homepage --------------------------------
        C.log(SOURCE, "warming up CF cookie via homepage…")
        if not _navigate_through_cf(page, HOMEPAGE, timeout=30):
            C.log(SOURCE, "homepage stayed on CF challenge; aborting")
            return 0, 0
        time.sleep(3)

        # --- Bare /cars-for-sale (~31 cards) ------------------------------
        if _navigate_through_cf(page, BARE_LIST_URL, timeout=30):
            time.sleep(3)
            queries += 1
            absorb("/cars-for-sale")
        else:
            blocked += 1
            C.log(SOURCE, "/cars-for-sale: CF blocked")

        # --- One page per body-type category -----------------------------
        for body in BODY_TYPES:
            url = f"{SEARCH_PREFIX}body-{body}?page_size=12&page_number=1"
            if not _navigate_through_cf(page, url, timeout=40):
                blocked += 1
                C.log(SOURCE, f"body-{body}: CF blocked, skipping")
                continue
            time.sleep(2 + sleep_s)
            queries += 1
            absorb(f"body-{body}")

        # --- Pagination is consistently CF-blocked. Document and stop. ---
        if blocked:
            C.log(SOURCE, f"{blocked} URL(s) stuck on CF — pagination unavailable "
                          f"in headless mode without a Turnstile solver.")

        if rows_buffer:
            C.insert_rows(conn, rows_buffer, scraped_at, SOURCE, run_id)
        return queries, len(seen)
    finally:
        browser.close()
        pw.stop()


def run(conn, *, sleep_s: float = 2.0, note: str | None = None,
        max_pages: int | None = None) -> None:
    run_id, scraped_at = C.open_run(conn, SOURCE, note=note)
    C.log(SOURCE, f"run #{run_id} starting (best-effort: bare list + body-type p1)")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        C.log(SOURCE, "Playwright not installed — install with: "
                      "pip install playwright && python -m playwright install chromium")
        C.close_run(conn, run_id, queries=0, cars_seen=0, cars_unique=0,
                    status="blocked",
                    error="Playwright not installed")
        return

    try:
        queries, unique = _harvest(conn, run_id, scraped_at, sleep_s)
        if unique == 0:
            C.close_run(conn, run_id, queries=queries, cars_seen=0,
                        cars_unique=0, status="blocked",
                        error="Cloudflare challenge — no cards captured")
        else:
            C.close_run(conn, run_id, queries=queries, cars_seen=unique,
                        cars_unique=unique)
        C.log(SOURCE, f"run #{run_id} done — {unique} unique, {queries} queries")
    except Exception as e:
        C.close_run(conn, run_id, queries=0, cars_seen=0, cars_unique=0,
                    status="error", error=str(e))
        C.log(SOURCE, f"run #{run_id} FAILED: {e}")
        raise
