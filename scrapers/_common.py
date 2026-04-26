"""Shared HTTP + DB helpers for the per-source scrapers.

Each scraper implements ``run(conn, run_id, scraped_at, **kwargs)`` and uses the
helpers here to:

  * fetch HTML/JSON with browser-like headers and (optionally) curl-cffi's
    Chrome TLS fingerprint, which dramatically reduces WAF/Cloudflare false
    positives;
  * upsert rows into the shared ``listings`` table keyed by
    (cid, scraped_at), where cid carries a per-source prefix so two sources
    never collide;
  * track a row in ``scrape_runs`` so the UI can show progress.
"""
from __future__ import annotations

import gzip
import http.cookiejar
import json
import random
import socket
import time
import urllib.request
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request

socket.setdefaulttimeout(30)

# --- HTTP transport --------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/132.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

try:
    from curl_cffi import requests as _cffi_requests  # type: ignore

    _CFFI_SESSION = _cffi_requests.Session()
    USE_CFFI = True
except Exception:
    _CFFI_SESSION = None
    USE_CFFI = False

_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))


class WAFBlocked(RuntimeError):
    """Raised when the upstream returns a known anti-bot challenge."""


def _is_waf(headers) -> bool:
    if (headers.get("x-amzn-waf-action") or "").lower() == "challenge":
        return True
    if (headers.get("cf-mitigated") or "").lower() == "challenge":
        return True
    return False


def http_get(
    url: str,
    *,
    headers: dict | None = None,
    timeout: int = 30,
    retries: int = 3,
    impersonate: str = "chrome131",
) -> str:
    """GET a URL and return the decoded body. Raises WAFBlocked on challenges."""
    hdrs = {**DEFAULT_HEADERS, **(headers or {})}
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if USE_CFFI:
                resp = _CFFI_SESSION.get(
                    url, headers=hdrs, impersonate=impersonate, timeout=timeout,
                    allow_redirects=True,
                )
                if _is_waf(resp.headers):
                    raise WAFBlocked(f"WAF/CF challenge on {url}")
                return resp.text
            req = Request(url, headers=hdrs)
            with _OPENER.open(req, timeout=timeout) as resp:
                if _is_waf(resp.headers):
                    raise WAFBlocked(f"WAF/CF challenge on {url}")
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except WAFBlocked:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt + random.random())
    assert last_err is not None
    raise last_err


# --- Run lifecycle ---------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_run(conn, source: str, note: str | None = None) -> tuple[int, str]:
    started = now_iso()
    cur = conn.execute(
        "INSERT INTO scrape_runs (source, started_at, status, note) VALUES (?, ?, 'running', ?)",
        (source, started, note),
    )
    conn.commit()
    return cur.lastrowid, started


def close_run(conn, run_id: int, *, queries: int, cars_seen: int, cars_unique: int,
              status: str = "ok", error: str | None = None) -> None:
    conn.execute(
        """UPDATE scrape_runs
           SET finished_at=?, queries_run=?, cars_seen=?, cars_unique=?,
               status=?, error=?
           WHERE run_id=?""",
        (now_iso(), queries, cars_seen, cars_unique, status, error, run_id),
    )
    conn.commit()


# --- Listings upsert -------------------------------------------------------

LISTINGS_COLS = (
    "cid", "scraped_at", "source", "run_id",
    "yr4", "amake", "amodel", "abody", "atrim",
    "namemmt", "title", "prc", "prvprc", "pcdisc",
    "isnew", "issold", "ishot", "isdp",
    "upd", "ipgvw", "img", "url", "location",
    "mileage_km", "color", "transmission", "fuel", "body_type",
    "seller_name", "seller_type", "condition", "detail_fetched_at",
    "raw_json",
)
_INSERT_SQL = (
    f"INSERT OR IGNORE INTO listings ({', '.join(LISTINGS_COLS)}) "
    f"VALUES ({', '.join('?' for _ in LISTINGS_COLS)})"
)


def parse_int(v, default=None):
    if v is None:
        return default
    s = str(v).replace(",", "").strip()
    if not s or s in ("-", "&nbsp;"):
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def insert_rows(conn, rows: list[dict], scraped_at: str, source: str, run_id: int) -> int:
    """Bulk insert a list of normalised dicts. Missing keys default to NULL.

    `cid` should be source-prefixed to avoid PK collisions across sources
    (e.g. ``f"{source}:{native_id}"``).
    """
    if not rows:
        return 0
    payload = [
        tuple(r.get(c) if c not in ("scraped_at", "source", "run_id")
              else (scraped_at if c == "scraped_at" else (source if c == "source" else run_id))
              for c in LISTINGS_COLS)
        for r in rows
    ]
    conn.executemany(_INSERT_SQL, payload)
    conn.execute(
        "UPDATE scrape_runs SET cars_seen=cars_seen+?, cars_unique=cars_unique+? WHERE run_id=?",
        (len(rows), len(rows), run_id),
    )
    conn.commit()
    return len(rows)


def log(prefix: str, msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] [{prefix}] {msg}", flush=True)
