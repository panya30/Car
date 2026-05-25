"""LLM polish layer for Car Story Units (OpenAI GPT-4o-mini).

Wraps the deterministic story_unit.py output in conversational Thai prose,
keeping every quantitative claim from the skeleton (cohort math, percentile
ranks, classification) but flowing as a chat-friendly summary you'd send a
buyer over LINE.

Usage::

    # OPENAI_API_KEY auto-loaded from Car/.env (mirrored from indicator)
    python llm_polish.py            # polish all auto-picked stories
    python llm_polish.py --in data/stories.md --out data/stories_polished.md

Skips gracefully (echoes the deterministic version) when the API key is
missing — so a CI run never hard-fails on configuration.
"""
from __future__ import annotations

import argparse
import os

from scrapers import _common as _  # noqa: F401 — triggers .env load


SYSTEM_PROMPT = """You are a Thai used-car analyst writing for a buyer who is about to spend ฿300k–3M.

You will be given a deterministic 6-section "Car Story Unit" containing real
market statistics (cohort median, P25/P75, mileage gaps, classification).

HARD CONSTRAINTS (violations will be flagged):

1. The section structure MUST be EXACTLY:
     ## 1. Hook
     ## 2. Context
     ## 3. Drivers
     ## 4. Counterpoints
     ## 5. Action
     ## 6. Track
   Never rename, reorder, merge, or split these sections.

2. EVERY ฿ figure, EVERY percentile (P10/P25/P50/P75/P90), and EVERY km number
   must appear in the polished output VERBATIM (same digits, same units).
   NEVER invent a number that isn't in the input — no estimated mileage,
   no made-up market range, no fabricated price band.

3. NEVER add details about the car that aren't in the input. No invented
   features ("ABS, airbags, sunroof"), no invented service history, no
   invented "comparable rivals". If a fact isn't in the skeleton, it
   doesn't exist for this story.

4. The classification badge from the input (DEAL / ANOMALY / FAIR /
   OVERPRICED) appears in section 1 (Hook). For ANOMALY, the buyer's
   safety is the headline, not the price.

5. End every story with one decisive line: either "Worth pursuing if X
   verifies." or "Walk away unless Y is documented." — using only X/Y
   that the input actually mentioned (cohort drivers, counterpoints,
   inspection priorities).

6. Style: conversational Thai with English where natural (Thai car-forum
   register). One paragraph per section. Total ≤ 400 words.

7. Preserve the cohort percentile table from section 2 verbatim.
"""


def polish_story(skeleton: str, *, model: str = "gpt-4o") -> str:
    """Send the deterministic skeleton to OpenAI and return the polished story.

    Falls back to returning the skeleton unchanged when OPENAI_API_KEY
    is missing, so callers don't need to special-case unconfigured envs.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return (
            skeleton
            + "\n\n> _(LLM polish skipped: set OPENAI_API_KEY in Car/.env to "
              "convert this skeleton into conversational Thai prose.)_\n"
        )

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        return skeleton + f"\n\n> _(LLM polish skipped: openai SDK not installed — {e})_\n"

    client = OpenAI()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Here is the deterministic Story Unit skeleton. "
                    "Polish it per your instructions:\n\n" + skeleton
                ),
            },
        ],
        max_completion_tokens=900,
    )
    return resp.choices[0].message.content or skeleton


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/stories.md")
    ap.add_argument("--out", dest="out", default="data/stories_polished.md")
    ap.add_argument("--model", default="gpt-4o")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        text = f.read()

    # Stories are separated by '\n---\n' top-level dividers in story_unit.py
    skeletons = [s.strip() for s in text.split("\n---\n\n") if s.strip()]
    polished = []
    for i, sk in enumerate(skeletons, 1):
        print(f"polishing story {i}/{len(skeletons)}…", flush=True)
        polished.append(polish_story(sk, model=args.model))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(polished))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
