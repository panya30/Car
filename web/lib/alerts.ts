import { getDb } from "./db";

export type Alert = {
  alert_id: number;
  kind: string;
  cid: string | null;
  cohort_key: string | null;
  severity: string | null;
  title: string | null;
  detail: string | null;
  payload_json: string | null;
  created_at: string;
  notified_at: string | null;
  seen_at: string | null;
};

export function listAlerts(opts: { limit?: number; unseenOnly?: boolean } = {}): Alert[] {
  const { limit = 100, unseenOnly = false } = opts;
  const where = unseenOnly ? "WHERE seen_at IS NULL" : "";
  return getDb()
    .prepare<[number], Alert>(
      `SELECT * FROM alerts ${where} ORDER BY created_at DESC LIMIT ?`,
    )
    .all(limit);
}

export function alertSummary() {
  const db = getDb();
  const total = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM alerts",
  ).get();
  const unseen = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM alerts WHERE seen_at IS NULL",
  ).get();
  const notified = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM alerts WHERE notified_at IS NOT NULL",
  ).get();
  const anomalies = db.prepare<[], { n: number }>(
    "SELECT COUNT(*) AS n FROM alerts WHERE kind = 'anomaly' AND seen_at IS NULL",
  ).get();
  return {
    total: total?.n ?? 0,
    unseen: unseen?.n ?? 0,
    notified: notified?.n ?? 0,
    anomaliesUnseen: anomalies?.n ?? 0,
  };
}
