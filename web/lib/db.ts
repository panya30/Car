import Database from "better-sqlite3";
import path from "node:path";

const DB_PATH = path.resolve(process.cwd(), "..", "data", "cars.db");

declare global {
  // eslint-disable-next-line no-var
  var __cars_db: Database.Database | undefined;
}

function open(): Database.Database {
  const db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
  db.pragma("journal_mode = WAL");
  return db;
}

export function getDb(): Database.Database {
  if (!global.__cars_db) global.__cars_db = open();
  return global.__cars_db;
}

export function dbExists(): boolean {
  try {
    getDb();
    return true;
  } catch {
    return false;
  }
}

export function latestSnapshot(): string | null {
  const row = getDb()
    .prepare<[], { ts: string | null }>("SELECT MAX(scraped_at) AS ts FROM listings")
    .get();
  return row?.ts ?? null;
}

const LATEST_PER_SOURCE_CTE = `
WITH latest AS (
  SELECT source, MAX(scraped_at) AS ts FROM listings GROUP BY source
)
`;
const JOIN_LATEST = `
  INNER JOIN latest lt ON lt.source = l.source AND lt.ts = l.scraped_at
`;

export type Listing = {
  cid: string;
  scraped_at: string;
  source: string;
  yr4: number | null;
  mk: number | null;
  md: number | null;
  prc: number | null;
  pcdisc: number | null;
  prvprc: string | null;
  namemmt: string | null;
  title: string | null;
  upd: string | null;
  ipgvw: number | null;
  img: string | null;
  url: string | null;
  location: string | null;
  mileage_km: number | null;
  color: string | null;
  transmission: string | null;
  fuel: string | null;
  body_type: string | null;
  seller_name: string | null;
  seller_type: string | null;
  condition: string | null;
  detail_fetched_at: string | null;
  isnew: string | null;
  ishot: string | null;
  issold: string | null;
  isdp: string | null;
  make_name: string | null;
  model_name: string | null;
};

export function totals() {
  const db = getDb();
  const ts = latestSnapshot();
  // "in latest" = sum of cars at each source's most recent snapshot.
  const inLatest = db
    .prepare<[], { n: number }>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT COUNT(*) AS n FROM listings l ${JOIN_LATEST}`,
    )
    .get()?.n ?? 0;
  const totalRows = db
    .prepare<[], { n: number }>("SELECT COUNT(*) AS n FROM listings")
    .get()?.n ?? 0;
  const snapshots = db
    .prepare<[], { n: number }>(
      "SELECT COUNT(DISTINCT scraped_at) AS n FROM listings",
    )
    .get()?.n ?? 0;
  const uniqueCids = db
    .prepare<[], { n: number }>("SELECT COUNT(DISTINCT cid) AS n FROM listings")
    .get()?.n ?? 0;
  return { ts, inLatest, totalRows, snapshots, uniqueCids };
}

export type MakeAgg = {
  make: string;
  n: number;
  avg_p: number | null;
  min_p: number | null;
  max_p: number | null;
};

export function topMakes(limit = 50): MakeAgg[] {
  return getDb()
    .prepare<[number], MakeAgg>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT COALESCE(NULLIF(l.amake, ''), m.name) AS make,
              COUNT(*) AS n,
              AVG(l.prc) AS avg_p,
              MIN(l.prc) AS min_p,
              MAX(l.prc) AS max_p
       FROM listings l ${JOIN_LATEST}
       LEFT JOIN makes m ON CAST(m.mk AS INTEGER) = l.mk
       WHERE COALESCE(NULLIF(l.amake, ''), m.name) IS NOT NULL
       GROUP BY make
       ORDER BY n DESC
       LIMIT ?`,
    )
    .all(limit);
}

