"""Run every scraper in sequence — one full snapshot of every source.

Usage:

    python scrape_all.py                  # one full pass, all sources
    python scrape_all.py --only kaidee    # one source only
    python scrape_all.py --skip one2car   # everything except one2car
    python scrape_all.py --loop 24h       # forever, 24-hour gap between passes
    python scrape_all.py --loop 6h --jitter 30m
"""
from __future__ import annotations

import argparse
import importlib
import random
import re
import time
from datetime import datetime, timedelta

from db import connect, init

# Scrapers run in order; failures in one don't abort the others.
SOURCES = ["taladrod", "kaidee", "toyotasure", "carcarrod", "one2car"]


def _parse_duration(s: str) -> float:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(s|m|h|d)?\s*", s, re.I)
    if not m:
        raise ValueError(f"bad duration: {s!r}")
    n = float(m.group(1))
    unit = (m.group(2) or "s").lower()
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _import_scraper(source: str):
    if source == "taladrod":
        # The legacy taladrod scraper lives at scraper.py:run() and writes the
        # same DB; reuse it as-is so we don't fork the working logic.
        return importlib.import_module("scraper")
    return importlib.import_module(f"scrapers.{source}")


def _run_source(source: str, sleep_s: float, note: str | None) -> bool:
    print(f"\n{'═' * 60}\n▶ {source}  (note={note})\n{'═' * 60}", flush=True)
    init()
    conn = connect()
    try:
        mod = _import_scraper(source)
        if source == "taladrod":
            mod.run(sleep_s=sleep_s, note=note)
        else:
            mod.run(conn, sleep_s=sleep_s, note=note)
        return True
    except Exception as e:
        print(f"!! {source} FAILED: {e}", flush=True)
        return False
    finally:
        conn.close()


def one_pass(args) -> dict[str, bool]:
    sources = list(SOURCES)
    if args.only:
        sources = [s for s in sources if s in args.only]
    if args.skip:
        sources = [s for s in sources if s not in args.skip]
    note = args.note or f"scheduled pass {datetime.now().isoformat(timespec='minutes')}"
    results: dict[str, bool] = {}
    for source in sources:
        sleep_s = args.sleep_taladrod if source == "taladrod" else args.sleep
        ok = _run_source(source, sleep_s, note)
        results[source] = ok
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=SOURCES,
                    help="only run these sources (repeatable)")
    ap.add_argument("--skip", action="append", choices=SOURCES,
                    help="skip these sources (repeatable)")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between requests for non-taladrod sources")
    ap.add_argument("--sleep-taladrod", type=float, default=6.0,
                    help="seconds between requests for taladrod (WAF-prone)")
    ap.add_argument("--loop", default=None,
                    help="loop forever, sleeping this duration between passes "
                         "(e.g. 24h, 6h, 30m). Omit for one-shot.")
    ap.add_argument("--jitter", default="0",
                    help="random extra wait per loop iteration (e.g. 30m)")
    ap.add_argument("--note", default=None)
    args = ap.parse_args()

    if not args.loop:
        results = one_pass(args)
        n_ok = sum(1 for v in results.values() if v)
        print(f"\n=== summary === {n_ok}/{len(results)} OK", flush=True)
        for s, ok in results.items():
            print(f"  {'✓' if ok else '✗'} {s}", flush=True)
        return

    interval_s = _parse_duration(args.loop)
    jitter_s = _parse_duration(args.jitter)
    print(f"loop mode: every {interval_s/3600:.1f}h "
          f"(±{jitter_s/60:.0f} min jitter)", flush=True)
    while True:
        started = datetime.now()
        results = one_pass(args)
        n_ok = sum(1 for v in results.values() if v)
        print(f"\n=== pass done at {datetime.now().isoformat(timespec='seconds')} ===")
        print(f"   {n_ok}/{len(results)} OK", flush=True)
        wait = interval_s + random.uniform(0, jitter_s)
        next_run = started + timedelta(seconds=wait)
        print(f"   sleeping until {next_run.isoformat(timespec='seconds')} "
              f"({wait/3600:.1f}h)", flush=True)
        time.sleep(wait)


if __name__ == "__main__":
    main()
