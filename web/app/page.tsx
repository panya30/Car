import Link from "next/link";
import { dbExists, totals, topMakes, yearDistribution, listRuns } from "@/lib/db";

export const dynamic = "force-dynamic";

export default function Home() {
  if (!dbExists()) return <Empty />;

  const t = totals();
  const makes = topMakes(15);
  const years = yearDistribution();
  const runs = listRuns(5);

  if (!t.ts) return <Empty />;

  const maxYearN = Math.max(1, ...years.map((y) => y.n));
  const maxMakeN = Math.max(1, ...makes.map((m) => m.n));

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-white/50 mt-1">
          Latest snapshot: <time className="text-white/80">{fmtTs(t.ts)}</time>
        </p>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Cars in latest" value={t.inLatest.toLocaleString()} />
        <Stat label="Distinct cars ever" value={t.uniqueCids.toLocaleString()} />
        <Stat label="Snapshots" value={t.snapshots.toString()} />
        <Stat label="Total rows" value={t.totalRows.toLocaleString()} />
      </section>

      <section className="grid lg:grid-cols-2 gap-8">
        <Card title="Top makes (latest)">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-white/40 text-xs uppercase tracking-wide">
                <th className="text-left font-medium pb-2">Make</th>
                <th className="text-right font-medium pb-2">N</th>
                <th className="text-right font-medium pb-2">Avg ฿</th>
                <th className="text-right font-medium pb-2">Range ฿</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {makes.map((m) => (
                <tr key={m.make} className="border-t border-white/5">
                  <td className="py-2">
                    <Link
                      href={`/listings?make=${encodeURIComponent(m.make ?? "")}`}
                      className="text-white/90 hover:text-[#3ba3ff]"
                    >
                      {m.make ?? "(unknown)"}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums text-white/80">
                    {m.n.toLocaleString()}
                  </td>
                  <td className="text-right tabular-nums text-white/70">
                    {fmtPrice(m.avg_p)}
                  </td>
                  <td className="text-right tabular-nums text-white/40 text-xs">
                    {fmtPrice(m.min_p)}–{fmtPrice(m.max_p)}
                  </td>
                  <td className="pl-3 w-28">
                    <Bar pct={m.n / maxMakeN} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card title="Year distribution">
          <div className="space-y-1.5">
            {years.map((y) => (
              <div key={y.yr4} className="flex items-center gap-3 text-sm">
                <span className="w-12 text-white/50 tabular-nums">{y.yr4}</span>
                <div className="flex-1">
                  <Bar pct={y.n / maxYearN} />
                </div>
                <span className="w-14 text-right tabular-nums text-white/80">
                  {y.n.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section>
        <Card title="Recent scrape runs">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-white/40 text-xs uppercase tracking-wide">
                <th className="text-left font-medium pb-2">#</th>
                <th className="text-left font-medium pb-2">Started</th>
                <th className="text-right font-medium pb-2">Queries</th>
                <th className="text-right font-medium pb-2">Unique cars</th>
                <th className="text-left font-medium pb-2 pl-3">Status</th>
                <th className="text-left font-medium pb-2 pl-3">Note</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} className="border-t border-white/5">
                  <td className="py-2 text-white/40 tabular-nums">#{r.run_id}</td>
                  <td className="text-white/80 tabular-nums text-xs">
                    {fmtTs(r.started_at)}
                  </td>
                  <td className="text-right tabular-nums text-white/70">
                    {r.queries_run ?? "-"}
                  </td>
                  <td className="text-right tabular-nums text-white/70">
                    {r.cars_unique?.toLocaleString() ?? "-"}
                  </td>
                  <td className="pl-3">
                    <Status status={r.status} />
                  </td>
                  <td className="pl-3 text-white/40 text-xs">{r.note ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] p-4">
      <div className="text-xs uppercase tracking-wide text-white/40">{label}</div>
      <div className="text-2xl font-semibold tabular-nums mt-1">{value}</div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] p-5">
      <h2 className="text-sm font-medium uppercase tracking-wide text-white/50 mb-4">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Bar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
      <div
        className="h-full bg-[#3ba3ff]/70 rounded-full"
        style={{ width: `${Math.max(2, pct * 100)}%` }}
      />
    </div>
  );
}

function Status({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    ok: "bg-emerald-500/15 text-emerald-300",
    running: "bg-amber-500/15 text-amber-300",
    error: "bg-rose-500/15 text-rose-300",
    interrupted: "bg-orange-500/15 text-orange-300",
  };
  const cls = colors[status ?? ""] ?? "bg-white/10 text-white/60";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs ${cls}`}>
      {status ?? "?"}
    </span>
  );
}

function Empty() {
  return (
    <div className="text-center py-24 text-white/50">
      <h1 className="text-xl mb-2">No data yet</h1>
      <p className="text-sm">
        Run <code className="text-white/80">python scraper.py</code> from the repo
        root, then refresh.
      </p>
    </div>
  );
}

function fmtTs(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtPrice(p: number | null): string {
  if (p == null) return "—";
  return Math.round(p).toLocaleString();
}
