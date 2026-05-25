import { getDb } from "./db";

export type MatchGroup = {
  group_id: string;
  n_listings: number;
  n_sources: number;
  cheapest_prc: number;
  dearest_prc: number;
  spread_pct: number;
  make: string;
  model: string;
  yr4: number;
  computed_at: string;
};

export type MatchListing = {
  group_id: string;
  cid: string;
  source: string;
  prc: number;
  mileage_km: number | null;
  url: string | null;
  title: string | null;
  yr4: number;
  delta_pct: number;
};

export function matchGroups(opts: {
  minSources?: number;
  minSpread?: number;
  limit?: number;
  offset?: number;
} = {}): MatchGroup[] {
  const { minSources = 2, minSpread = 0, limit = 50, offset = 0 } = opts;
  return getDb()
    .prepare<[number, number, number, number], MatchGroup>(
      `SELECT * FROM match_groups
       WHERE n_sources >= ? AND spread_pct >= ?
       ORDER BY spread_pct DESC, n_listings DESC
       LIMIT ? OFFSET ?`,
    )
    .all(minSources, minSpread, limit, offset);
}

export function matchListings(group_id: string): MatchListing[] {
  return getDb()
    .prepare<[string], MatchListing>(
      `SELECT * FROM matches WHERE group_id = ? ORDER BY prc ASC`,
    )
    .all(group_id);
}

export function matchSummary() {
  const db = getDb();
  const total = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM match_groups",
  ).get();
  const cross = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM match_groups WHERE n_sources >= 2",
  ).get();
  const matched = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM matches",
  ).get();
  const computed = db.prepare<[], { ts: string | null }>(
    "SELECT MAX(computed_at) AS ts FROM match_groups",
  ).get();
  return {
    groups: total?.n ?? 0,
    crossSourceGroups: cross?.n ?? 0,
    listingsMatched: matched?.n ?? 0,
    computedAt: computed?.ts ?? null,
  };
}

export function matchTablesExist(): boolean {
  try {
    getDb()
      .prepare(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='match_groups'",
      )
      .get();
    return true;
  } catch {
    return false;
  }
}
