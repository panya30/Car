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

export type Listing = {
  cid: string;
  scraped_at: string;
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
  const inLatest = ts
    ? (db
        .prepare<[string], { n: number }>(
          "SELECT COUNT(*) AS n FROM listings WHERE scraped_at = ?",
        )
        .get(ts)?.n ?? 0)
    : 0;
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
  const ts = latestSnapshot();
  if (!ts) return [];
  return getDb()
    .prepare<[string, number], MakeAgg>(
      `SELECT m.name AS make,
              COUNT(*) AS n,
              AVG(l.prc) AS avg_p,
              MIN(l.prc) AS min_p,
              MAX(l.prc) AS max_p
       FROM listings l
       LEFT JOIN makes m ON CAST(m.mk AS INTEGER) = l.mk
       WHERE l.scraped_at = ?
       GROUP BY m.name
       ORDER BY n DESC
       LIMIT ?`,
    )
    .all(ts, limit);
}

export function yearDistribution(): { yr4: number; n: number }[] {
  const ts = latestSnapshot();
  if (!ts) return [];
  return getDb()
    .prepare<[string], { yr4: number; n: number }>(
      `SELECT yr4, COUNT(*) AS n
       FROM listings
       WHERE scraped_at = ? AND yr4 IS NOT NULL
       GROUP BY yr4
       ORDER BY yr4 DESC`,
    )
    .all(ts);
}

export type ListingsQuery = {
  make?: string;
  year?: number;
  minPrice?: number;
  maxPrice?: number;
  search?: string;
  sort?: "price_desc" | "price_asc" | "year_desc" | "views_desc";
  limit?: number;
  offset?: number;
};

export function listLatestListings(q: ListingsQuery = {}) {
  const ts = latestSnapshot();
  if (!ts) return { rows: [] as Listing[], total: 0 };
  const where: string[] = ["l.scraped_at = ?"];
  const params: (string | number)[] = [ts];
  if (q.make) {
    where.push("m.name = ?");
    params.push(q.make);
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
  }[q.sort ?? "year_desc"];

  const limit = Math.min(q.limit ?? 60, 200);
  const offset = Math.max(q.offset ?? 0, 0);

  const sql = `
    SELECT l.cid, l.scraped_at, l.yr4, l.mk, l.md, l.prc, l.pcdisc, l.prvprc,
           l.namemmt, l.title, l.upd, l.ipgvw, l.img,
           l.isnew, l.ishot, l.issold, l.isdp,
           COALESCE(NULLIF(l.amake, ''),  m.name)  AS make_name,
           COALESCE(NULLIF(l.amodel, ''), md.name) AS model_name
    FROM listings l
    LEFT JOIN makes  m  ON CAST(m.mk AS INTEGER)  = l.mk
    LEFT JOIN models md ON CAST(md.mk AS INTEGER) = l.mk
                       AND CAST(md.md AS INTEGER) = l.md
    WHERE ${where.join(" AND ")}
    ORDER BY ${order}
    LIMIT ? OFFSET ?
  `;
  const rows = getDb()
    .prepare<typeof params extends unknown[] ? typeof params : never, Listing>(sql)
    .all(...params, limit, offset);

  const totalSql = `
    SELECT COUNT(*) AS n
    FROM listings l
    LEFT JOIN makes  m  ON CAST(m.mk AS INTEGER) = l.mk
    WHERE ${where.join(" AND ")}
  `;
  const total = getDb()
    .prepare<(string | number)[], { n: number }>(totalSql)
    .get(...params)?.n ?? 0;
  return { rows, total };
}

export function allMakeNames(): string[] {
  const ts = latestSnapshot();
  if (!ts) return [];
  const rows = getDb()
    .prepare<[string], { name: string }>(
      `SELECT DISTINCT m.name
       FROM listings l
       JOIN makes m ON CAST(m.mk AS INTEGER) = l.mk
       WHERE l.scraped_at = ?
       ORDER BY m.name`,
    )
    .all(ts);
  return rows.map((r) => r.name).filter(Boolean);
}

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
