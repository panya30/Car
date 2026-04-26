"""LLM polish layer for Car Story Units.

Wraps the deterministic story_unit.py output in conversational Thai prose,
keeping every quantitative claim from the skeleton (cohort math, percentile
ranks, classification) but flowing as a chat-friendly summary you'd actually
send a buyer over LINE.

Usage::

    export ANTHROPIC_API_KEY=sk-ant-...
    python llm_polish.py            # polish all auto-picked stories
    python llm_polish.py --in data/stories.md --out data/stories_polished.md

Skips gracefully (echoes the deterministic version) when the API key is
missing — so a CI run never hard-fails on configuration.
"""
from __future__ import annotations

import argparse
import os

SYSTEM_PROMPT = """You are a Thai used-car analyst writing for a buyer who is about to spend ฿300k–3M.

You will be given a deterministic 6-section "Car Story Unit" containing real
market statistics (cohort median, P25/P75, mileage gaps, classification).

Your job:
1. **Preserve every quantitative claim** — every ฿ figure, every percentile,
   every km number must survive verbatim. The math is the contract.
2. **Rewrite as conversational Thai** (with English where natural, mixed
   Thai/English style typical of Thai car forums).
3. **Lead with the classification badge** (DEAL / ANOMALY / FAIR / OVERPRICED).
   For ANOMALY, the buyer's safety is the headline, not the price.
4. **One paragraph per section**, but keep the H2 headings (1. Hook ... 6. Track).
5. **Don't add data that isn't in the input**. If you don't know the seller's
   reputation, say so. No hallucinated VIN history.
6. **End every story with a single decisive line**: either "Worth pursuing
   if X verifies." or "Walk away unless Y is documented." — buyer must know
   the call.
7. Keep it tight. ~250-400 Thai/English words per story.
"""


def polish_story(skeleton: str, *, model: str = "claude-sonnet-4-6") -> str:
    """Send the deterministic skeleton to Claude and return the polished story.

    Falls back to returning the skeleton unchanged when ANTHROPIC_API_KEY
    is missing, so callers don't need to special-case unconfigured envs.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            skeleton
            + "\n\n> _(LLM polish skipped: set ANTHROPIC_API_KEY to "
              "convert this skeleton into conversational Thai prose.)_\n"
        )

    try:
        import anthropic  # type: ignore
    except Exception as e:
        return skeleton + f"\n\n> _(LLM polish skipped: anthropic SDK not "f"installed — {e})_\n"

    client = anthropic.Anthropic()

    # Cache the system prompt so subsequent stories reuse the prefix.
    msg = client.messages.create(
        model=model,
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                "Here is the deterministic Story Unit skeleton. "
                "Polish it per your instructions:\n\n" + skeleton
            ),
        }],
    )
    return "".join(b.text for b in msg.content if hasattr(b, "text"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/stories.md")
    ap.add_argument("--out", dest="out", default="data/stories_polished.md")
    ap.add_argument("--model", default="claude-sonnet-4-6")
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
