"""Post-scrape pipeline: matches → stories → photo verify → LINE push.

Run after every full scrape (or schedule independently). Each step is
independent and reports its own summary; a single step failing doesn't
abort the rest.

Usage::

    python pipeline.py                         # everything
    python pipeline.py --skip photos --skip line
    python pipeline.py --only stories
"""
from __future__ import annotations

import argparse
import json
import time
import traceback

import cross_source
import regenerate_stories
import photo_verify
import line_alerts
from db import connect, init


STEPS = [
    "matches",
    "stories",
    "photos",
    "line",
]


def run_pipeline(*, skip: list[str] | None = None,
                 only: list[str] | None = None,
                 photo_limit: int = 20,
                 photo_only_anomaly: bool = True,
                 line_limit: int = 10,
                 line_dry_run: bool = False) -> dict:
    skip = set(skip or [])
    if only:
        skip = set(STEPS) - set(only)

    summary: dict[str, object] = {}
    init()
    conn = connect()

    if "matches" not in skip:
        t0 = time.time()
        try:
            res = cross_source.rebuild(conn)
            res["took_s"] = round(time.time() - t0, 1)
            summary["matches"] = res
        except Exception as e:
            summary["matches"] = {"error": str(e), "trace": traceback.format_exc()}

    if "stories" not in skip:
        t0 = time.time()
        try:
            res = regenerate_stories.regenerate(conn)
            res["took_s"] = round(time.time() - t0, 1)
            summary["stories"] = res
        except Exception as e:
            summary["stories"] = {"error": str(e), "trace": traceback.format_exc()}

    conn.close()  # release WAL writer before photo_verify opens its own

    if "photos" not in skip:
        t0 = time.time()
        try:
            res = photo_verify.run(
                only_anomaly=photo_only_anomaly,
                only_unanalyzed=True,
                limit=photo_limit,
            )
            res["took_s"] = round(time.time() - t0, 1)
            summary["photos"] = res
        except Exception as e:
            summary["photos"] = {"error": str(e), "trace": traceback.format_exc()}

    if "line" not in skip:
        t0 = time.time()
        try:
            res = line_alerts.push_pending(limit=line_limit, dry_run=line_dry_run)
            res["took_s"] = round(time.time() - t0, 1)
            summary["line"] = res
        except Exception as e:
            summary["line"] = {"error": str(e), "trace": traceback.format_exc()}

    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", action="append", choices=STEPS, default=[])
    ap.add_argument("--only", action="append", choices=STEPS, default=None)
    ap.add_argument("--photo-limit", type=int, default=20)
    ap.add_argument("--photo-all", action="store_true",
                    help="analyze all candidates, not just anomalies")
    ap.add_argument("--line-limit", type=int, default=10)
    ap.add_argument("--line-dry-run", action="store_true")
    args = ap.parse_args()

    summary = run_pipeline(
        skip=args.skip,
        only=args.only,
        photo_limit=args.photo_limit,
        photo_only_anomaly=not args.photo_all,
        line_limit=args.line_limit,
        line_dry_run=args.line_dry_run,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
