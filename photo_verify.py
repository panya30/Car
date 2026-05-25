"""Multimodal photo audit on listing images via OpenAI gpt-4o.

For each car the cohort detector ranks as a DEAL or ANOMALY, we feed the
listing's primary thumbnail to OpenAI and ask for the four red-flag
categories that matter in the Thai used-car market:

  * flood damage (water-line on dashboard, rust on lower panels, mildew)
  * paint mismatch (panel-to-panel colour differences, overspray)
  * accident repair (uneven panel gaps, replaced bumper)
  * odometer rollback proxy (interior wear inconsistent with claimed km)

The model returns a structured JSON verdict (Structured Outputs); we
persist it to `photo_analyses` so subsequent runs are idempotent and the
UI can render the findings inline.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from db import connect, init
from scrapers import _common as _  # noqa: F401 — triggers .env load


SYSTEM_PROMPT = """You are an experienced Thai used-car appraiser auditing a single listing photo.

Look at the image and return JSON with this exact shape:

{
  "risk_score": <integer 0-100, higher = more risk>,
  "flags": {
    "flood_damage": <bool>,
    "paint_mismatch": <bool>,
    "accident_repair": <bool>,
    "interior_inconsistent_with_km": <bool>
  },
  "findings": ["<one-line observation in Thai or English>", ...],
  "confidence": "low" | "medium" | "high"
}

Be conservative. If the image is too small, low-res, or only shows a logo
or interior cluster, set confidence="low" and risk_score<=20. Never invent
defects you can't actually see. Specific to Thailand: flood damage is the
most common hidden defect — look for water lines on door cards, rust on
lower suspension components, mildew patterns on upholstery.
"""


VERDICT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "flags": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "flood_damage":                  {"type": "boolean"},
                "paint_mismatch":                {"type": "boolean"},
                "accident_repair":               {"type": "boolean"},
                "interior_inconsistent_with_km": {"type": "boolean"},
            },
            "required": [
                "flood_damage", "paint_mismatch",
                "accident_repair", "interior_inconsistent_with_km",
            ],
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["risk_score", "flags", "findings", "confidence"],
}


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
        ORDER BY (cs.classification = 'anomaly') DESC, ABS(cs.discount_pct) DESC
        LIMIT ?
        """,
        [limit],
    )


def analyze_one(client, model_id: str, *, img_url: str,
                year: int | None, make: str, model: str,
                mileage: int | None, prc: int | None) -> dict:
    """Send one photo to OpenAI gpt-4o and return the parsed JSON verdict."""
    user_text = (
        f"Listing context (do NOT use this to fabricate findings — only as "
        f"baseline for what should/shouldn't be present):\n"
        f"  Year: {year or '?'}\n"
        f"  Make/Model: {make} {model}\n"
        f"  Claimed mileage: {f'{mileage:,} km' if mileage else 'unknown'}\n"
        f"  Listed price: ฿{prc:,}\n\n"
        f"Audit the photo per your instructions. Return JSON only."
    )
    resp = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": img_url, "detail": "low"}},
            ]},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "PhotoAudit",
                "strict": True,
                "schema": VERDICT_SCHEMA,
            },
        },
        max_completion_tokens=600,
    )
    text = resp.choices[0].message.content or ""
    try:
        return json.loads(text)
    except Exception:
        return {
            "risk_score": None, "flags": {}, "findings": [],
            "confidence": "low", "_parse_error": text,
        }


def run(*, only_anomaly: bool = False, only_unanalyzed: bool = True,
        limit: int = 50, model_id: str = "gpt-4o") -> dict:
    if not os.environ.get("OPENAI_API_KEY"):
        return {"skipped": "OPENAI_API_KEY not set"}
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        return {"skipped": f"openai SDK missing: {e}"}

    init()
    conn = connect()
    sql, params = _candidates_sql(only_anomaly, only_unanalyzed, limit)
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return {"analyzed": 0, "note": "no candidates"}

    client = OpenAI()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_ok = n_err = 0
    for r in rows:
        if not r["img"]:
            continue
        try:
            verdict = analyze_one(
                client, model_id,
                img_url=r["img"],
                year=r["yr4"], make=r["make"], model=r["model"],
                mileage=r["mileage"], prc=r["prc"] or 0,
            )
        except Exception as e:
            n_err += 1
            print(f"  {r['cid']} ERR: {type(e).__name__}: {e}", flush=True)
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
            print(f"  analyzed {n_ok}/{len(rows)} (errs={n_err})", flush=True)
    conn.commit()
    return {"analyzed": n_ok, "errors": n_err, "candidates": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--only-anomaly", action="store_true",
                    help="restrict to anomaly stories")
    ap.add_argument("--reanalyze", action="store_true",
                    help="re-run analysis on already-analyzed photos")
    ap.add_argument("--model", default="gpt-4o")
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
