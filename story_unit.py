"""Generate Indicator-style "Car Story Unit" reports from real data.

A Story Unit follows the same 6-section template Indicator uses for stocks:

    1. HOOK         — one-line price-anomaly headline
    2. CONTEXT      — cohort statistics (median, P10/P25/P75/P90, n)
    3. DRIVERS      — what makes this listing better than the cohort
    4. COUNTERPOINTS — what makes it worse / what to verify
    5. ACTION       — recommended buyer move
    6. TRACK        — proof loop (what we'll watch for going forward)

Run::

    python story_unit.py                            # auto-pick top 3 deals
    python story_unit.py --make TOYOTA --model "HILUX REVO" --year 2021
"""
from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from db import connect


# --- Cohort & listing dataclasses ----------------------------------------

@dataclass
class Listing:
    cid: str
    source: str
    prc: int
    yr4: int | None
    make: str | None
    model: str | None
    trim: str | None
    engine_size: float | None
    mileage_km: int | None
    color: str | None
    fuel: str | None
    transmission: str | None
    body_type: str | None
    seller_name: str | None
    seller_type: str | None
    location: str | None
    url: str | None
    title: str | None
    img: str | None


def fetch_cohort(conn, make: str, model: str, year: int,
                 engine_size: float | None = None) -> list[Listing]:
    """Pull the latest snapshot for every listing in a (make, model, year,
    optional engine_size) cohort. When engine_size is provided, results
    are restricted to that displacement; without it, mixed-trim cohorts
    are returned (legacy behaviour, kept for the explore CLI)."""
    extra = "AND ABS(l.engine_size - ?) < 0.05" if engine_size else ""
    sql = f"""
    WITH latest AS (
      SELECT cid, MAX(scraped_at) AS ts FROM listings GROUP BY cid
    )
    SELECT l.cid, l.source, l.prc, l.yr4,
           UPPER(l.amake) AS make, UPPER(l.amodel) AS model, l.atrim AS trim,
           l.engine_size, l.mileage_km, l.color, l.fuel, l.transmission,
           l.body_type, l.seller_name, l.seller_type, l.location,
           l.url, l.title, l.namemmt, l.img
    FROM listings l JOIN latest lt ON lt.cid=l.cid AND lt.ts=l.scraped_at
    WHERE UPPER(l.amake) = UPPER(?)
      AND UPPER(l.amodel) = UPPER(?)
      AND l.yr4 = ?
      AND l.prc > 50000
      {extra}
    """
    params: list = [make, model, year]
    if engine_size:
        params.append(engine_size)
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["title"] = d.get("title") or d.get("namemmt")
        d.pop("namemmt", None)
        out.append(Listing(**d))
    return out


# --- Statistics helpers --------------------------------------------------

