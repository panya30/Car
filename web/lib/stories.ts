import { getDb } from "./db";

// --- types ---------------------------------------------------------------

export type CohortRow = {
  cid: string;
  source: string;
  prc: number;
  yr4: number;
  amake: string;
  amodel: string;
  atrim: string | null;
  mileage_km: number | null;
  color: string | null;
  fuel: string | null;
  transmission: string | null;
  body_type: string | null;
  seller_name: string | null;
  location: string | null;
  url: string | null;
  title: string | null;
  img: string | null;
};

export type CohortStats = {
  n: number;
  n_sources: number;
  median_prc: number;
  p10_prc: number;
  p25_prc: number;
  p75_prc: number;
  p90_prc: number;
  median_km: number | null;
  p25_km: number | null;
  p75_km: number | null;
  topColors: { value: string; n: number }[];
  topFuels: { value: string; n: number }[];
};

export type Classification = "deal" | "anomaly" | "fair" | "overpriced";

export type Story = {
  cohort: { make: string; model: string; year: number };
  stats: CohortStats;
  deal: CohortRow;
  classification: Classification;
  discountPct: number;
  kmAdvantagePct: number | null;
  drivers: string[];
  counterpoints: string[];
};

// --- queries -------------------------------------------------------------

export function fetchCohort(make: string, model: string, year: number): CohortRow[] {
  return getDb()
    .prepare<[string, string, number], CohortRow>(
      `WITH latest AS (
         SELECT cid, MAX(scraped_at) AS ts FROM listings GROUP BY cid
       )
       SELECT l.cid, l.source, l.prc,
              l.yr4, UPPER(l.amake) AS amake, UPPER(l.amodel) AS amodel,
              l.atrim, l.mileage_km, l.color, l.fuel, l.transmission,
              l.body_type, l.seller_name, l.location, l.url,
              COALESCE(NULLIF(l.title, ''), l.namemmt) AS title, l.img
       FROM listings l
       JOIN latest lt ON lt.cid = l.cid AND lt.ts = l.scraped_at
       WHERE UPPER(l.amake) = UPPER(?)
         AND UPPER(l.amodel) = UPPER(?)
         AND l.yr4 = ?
         AND l.prc > 50000`,
    )
    .all(make, model, year);
}

// --- math ----------------------------------------------------------------

function percentile(xs: number[], p: number): number {
  if (xs.length === 0) return NaN;
  const s = [...xs].sort((a, b) => a - b);
  const k = (s.length - 1) * (p / 100);
  const lo = Math.floor(k);
  const hi = Math.min(lo + 1, s.length - 1);
  return s[lo] + (s[hi] - s[lo]) * (k - lo);
}

function median(xs: number[]): number {
  return percentile(xs, 50);
}

