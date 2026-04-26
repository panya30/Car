"""Multimodal photo analysis on listing images.

For each car the cohort detector ranks as a DEAL or ANOMALY, we feed the
listing's primary thumbnail to Claude Sonnet 4.6 and ask for the four
red-flag categories that matter in the Thai used-car market:

  * flood damage (water-line on dashboard, rust on lower panels, mildew)
  * paint mismatch (panel-to-panel colour differences, overspray)
  * accident repair (uneven panel gaps, replaced bumper)
  * odometer rollback proxy (interior wear inconsistent with claimed km)

The model returns a structured JSON verdict; we persist it to
`photo_analyses` so later runs are idempotent and the UI can render the
findings inline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone

from db import connect, init


SYSTEM_PROMPT = """You are an experienced Thai used-car appraiser auditing a single listing photo.

Look at the image and return a JSON object exactly matching this schema (no
prose, no code-fence — just JSON):

{
  "risk_score": <integer 0-100, higher = more risk>,
  "flags": {
    "flood_damage": <bool>,
    "paint_mismatch": <bool>,
    "accident_repair": <bool>,
    "interior_inconsistent_with_km": <bool>
  },
  "findings": [
    "<one-line observation in Thai or English>",
    ...
  ],
  "confidence": "low" | "medium" | "high"
}

Be conservative. If the image is too small, low-res, or only shows a logo
or interior cluster, set confidence="low" and risk_score<=20. Don't invent
defects you can't see. Specific to Thailand: flood damage is the most
common hidden defect — look for water lines on door cards, rust on lower
suspension components, mildew patterns on upholstery.
"""


PROMPT_TEMPLATE = (
    "Listing context (do NOT use this to fabricate findings — only as "
    "context for what should/shouldn't be present):\n"
    "  Year: {year}\n"
    "  Make/Model: {make} {model}\n"
    "  Claimed mileage: {mileage}\n"
    "  Listed price: ฿{price:,}\n"
    "\n"
    "Audit the photo per your instructions. Return JSON only."
)


def _candidates_sql(only_anomaly: bool, only_unanalyzed: bool, limit: int) -> tuple[str, list]:
    where = ["cs.classification IN ('anomaly', 'deal')"] if only_anomaly else []
    where.append("cs.cid IS NOT NULL")
    if only_unanalyzed:
        where.append("pa.cid IS NULL")
    return (
        f"""
        SELECT cs.cid, cs.classification,
               json_extract(cs.story_json, '$.deal.img') AS img,
               json_extract(cs.story_json, '$.deal.title') AS title,
               json_extract(cs.story_json, '$.deal.prc') AS prc,
               json_extract(cs.story_json, '$.deal.yr4') AS yr4,
               json_extract(cs.story_json, '$.deal.mileage_km') AS mileage,
               cs.make, cs.model
        FROM cached_stories cs
        LEFT JOIN photo_analyses pa ON pa.cid = cs.cid
        WHERE {' AND '.join(where)}
        ORDER BY (cs.classification = 'anomaly') DESC, cs.discount_pct DESC
        LIMIT ?
        """,
        [limit],
    )


def analyze_one(client, model_id: str, *, cid: str, img_url: str,
                year: int | None, make: str, model: str,
                mileage: int | None, prc: int | None) -> dict:
    """Send one photo to Claude and return the parsed JSON verdict."""
    import urllib.request
    # Anthropic SDK accepts URL or base64. URL is simplest.
    user_text = PROMPT_TEMPLATE.format(
        year=year or "?", make=make, model=model,
        mileage=f"{mileage:,} km" if mileage else "unknown",
        price=prc or 0,
    )
    msg = client.messages.create(
        model=model_id,
        max_tokens=600,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "url", "url": img_url}},
                {"type": "text", "text": user_text},
            ],
        }],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    # Strip code fences if Claude added any despite our instruction.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
    try:
        return json.loads(cleaned)
    except Exception:
        return {
            "risk_score": None, "flags": {}, "findings": [],
            "confidence": "low", "_parse_error": text,
        }


def run(*, only_anomaly: bool = False, only_unanalyzed: bool = True,
        limit: int = 50, model_id: str = "claude-sonnet-4-6") -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"skipped": "ANTHROPIC_API_KEY not set"}
    try:
        import anthropic  # type: ignore
    except Exception as e:
        return {"skipped": f"anthropic SDK missing: {e}"}

    init()
    conn = connect()
    sql, params = _candidates_sql(only_anomaly, only_unanalyzed, limit)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return {"analyzed": 0, "note": "no candidates"}

    client = anthropic.Anthropic()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_ok = n_err = 0
    for r in rows:
        if not r["img"]:
            continue
        try:
            verdict = analyze_one(
                client, model_id,
                cid=r["cid"], img_url=r["img"],
                year=r["yr4"], make=r["make"], model=r["model"],
                mileage=r["mileage"], prc=r["prc"],
            )
        except Exception as e:
            n_err += 1
            print(f"  {r['cid']} ERR: {e}")
            continue
        conn.execute(
            """INSERT INTO photo_analyses
               (cid, img_url, model_id, risk_score, findings, flags_json,
                raw_response, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(cid) DO UPDATE SET
                 model_id=excluded.model_id,
                 risk_score=excluded.risk_score,
                 findings=excluded.findings,
                 flags_json=excluded.flags_json,
                 raw_response=excluded.raw_response,
                 analyzed_at=excluded.analyzed_at""",
            (
                r["cid"], r["img"], model_id,
                verdict.get("risk_score"),
                "\n".join(verdict.get("findings") or []),
                json.dumps(verdict.get("flags") or {}, ensure_ascii=False),
                json.dumps(verdict, ensure_ascii=False),
                now,
            ),
        )
        n_ok += 1
        if n_ok % 5 == 0:
            conn.commit()
            print(f"  analyzed {n_ok}/{len(rows)}", flush=True)
    conn.commit()
    return {"analyzed": n_ok, "errors": n_err, "candidates": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--only-anomaly", action="store_true",
                    help="restrict to anomaly stories")
    ap.add_argument("--reanalyze", action="store_true",
                    help="re-run analysis on already-analyzed photos")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args()
    summary = run(
        only_anomaly=args.only_anomaly,
        only_unanalyzed=not args.reanalyze,
        limit=args.limit,
        model_id=args.model,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
