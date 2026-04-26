"""Push pending alerts to LINE subscribers via the Messaging API.

Configuration via env vars:
    LINE_CHANNEL_ACCESS_TOKEN — long-lived bot token from LINE Developers
    LINE_TARGET_USER_ID       — single userId to broadcast to (M.V.P.)
                                or LINE_TARGET_GROUP_ID for a group chat

If neither is set, this module gracefully reports skip — the rest of the
pipeline keeps working. To go multi-tenant later, replace the single
target var with a `subscribers` table.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from db import connect, init


LINE_API = "https://api.line.me/v2/bot/message/push"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _format_message(alert: dict) -> str:
    """Build the LINE text body for a single alert (LINE caps at 5000 chars)."""
    icon = {"red": "🚨", "warn": "⚠️", "info": "ℹ️"}.get(alert.get("severity", "info"), "•")
    payload = json.loads(alert["payload_json"]) if alert.get("payload_json") else {}
    deal = payload.get("deal", {})
    stats = payload.get("stats", {})
    cohort = payload.get("cohort", {})
    url = deal.get("url") or (
        f"https://www.taladrod.com/w40/iCar/CarDet.aspx?cid={deal.get('cid','').split(':')[-1]}"
        if deal.get("source") == "taladrod" else ""
    )
    median = stats.get("median_prc")
    body = [
        f"{icon} {alert['title']}",
        "",
        alert.get("detail") or "",
    ]
    if deal:
        body += [
            "",
            f"💰 ราคา: ฿{deal.get('prc', 0):,}" + (
                f"  (median ฿{int(median):,})" if median else ""
            ),
            f"📍 {deal.get('location') or '—'}",
            f"🚗 {deal.get('mileage_km', '?'):,} km · {deal.get('color') or '—'} · {deal.get('fuel') or '—'}"
                if isinstance(deal.get("mileage_km"), int)
                else f"🚗 {deal.get('color') or '—'} · {deal.get('fuel') or '—'}",
        ]
        if deal.get("seller_name"):
            body.append(f"👤 {deal['seller_name']}")
    if url:
        body += ["", f"🔗 {url}"]
    return "\n".join(s for s in body if s is not None)


def _push(token: str, to: str, message: str) -> tuple[bool, str]:
    body = json.dumps({
        "to": to,
        "messages": [{"type": "text", "text": message[:4990]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        LINE_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (resp.status < 300, f"{resp.status}")
    except urllib.error.HTTPError as e:
        return (False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")


def push_pending(*, limit: int = 10, dry_run: bool = False) -> dict:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    target = (
        os.environ.get("LINE_TARGET_USER_ID")
        or os.environ.get("LINE_TARGET_GROUP_ID")
    )
    if not token or not target:
        return {
            "skipped": "set LINE_CHANNEL_ACCESS_TOKEN + LINE_TARGET_USER_ID "
                       "(or LINE_TARGET_GROUP_ID) to enable",
        }

    init()
    conn = connect()
    rows = conn.execute(
        """SELECT alert_id, kind, cid, severity, title, detail, payload_json,
                  created_at
           FROM alerts
           WHERE notified_at IS NULL
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    n_ok = n_err = 0
    errors: list[str] = []
    for r in rows:
        msg = _format_message(dict(r))
        if dry_run:
            print(f"--- alert {r['alert_id']} ({r['kind']}) ---")
            print(msg)
            print()
            n_ok += 1
            continue
        ok, info = _push(token, target, msg)
        if ok:
            n_ok += 1
            conn.execute(
                "UPDATE alerts SET notified_at = ? WHERE alert_id = ?",
                (_now(), r["alert_id"]),
            )
            conn.commit()
        else:
            n_err += 1
            errors.append(f"#{r['alert_id']}: {info}")
    return {
        "queued": len(rows),
        "sent": n_ok,
        "errors": n_err,
        "error_detail": errors[:5],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true",
                    help="print messages instead of pushing")
    args = ap.parse_args()
    summary = push_pending(limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
