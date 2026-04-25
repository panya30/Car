"""Quick stats from cars.db. Run after `python scraper.py`."""
from db import connect


def main():
    conn = connect()

    print("=== Recent scrape runs ===")
    runs = list(conn.execute("""
        SELECT run_id, started_at, finished_at, queries_run, cars_unique, status, note
        FROM scrape_runs
        ORDER BY run_id DESC
        LIMIT 10
    """))
    if not runs:
        print("  (none)")
    for r in runs:
        d = dict(r)
        print(f"  #{d['run_id']:<3} {d['started_at']} -> {d['finished_at'] or '...'} "
              f"q={d['queries_run']:<4} unique={d['cars_unique']:<5} {d['status']}"
              + (f"  [{d['note']}]" if d['note'] else ""))

    latest = conn.execute("SELECT MAX(scraped_at) AS ts FROM listings").fetchone()
    if not latest or not latest["ts"]:
        print("\nNo listings yet.")
        return
    ts = latest["ts"]
    print(f"\nLatest snapshot: {ts}")

    print("\n=== Top 15 makes (latest snapshot) ===")
    for row in conn.execute("""
        SELECT m.name AS make,
               COUNT(*) AS n,
               AVG(l.prc) AS avg_p,
               MIN(l.prc) AS min_p,
               MAX(l.prc) AS max_p
        FROM listings l
        LEFT JOIN makes m ON CAST(m.mk AS INTEGER) = l.mk
        WHERE l.scraped_at = ?
        GROUP BY m.name
        ORDER BY n DESC
        LIMIT 15
    """, (ts,)):
        d = dict(row)
        avg = int(d["avg_p"] or 0)
        mn = int(d["min_p"] or 0)
        mx = int(d["max_p"] or 0)
        name = d["make"] or "(unknown)"
        print(f"  {name:<14} n={d['n']:<5} avg={avg:>10,}  range={mn:,}–{mx:,}")

    print("\n=== Year distribution (latest snapshot) ===")
    for row in conn.execute("""
        SELECT yr4, COUNT(*) AS n
        FROM listings
        WHERE scraped_at = ? AND yr4 IS NOT NULL
        GROUP BY yr4
        ORDER BY yr4 DESC
    """, (ts,)):
        print(f"  {row['yr4']}: {row['n']}")

    print("\n=== Totals ===")
    n_latest = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE scraped_at = ?", (ts,)
    ).fetchone()[0]
    n_total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    n_snaps = conn.execute("SELECT COUNT(DISTINCT scraped_at) FROM listings").fetchone()[0]
    n_uniq = conn.execute("SELECT COUNT(DISTINCT cid) FROM listings").fetchone()[0]
    print(f"  cars in latest snapshot: {n_latest:,}")
    print(f"  total snapshot rows:     {n_total:,}")
    print(f"  distinct snapshots:      {n_snaps:,}")
    print(f"  distinct cids ever seen: {n_uniq:,}")

    print("\n=== Price changes (cars seen in 2+ snapshots with prc change) ===")
    rows = list(conn.execute("""
        SELECT cid,
               COUNT(DISTINCT prc) AS n_prices,
               MIN(prc) AS lo,
               MAX(prc) AS hi,
               MAX(scraped_at) AS last_seen
        FROM listings
        WHERE prc IS NOT NULL
        GROUP BY cid
        HAVING n_prices > 1
        ORDER BY (hi - lo) DESC
        LIMIT 10
    """))
    if not rows:
        print("  (need 2+ snapshots before price changes appear)")
    for r in rows:
        d = dict(r)
        print(f"  cid={d['cid']:<10} prices={d['n_prices']}  {int(d['lo']):,}–{int(d['hi']):,}  last={d['last_seen']}")

    conn.close()


if __name__ == "__main__":
    main()