export function yearDistribution(): { yr4: number; n: number }[] {
  return getDb()
    .prepare<[], { yr4: number; n: number }>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT l.yr4 AS yr4, COUNT(*) AS n
       FROM listings l ${JOIN_LATEST}
       WHERE l.yr4 IS NOT NULL
       GROUP BY l.yr4
       ORDER BY l.yr4 DESC`,
    )
    .all();
}

export type ListingsQuery = {
  source?: string;
  make?: string;
  year?: number;
  minPrice?: number;
  maxPrice?: number;
  fuel?: string;
  transmission?: string;
  body?: string;
  color?: string;
  maxMileage?: number;
  search?: string;
  sort?: "price_desc" | "price_asc" | "year_desc" | "views_desc" | "mileage_asc";
  limit?: number;
  offset?: number;
};

export function listLatestListings(q: ListingsQuery = {}) {
  // restrict to each source's latest snapshot via JOIN_LATEST below
  const where: string[] = [];
  const params: (string | number)[] = [];
  if (q.source) {
    where.push("l.source = ?");
    params.push(q.source);
  }
  if (q.make) {
    where.push("(m.name = ? OR l.amake = ?)");
    params.push(q.make, q.make);
  }
  if (q.year) {
    where.push("l.yr4 = ?");
    params.push(q.year);
  }
  if (q.minPrice) {
    where.push("l.prc >= ?");
    params.push(q.minPrice);
  }
  if (q.maxPrice) {
    where.push("l.prc <= ?");
    params.push(q.maxPrice);
  }
  if (q.fuel) {
    where.push("l.fuel = ?");
    params.push(q.fuel);
  }
  if (q.transmission) {
    where.push("l.transmission LIKE ?");
    params.push(`%${q.transmission}%`);
  }
  if (q.body) {
    where.push("l.body_type LIKE ?");
    params.push(`%${q.body}%`);
  }
  if (q.color) {
    where.push("l.color = ?");
    params.push(q.color);
  }
  if (q.maxMileage) {
    where.push("l.mileage_km <= ?");
    params.push(q.maxMileage);
  }
  if (q.search) {
    where.push("(l.namemmt LIKE ? OR l.title LIKE ?)");
    const s = `%${q.search}%`;
    params.push(s, s);
  }
  const order = {
    price_desc: "l.prc DESC NULLS LAST",
    price_asc: "l.prc ASC NULLS LAST",
    year_desc: "l.yr4 DESC NULLS LAST, l.prc DESC",
    views_desc: "l.ipgvw DESC NULLS LAST",
    mileage_asc: "l.mileage_km ASC NULLS LAST",
  }[q.sort ?? "year_desc"];

  const limit = Math.min(q.limit ?? 60, 200);
  const offset = Math.max(q.offset ?? 0, 0);

  const whereClause = where.length ? `WHERE ${where.join(" AND ")}` : "";
  const sql = `
    ${LATEST_PER_SOURCE_CTE}
    SELECT l.cid, l.scraped_at, l.source, l.yr4, l.mk, l.md, l.prc,
           l.pcdisc, l.prvprc, l.namemmt, l.title, l.upd, l.ipgvw, l.img,
           l.url, l.location, l.mileage_km, l.color, l.transmission,
           l.fuel, l.body_type, l.seller_name, l.seller_type, l.condition,
           l.detail_fetched_at,
           l.isnew, l.ishot, l.issold, l.isdp,
           COALESCE(NULLIF(l.amake, ''),  m.name)  AS make_name,
           COALESCE(NULLIF(l.amodel, ''), md.name) AS model_name
    FROM listings l ${JOIN_LATEST}
    LEFT JOIN makes  m  ON CAST(m.mk AS INTEGER)  = l.mk
    LEFT JOIN models md ON CAST(md.mk AS INTEGER) = l.mk
                       AND CAST(md.md AS INTEGER) = l.md
    ${whereClause}
    ORDER BY ${order}
    LIMIT ? OFFSET ?
  `;
  const rows = getDb()
    .prepare<typeof params extends unknown[] ? typeof params : never, Listing>(sql)
    .all(...params, limit, offset);

  const totalSql = `
    ${LATEST_PER_SOURCE_CTE}
    SELECT COUNT(*) AS n
    FROM listings l ${JOIN_LATEST}
    LEFT JOIN makes  m  ON CAST(m.mk AS INTEGER) = l.mk
    ${whereClause}
  `;
  const total = getDb()
    .prepare<(string | number)[], { n: number }>(totalSql)
    .get(...params)?.n ?? 0;
  return { rows, total };
}

export function allSources(): { source: string; n: number }[] {
  return getDb()
    .prepare<[], { source: string; n: number }>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT l.source AS source, COUNT(*) AS n
       FROM listings l ${JOIN_LATEST}
       GROUP BY l.source
       ORDER BY n DESC`,
    )
    .all();
}

export function allMakeNames(): string[] {
  const rows = getDb()
    .prepare<[], { name: string }>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT DISTINCT COALESCE(NULLIF(l.amake, ''), m.name) AS name
       FROM listings l ${JOIN_LATEST}
       LEFT JOIN makes m ON CAST(m.mk AS INTEGER) = l.mk
       WHERE COALESCE(NULLIF(l.amake, ''), m.name) IS NOT NULL
       ORDER BY name`,
    )
    .all();
  return rows.map((r) => r.name).filter(Boolean);
}

// --- facets for filter dropdowns ---------------------------------------

function _distinctFacet(col: string): { value: string; n: number }[] {
  return getDb()
    .prepare<[], { value: string; n: number }>(
      `${LATEST_PER_SOURCE_CTE}
       SELECT ${col} AS value, COUNT(*) AS n
       FROM listings l ${JOIN_LATEST}
       WHERE ${col} IS NOT NULL AND ${col} != ''
       GROUP BY ${col}
       ORDER BY n DESC`,
    )
    .all();
}

export const fuelFacet = () => _distinctFacet("l.fuel");
export const transmissionFacet = () => _distinctFacet("l.transmission");
export const bodyFacet = () => _distinctFacet("l.body_type");
export const colorFacet = () => _distinctFacet("l.color");

export type ScrapeRun = {
  run_id: number;
  started_at: string;
  finished_at: string | null;
  queries_run: number | null;
  cars_seen: number | null;
  cars_unique: number | null;
  status: string | null;
  error: string | null;
  note: string | null;
};

export function listRuns(limit = 25): ScrapeRun[] {
  return getDb()
    .prepare<[number], ScrapeRun>(
      `SELECT run_id, started_at, finished_at, queries_run, cars_seen,
              cars_unique, status, error, note
       FROM scrape_runs ORDER BY run_id DESC LIMIT ?`,
    )
    .all(limit);
}