function topCounts<T extends string>(xs: (T | null)[], k = 5): { value: T; n: number }[] {
  const c = new Map<T, number>();
  for (const x of xs) if (x) c.set(x, (c.get(x) ?? 0) + 1);
  return [...c.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
    .map(([value, n]) => ({ value, n }));
}

export function computeStats(rows: CohortRow[]): CohortStats {
  const prcs = rows.map((r) => r.prc);
  const kms = rows.map((r) => r.mileage_km).filter((x): x is number => !!x);
  return {
    n: rows.length,
    n_sources: new Set(rows.map((r) => r.source)).size,
    median_prc: median(prcs),
    p10_prc: percentile(prcs, 10),
    p25_prc: percentile(prcs, 25),
    p75_prc: percentile(prcs, 75),
    p90_prc: percentile(prcs, 90),
    median_km: kms.length ? median(kms) : null,
    p25_km: kms.length ? percentile(kms, 25) : null,
    p75_km: kms.length ? percentile(kms, 75) : null,
    topColors: topCounts(rows.map((r) => r.color)),
    topFuels: topCounts(rows.map((r) => r.fuel)),
  };
}

// --- scoring (mirrors story_unit.py) ------------------------------------

export function scoreListing(
  l: CohortRow,
  s: CohortStats,
): { score: number; classification: Classification } {
  const priceGap = (s.median_prc - l.prc) / s.median_prc;
  const kmGap =
    l.mileage_km && s.median_km
      ? (s.median_km - l.mileage_km) / s.median_km
      : 0;

  if (priceGap > 0.15 && kmGap > 0.5) {
    return { score: priceGap * 0.6 + kmGap * 0.6, classification: "anomaly" };
  }
  if (priceGap > 0.1) {
    return { score: priceGap * 1.0 + kmGap * 0.4, classification: "deal" };
  }
  if (priceGap > -0.05) {
    return { score: priceGap * 1.0 + kmGap * 0.4, classification: "fair" };
  }
  return { score: priceGap * 1.0 + kmGap * 0.4, classification: "overpriced" };
}

const TYPE_RANK: Record<Classification, number> = {
  deal: 1,
  anomaly: 2,
  fair: 3,
  overpriced: 4,
};

export function pickStory(
  rows: CohortRow[],
  s: CohortStats,
): { deal: CohortRow; classification: Classification } | null {
  const candidates = rows.filter((l) => l.prc < s.median_prc);
  if (candidates.length === 0) return null;
  const scored = candidates.map((l) => ({
    l,
    ...scoreListing(l, s),
  }));
  scored.sort(
    (a, b) =>
      TYPE_RANK[a.classification] - TYPE_RANK[b.classification] ||
      b.score - a.score,
  );
  return { deal: scored[0].l, classification: scored[0].classification };
}

export function buildStory(
  make: string,
  model: string,
  year: number,
): Story | null {
  const rows = fetchCohort(make, model, year);
  if (rows.length < 10) return null;
  const stats = computeStats(rows);
  const picked = pickStory(rows, stats);
  if (!picked) return null;
  const { deal, classification } = picked;

  const discountPct = ((stats.median_prc - deal.prc) / stats.median_prc) * 100;
  const kmAdvantagePct =
    deal.mileage_km && stats.median_km
      ? ((stats.median_km - deal.mileage_km) / stats.median_km) * 100
      : null;

  const drivers: string[] = [];
  const counterpoints: string[] = [];
  const isAnomaly = classification === "anomaly";

  if (kmAdvantagePct !== null && kmAdvantagePct > 5) {
    const line = `Mileage: ${deal.mileage_km!.toLocaleString()} km vs cohort median ${Math.round(
      stats.median_km!,
    ).toLocaleString()} km (${kmAdvantagePct >= 0 ? "+" : ""}${kmAdvantagePct.toFixed(0)}% below typical)`;
    if (isAnomaly && kmAdvantagePct > 50) {
      counterpoints.push(
        `${line} — combined with the ${discountPct.toFixed(0)}% price discount this is the odometer-rollback / flood-rebrand signature in the Thai used-truck market. Treat as suspicious until verified.`,
      );
    } else {
      drivers.push(line);
    }
  }
  if (deal.color) {
    const colorRank = stats.topColors.findIndex((c) => c.value === deal.color);
    if (colorRank >= 0 && colorRank < 2) {
      drivers.push(`Color: ${deal.color} — top-${colorRank + 1} most common (easiest to resell)`);
    } else if (deal.color) {
      drivers.push(`Color: ${deal.color}`);
    }
  }
  if (deal.transmission) drivers.push(`Transmission: ${deal.transmission}`);
  if (deal.fuel) drivers.push(`Fuel: ${deal.fuel}`);
  if (deal.location) drivers.push(`Location: ${deal.location}`);

  if (deal.mileage_km && stats.median_km && deal.mileage_km > stats.median_km) {
    counterpoints.push(
      `Mileage ${deal.mileage_km.toLocaleString()} km is above cohort median ${Math.round(
        stats.median_km,
      ).toLocaleString()} km — confirm odometer authenticity`,
    );
  }
  if (discountPct > 25) {
    counterpoints.push(
      `Discount ${discountPct.toFixed(0)}% from median is unusually deep — verify chassis (flood/accident) before deposit`,
    );
  }
  if (counterpoints.length === 0) {
    counterpoints.push(
      "Photos look clean in thumbnails, but always commission an independent inspection before deposit (Thai market: flood + odometer rollback risk)",
    );
  }

  return {
    cohort: { make, model, year },
    stats,
    deal,
    classification,
    discountPct,
    kmAdvantagePct,
    drivers,
    counterpoints,
  };
}

export const CANDIDATE_COHORTS: { make: string; model: string; year: number }[] = [
  { make: "TOYOTA", model: "HILUX REVO", year: 2021 },
  { make: "HONDA", model: "CIVIC", year: 2019 },
  { make: "TOYOTA", model: "YARIS", year: 2023 },
  { make: "ISUZU", model: "D-MAX", year: 2022 },
  { make: "TOYOTA", model: "CAMRY", year: 2019 },
  { make: "HONDA", model: "CITY", year: 2022 },
  { make: "TOYOTA", model: "YARIS ATIV", year: 2024 },
  { make: "TOYOTA", model: "FORTUNER", year: 2020 },
];

export function topStories(n = 6): Story[] {
  const out: Story[] = [];
  for (const c of CANDIDATE_COHORTS) {
    if (out.length >= n) break;
    const story = buildStory(c.make, c.model, c.year);
    if (story) out.push(story);
  }
  return out;
}
