"""Taladrod listings scraper.

Strategy: each query at /w40/isch/schc.aspx returns up to 600 cars in an
embedded `var SchDataJSON = {...}` blob. To cover the full catalog, we:

  1. fetch fno:all to discover the make facet (~50 makes),
  2. drill each make (mk:N),
  3. for any make that hits the 600-cap, drill its model facet (mk:N+md:M).

Each run inserts a fresh snapshot keyed by (cid, scraped_at), so re-running
appends history rather than overwriting.
"""
import argparse
import gzip
import http.cookiejar
import json
import random
import re
import time
import urllib.request
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request

from db import connect, init

URL = "https://www.taladrod.com/w40/isch/schc.aspx"
HEADERS = {
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
    "Referer": "https://www.taladrod.com/w40/isch/schc.aspx?fno:all",
}
PAGE_CAP = 600
DEFAULT_SLEEP = 3.0
TIMEOUT = 30
MAX_RETRIES = 3
JSON_RE = re.compile(r"var SchDataJSON=")
WAF_HEADER = "x-amzn-waf-action"

_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))

# Optional: curl-cffi gives a real Chrome TLS fingerprint, which dramatically
# lowers the chance of getting a CloudFront/WAF challenge. Falls back to stdlib.
try:
    from curl_cffi import requests as _cffi_requests  # type: ignore
    _cffi_session = _cffi_requests.Session()
    USE_CFFI = True
except Exception:
    _cffi_session = None
    USE_CFFI = False


class WAFBlocked(RuntimeError):
    pass


def http_get(url):
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if USE_CFFI:
                resp = _cffi_session.get(
                    url, headers=HEADERS, impersonate="chrome131", timeout=TIMEOUT
                )
                waf = resp.headers.get(WAF_HEADER)
                if waf == "challenge":
                    raise WAFBlocked(f"AWS WAF challenge on {url}")
                return resp.text
            else:
                req = Request(url, headers=HEADERS)
                with _OPENER.open(req, timeout=TIMEOUT) as resp:
                    if resp.headers.get(WAF_HEADER) == "challenge":
                        raise WAFBlocked(f"AWS WAF challenge on {url}")
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    return raw.decode("utf-8", errors="replace")
        except WAFBlocked:
            raise
        except (HTTPError, URLError, TimeoutError) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt + random.random())
    raise last_err


def fetch_query(query):
    html = http_get(f"{URL}?{query}")
    m = JSON_RE.search(html)
    if not m:
        # Empty/short response with no SchDataJSON typically means "0 results"
        # for that filter combination. Distinguish from real errors.
        if len(html) < 5000 and "SchDataJSON" not in html:
            return {"cars": [], "ncar": "0", "lists": [], "_empty": True}
        raise ValueError(f"SchDataJSON not found for query={query!r} (resp_len={len(html)})")
    decoder = json.JSONDecoder()
    data, _ = decoder.raw_decode(html[m.end():])
    return data


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