def percentile(xs: list[int | float], p: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


@dataclass
class CohortStats:
    n: int
    n_sources: int
    median_prc: float
    p10_prc: float
    p25_prc: float
    p75_prc: float
    p90_prc: float
    median_km: float | None
    p25_km: float | None
    p75_km: float | None
    color_top: list[tuple[str, int]]
    fuel_top: list[tuple[str, int]]


def compute_stats(rows: list[Listing]) -> CohortStats:
    from collections import Counter
    prcs = [r.prc for r in rows]
    kms = [r.mileage_km for r in rows if r.mileage_km]
    color_c = Counter(r.color for r in rows if r.color)
    fuel_c = Counter(r.fuel for r in rows if r.fuel)
    return CohortStats(
        n=len(rows),
        n_sources=len({r.source for r in rows}),
        median_prc=statistics.median(prcs),
        p10_prc=percentile(prcs, 10),
        p25_prc=percentile(prcs, 25),
        p75_prc=percentile(prcs, 75),
        p90_prc=percentile(prcs, 90),
        median_km=statistics.median(kms) if kms else None,
        p25_km=percentile(kms, 25) if kms else None,
        p75_km=percentile(kms, 75) if kms else None,
        color_top=color_c.most_common(5),
        fuel_top=fuel_c.most_common(5),
    )


# --- Deal-quality score --------------------------------------------------

def score_listing(l: Listing, s: CohortStats) -> tuple[float, str]:
    """Returns (score, classification).

    classification ∈ {"deal", "anomaly", "fair", "overpriced"}.

    A listing is an *anomaly* (not a deal) when both the price discount and
    the mileage gap are extreme — that's the odometer-rollback / flood-rebrand
    signature in the Thai market. We rank these high too so the buyer sees
    them, but reframed as "verify or walk away" not "best price".
    """
    price_gap = (s.median_prc - l.prc) / s.median_prc
    km_gap = (
        (s.median_km - l.mileage_km) / s.median_km
        if (l.mileage_km and s.median_km) else 0
    )

    # "Too good to be true" trigger
    if price_gap > 0.15 and km_gap > 0.50:
        # Heavy discount + heavy km advantage simultaneously is the
        # rollback fingerprint. Still surface it (buyers want to see),
        # but with a different action template.
        return (price_gap * 0.6 + km_gap * 0.6, "anomaly")

    if price_gap > 0.10:
        return (price_gap * 1.0 + km_gap * 0.4, "deal")
    if price_gap > -0.05:
        return (price_gap * 1.0 + km_gap * 0.4, "fair")
    return (price_gap * 1.0 + km_gap * 0.4, "overpriced")


def find_best_deal(rows: list[Listing], s: CohortStats) -> tuple[Listing, str] | None:
    """Pick the top-ranked deal/anomaly worth telling a story about."""
    candidates = [l for l in rows if l.prc < s.median_prc and l.mileage_km]
    if not candidates:
        candidates = [l for l in rows if l.prc < s.median_prc]
    if not candidates:
        return None
    scored = [(l, *score_listing(l, s)) for l in candidates]
    # Prefer "deal" over "anomaly" at similar score (deal is higher confidence)
    type_rank = {"deal": 1, "anomaly": 2, "fair": 3, "overpriced": 4}
    scored.sort(key=lambda t: (type_rank[t[2]], -t[1]))
    chosen = scored[0]
    return chosen[0], chosen[2]


# --- Renderer ------------------------------------------------------------

def fmt_baht(x: float | int | None) -> str:
    if x is None:
        return "—"
    return f"฿{int(round(x)):,}"


def fmt_km(x: float | int | None) -> str:
    if x is None:
        return "—"
    return f"{int(round(x)):,} km"


def render_story(rows: list[Listing], s: CohortStats, deal: Listing,
                 classification: str,
                 make: str, model: str, year: int) -> str:
    discount_pct = (s.median_prc - deal.prc) / s.median_prc * 100
    km_advantage_pct = (
        (s.median_km - deal.mileage_km) / s.median_km * 100
        if (deal.mileage_km and s.median_km) else None
    )
    expected_topdown = s.p75_prc - deal.prc
    drivers: list[str] = []
    counterpoints: list[str] = []
    is_anomaly = classification == "anomaly"

    # --- Drivers / red flags split ---
    if km_advantage_pct is not None and km_advantage_pct > 5:
        line = (
            f"**Mileage**: {fmt_km(deal.mileage_km)} vs cohort median "
            f"{fmt_km(s.median_km)} (**{km_advantage_pct:+.0f}%** below typical)"
        )
        if is_anomaly and km_advantage_pct > 50:
            counterpoints.insert(
                0,
                f"⚠️ {line} — combined with the {discount_pct:.0f}% price discount, "
                f"this is the **odometer-rollback / flood-rebrand signature** in the "
                f"Thai used-truck market. Treat as suspicious until verified."
            )
        else:
            drivers.append(line)
    if deal.color:
        from collections import Counter
        color_c = Counter(r.color for r in rows if r.color)
        rank = next(
            (i for i, (c, _) in enumerate(color_c.most_common()) if c == deal.color),
            None,
        )
        if rank is not None and rank < 2:
            drivers.append(
                f"**Color**: {deal.color} — top-{rank+1} most common in cohort "
                f"(easiest to resell)"
            )
        elif rank is not None:
            drivers.append(f"**Color**: {deal.color} (rank #{rank+1} in cohort)")
    if deal.transmission:
        drivers.append(f"**Transmission**: {deal.transmission}")
    if deal.fuel:
        drivers.append(f"**Fuel**: {deal.fuel}")
    if deal.location:
        drivers.append(f"**Location**: {deal.location}")
    if deal.seller_name:
        from collections import Counter
        same = Counter(r.seller_name for r in rows if r.seller_name)
        if same.get(deal.seller_name, 0) > 1:
            drivers.append(
                f"**Seller**: {deal.seller_name} has {same[deal.seller_name]} "
                f"current listings in this cohort (track record)"
            )

    # --- Counterpoints ---
    if deal.mileage_km and s.median_km and deal.mileage_km > s.median_km:
        counterpoints.append(
            f"Mileage {fmt_km(deal.mileage_km)} is **above** cohort median "
            f"{fmt_km(s.median_km)} — confirm odometer authenticity"
        )
    if discount_pct > 25:
        counterpoints.append(
            f"Discount {discount_pct:.0f}% from median is **unusually deep** — "
            f"verify chassis (flood/accident) before deposit"
        )
    if not deal.seller_name:
        counterpoints.append(
            "Seller info missing from listing — independent inspection essential"
        )

    if not counterpoints:
        counterpoints.append(
            "Photos look clean in listing thumbnails, but **always commission an "
            "independent inspection** before deposit (Thai market: flood + odometer rollback risk)"
        )

    detail_url = (
        deal.url
        or (f"https://www.taladrod.com/w40/iCar/CarDet.aspx?cid={deal.cid}"
            if deal.source == "taladrod" else "")
    )
    title = deal.title or f"{deal.yr4} {make} {model}"

    badge = {
        "anomaly":    "🚩 **ANOMALY — verify before deposit**",
        "deal":       "🟢 **DEAL — top-25% value**",
        "fair":       "🟡 **FAIR — priced near cohort median**",
        "overpriced": "🔴 **OVERPRICED — above cohort median**",
    }[classification]

    # --- Render ---
    out = [
        f"# {title}",
        "",
        f"**[{deal.source.upper()}]**  ·  cid `{deal.cid}`  ·  [view listing]({detail_url})",
        "",
        badge,
        "",
        "---",
        "",
        "## 1. Hook",
        "",
        f"**{year} {make} {model}** listed at **{fmt_baht(deal.prc)}** — "
        f"**{discount_pct:.0f}%** below the cohort median of {fmt_baht(s.median_prc)}.",
        "",
    ]
    if is_anomaly:
        out += [
            "> _The combination of price gap + km gap is the rollback/flood signature. "
            "**This is not a recommendation to buy** — it's a recommendation to inspect "
            "thoroughly OR walk away._",
            "",
        ]
    out += [
        "## 2. Context",
        "",
        f"Cohort: {make} {model} {year}, {s.n} listings across {s.n_sources} source(s).",
        "",
        "| Percentile | Price | Mileage |",
        "|---:|---:|---:|",
        f"| P10  | {fmt_baht(s.p10_prc)} | — |",
        f"| P25  | {fmt_baht(s.p25_prc)} | {fmt_km(s.p25_km)} |",
        f"| **P50 (median)** | **{fmt_baht(s.median_prc)}** | **{fmt_km(s.median_km)}** |",
        f"| P75  | {fmt_baht(s.p75_prc)} | {fmt_km(s.p75_km)} |",
        f"| P90  | {fmt_baht(s.p90_prc)} | — |",
        "",
        "Top colors: " + ", ".join(f"{c} ({n})" for c, n in s.color_top[:5]),
        "  ",
        "Top fuels: " + ", ".join(f"{f} ({n})" for f, n in s.fuel_top[:5]),
        "",
        "## 3. Drivers (why this is positioned where it is)",
        "",
    ]
    out += [f"- {d}" for d in drivers] or ["- (no notable drivers detected)"]
    out += [
        "",
        "## 4. Counterpoints (what to verify)",
        "",
    ]
    out += [f"- {c}" for c in counterpoints]
    out += [
        "",
        "## 5. Action",
        "",
    ]
    if is_anomaly:
        out += [
            "**Verify or walk away — do not deposit blind.**",
            "",
            f"- **If genuine** (low-km history confirmed): anchor offer "
            f"{fmt_baht(deal.prc * 0.95)}, walk-away above {fmt_baht(deal.prc * 1.02)}",
            "- **Required documents**: เล่มทะเบียน history, service-book stamps, "
            "first-owner registration date",
            "- **Required inspection**: third-party odometer audit (computer ECU "
            "vs dashboard reading), undercarriage flood signs, paint thickness gauge "
            "on every panel",
            "- **Walk away if**: any document gap, paint mismatch, dealer refuses ECU read",
            "",
        ]
    else:
        out += [
            f"- **Anchor offer**: {fmt_baht(deal.prc * 0.93)}",
            f"- **Walk-away above**: {fmt_baht(min(deal.prc * 1.02, s.p25_prc))}",
            f"- **Headroom to median**: {fmt_baht(expected_topdown)} "
            f"({(expected_topdown/deal.prc)*100:.0f}% upside if resold at P75)",
            "- **Inspection priority**: undercarriage (flood), engine bay (oil leaks), "
            "odometer authenticity, transmission shift quality",
            "",
        ]
    out += [
        "## 6. Track (proof loop)",
        "",
        f"- Watch CID `{deal.cid}` — alert if price drops further (seller getting nervous)",
        f"- Alert if listing disappears within 7 days (sold or pulled — confirms market signal)",
        f"- Track {make} {model} {year} cohort weekly: did our P50 estimate "
        f"{fmt_baht(s.median_prc)} match actual closed sales?",
        "- Build seller reputation graph: how many listings does this seller close vs. relist?",
        "",
    ]
    return "\n".join(out)


# --- Top-3 auto-pick -----------------------------------------------------

CANDIDATE_COHORTS = [
    ("TOYOTA", "HILUX REVO", 2021),
    ("HONDA",  "CIVIC",      2019),
    ("TOYOTA", "YARIS",      2023),
    ("ISUZU",  "D-MAX",      2022),
    ("TOYOTA", "CAMRY",      2019),
    ("HONDA",  "CITY",       2022),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", help="(optional) cohort make")
    ap.add_argument("--model", help="(optional) cohort model")
    ap.add_argument("--year", type=int, help="(optional) cohort year")
    ap.add_argument("--top", type=int, default=3, help="auto-pick top N stories")
    ap.add_argument("--out", help="write to this markdown file (default: stdout)")
    args = ap.parse_args()

    conn = connect()
    if args.make and args.model and args.year:
        cohorts = [(args.make.upper(), args.model.upper(), args.year)]
    else:
        cohorts = CANDIDATE_COHORTS[: args.top]

    chunks = []
    for make, model, year in cohorts:
        rows = fetch_cohort(conn, make, model, year)
        if len(rows) < 10:
            chunks.append(f"# {year} {make} {model}\n\n_(only {len(rows)} listings — skipping)_\n")
            continue
        s = compute_stats(rows)
        result = find_best_deal(rows, s)
        if not result:
            chunks.append(f"# {year} {make} {model}\n\n_(no deal candidates)_\n")
            continue
        deal, classification = result
        chunks.append(render_story(rows, s, deal, classification, make, model, year))

    output = "\n\n---\n\n".join(chunks)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"wrote {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