INSERT_SQL = """
INSERT OR IGNORE INTO listings (
    cid, scraped_at, run_id, yr4, mk, md, bd, ta,
    amake, amodel, abody, atrim, namemmt, title,
    prc, sbaht, prvprc, pcdisc, dpmt, cbt,
    isnew, issold, ishot, isdp, isvo, isdprc,
    upd, ipgvw, ireg, img, raw_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def car_to_row(car, scraped_at, run_id):
    return (
        car.get("cid"),
        scraped_at,
        run_id,
        parse_int(car.get("yr4")),
        parse_int(car.get("mk")),
        parse_int(car.get("md")),
        parse_int(car.get("bd")),
        parse_int(car.get("ta")),
        car.get("amake"),
        car.get("amodel"),
        car.get("abody"),
        car.get("atrim"),
        car.get("namemmt"),
        car.get("title"),
        parse_int(car.get("prc")),
        car.get("sbaht"),
        car.get("prvprc"),
        parse_int(car.get("pcdisc")),
        car.get("dpmt"),
        car.get("cbt"),
        car.get("isnew"),
        car.get("issold"),
        car.get("ishot"),
        car.get("isdp"),
        car.get("isvo"),
        car.get("isdprc"),
        car.get("upd"),
        parse_int(car.get("ipgvw")),
        car.get("ireg"),
        car.get("img"),
        json.dumps(car, ensure_ascii=False, separators=(",", ":")),
    )


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def crawl(conn, run_id, scraped_at, sleep_s, max_makes=None, smoke=False):
    seen = set()
    rows = []
    queries_run = 0

    def absorb(data, label):
        nonlocal queries_run
        queries_run += 1
        cars = data.get("cars", [])
        ncar = parse_int(data.get("ncar"), 0)
        new = 0
        for car in cars:
            cid = car.get("cid")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            rows.append(car_to_row(car, scraped_at, run_id))
            new += 1
        log(f"  {label}: cars={len(cars)} ncar={ncar} new={new} total={len(seen)}")
        return ncar

    log("Step 1: fetch fno:all")
    try:
        root = fetch_query("fno:all")
    except WAFBlocked as e:
        log(f"FATAL: {e}. Cool-down and retry, or use Playwright/curl-cffi (see README).")
        raise
    absorb(root, "fno:all")
    makes = root.get("lists", []) or []
    log(f"Discovered {len(makes)} makes")

    for m in makes:
        conn.execute(
            """
            INSERT INTO makes (mk, name, first_seen, last_seen, last_count)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(mk) DO UPDATE SET
                name = excluded.name,
                last_seen = excluded.last_seen
            """,
            (m.get("mk"), m.get("name"), scraped_at, scraped_at),
        )
    conn.commit()

    if smoke:
        log("smoke mode: skipping make/model drill")
        makes = []
    elif max_makes is not None:
        makes = makes[:max_makes]
        log(f"limited to first {len(makes)} makes")

    log("Step 2: drill each make")
    for i, make in enumerate(makes, 1):
        mk = make.get("mk")
        name = make.get("name")
        time.sleep(sleep_s + random.uniform(0, sleep_s * 0.3))
        try:
            page = fetch_query(f"mk:{mk}")
        except WAFBlocked as e:
            log(f"  [{i}/{len(makes)}] mk:{mk} ({name}) WAF block, sleeping 60s")
            time.sleep(60)
            try:
                page = fetch_query(f"mk:{mk}")
            except Exception as e2:
                log(f"  [{i}/{len(makes)}] mk:{mk} ({name}) WAF retry FAILED: {e2}")
                continue
        except Exception as e:
            log(f"  [{i}/{len(makes)}] mk:{mk} ({name}) FAILED: {e}")
            continue
        ncar = absorb(page, f"[{i}/{len(makes)}] mk:{mk} {name}")
        conn.execute("UPDATE makes SET last_count = ? WHERE mk = ?", (ncar, mk))

        models = page.get("lists", []) or []
        for model in models:
            conn.execute(
                """
                INSERT INTO models (mk, md, name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mk, md) DO UPDATE SET
                    name = excluded.name,
                    last_seen = excluded.last_seen
                """,
                (mk, model.get("md"), model.get("name"), scraped_at, scraped_at),
            )
        conn.commit()

        if ncar < PAGE_CAP:
            continue

        log(f"    {name} hit {PAGE_CAP}-cap; drilling {len(models)} models")
        for j, model in enumerate(models, 1):
            md = model.get("md")
            mname = model.get("name")
            time.sleep(sleep_s + random.uniform(0, sleep_s * 0.3))
            try:
                page2 = fetch_query(f"mk:{mk}+md:{md}")
            except WAFBlocked:
                log(f"    [{j}/{len(models)}] mk:{mk}+md:{md} WAF block, sleeping 60s")
                time.sleep(60)
                try:
                    page2 = fetch_query(f"mk:{mk}+md:{md}")
                except Exception as e2:
                    log(f"    [{j}/{len(models)}] mk:{mk}+md:{md} ({mname}) retry FAILED: {e2}")
                    continue
            except Exception as e:
                log(f"    [{j}/{len(models)}] mk:{mk}+md:{md} ({mname}) FAILED: {e}")
                continue
            absorb(page2, f"    [{j}/{len(models)}] mk:{mk}+md:{md} {mname}")

    log(f"Inserting {len(rows)} rows...")
    conn.executemany(INSERT_SQL, rows)
    conn.commit()
    return queries_run, len(rows), len(seen)


def run(sleep_s=DEFAULT_SLEEP, max_makes=None, smoke=False, note=None):
    init()
    conn = connect()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO scrape_runs (started_at, status, note) VALUES (?, 'running', ?)",
        (started, note),
    )
    run_id = cur.lastrowid
    conn.commit()
    log(f"Run #{run_id} started at {started}  (transport={'curl-cffi' if USE_CFFI else 'urllib'})")

    try:
        q, cs, cu = crawl(conn, run_id, started, sleep_s, max_makes=max_makes, smoke=smoke)
    except KeyboardInterrupt:
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE scrape_runs SET finished_at=?, status='interrupted' WHERE run_id=?",
            (finished, run_id),
        )
        conn.commit()
        log(f"Run #{run_id} interrupted")
        raise
    except Exception as e:
        finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE scrape_runs SET finished_at=?, status='error', error=? WHERE run_id=?",
            (finished, str(e), run_id),
        )
        conn.commit()
        log(f"Run #{run_id} FAILED: {e}")
        raise
    finally:
        conn.close()

    conn = connect()
    finished = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        UPDATE scrape_runs
        SET finished_at=?, queries_run=?, cars_seen=?, cars_unique=?, status='ok'
        WHERE run_id=?
        """,
        (finished, q, cs, cu, run_id),
    )
    conn.commit()
    conn.close()
    log(f"Run #{run_id} OK — {cu} unique cars, {q} queries, finished {finished}")


def main():
    ap = argparse.ArgumentParser(description="Scrape Taladrod listings into SQLite.")
    ap.add_argument("--sleep", type=float, default=DEFAULT_SLEEP,
                    help="seconds between requests (default 1.0)")
    ap.add_argument("--max-makes", type=int, default=None,
                    help="limit to first N makes (for testing)")
    ap.add_argument("--smoke", action="store_true",
                    help="only fetch fno:all and stop")
    ap.add_argument("--note", default=None, help="free-text note for this run")
    args = ap.parse_args()
    run(sleep_s=args.sleep, max_makes=args.max_makes, smoke=args.smoke, note=args.note)


if __name__ == "__main__":
    main()
