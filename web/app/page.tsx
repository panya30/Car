import Link from "next/link";
import {
  dbExists, totals, topMakes, yearDistribution, listRuns, allSources,
} from "@/lib/db";
import { getLocale, t as tr } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function Home() {
  const loc = await getLocale();
  if (!dbExists()) return <Empty msg={tr(loc, "no_data")} />;

  const t = totals();
  const makes = topMakes(15);
  const years = yearDistribution();
  const runs = listRuns(5);
  const sources = allSources();

  if (!t.ts) return <Empty msg={tr(loc, "no_data")} />;

  const maxYearN = Math.max(1, ...years.map((y) => y.n));
  const maxMakeN = Math.max(1, ...makes.map((m) => m.n));

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight" style={{fontFamily:"var(--font-display)"}}>
          {tr(loc, "overview_title")}
        </h1>
        <p className="text-sm text-[color:var(--color-fg-2)] mt-1">
          {tr(loc, "overview_latest")}{" "}
          <time className="text-[color:var(--color-fg)]">{fmtTs(t.ts)}</time>
        </p>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label={tr(loc, "stat_in_latest")} value={t.inLatest.toLocaleString()} />
        <Stat label={tr(loc, "stat_distinct_ever")} value={t.uniqueCids.toLocaleString()} />
        <Stat label={tr(loc, "stat_snapshots")} value={t.snapshots.toString()} />
        <Stat label={tr(loc, "stat_total_rows")} value={t.totalRows.toLocaleString()} />
      </section>

      <section className="flex flex-wrap gap-2 text-sm">
        {sources.map((s) => (
          <Link
            key={s.source}
            href={`/listings?source=${encodeURIComponent(s.source)}`}
            className="px-3 py-1.5 rounded-md surface hover:bg-[color:var(--color-surface-2)] transition-colors"
          >
            <span className="text-[color:var(--color-fg)] mr-2 font-medium">{s.source}</span>
            <span className="text-[color:var(--color-fg-3)] tabular-nums text-xs">
              {s.n.toLocaleString()}
            </span>
          </Link>
        ))}
      </section>

      <section className="grid lg:grid-cols-2 gap-8">
        <Card title={tr(loc, "card_top_makes")}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[color:var(--color-fg-3)] text-xs uppercase tracking-wide">
                <th className="text-left font-medium pb-2">{tr(loc, "th_make")}</th>
                <th className="text-right font-medium pb-2">{tr(loc, "th_n")}</th>
                <th className="text-right font-medium pb-2">{tr(loc, "th_avg_price")}</th>
                <th className="text-right font-medium pb-2">{tr(loc, "th_range")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {makes.map((m) => (
                <tr key={m.make} className="border-t border-[color:var(--color-line)]">
                  <td className="py-2">
                    <Link
                      href={`/listings?make=${encodeURIComponent(m.make ?? "")}`}
                      className="text-[color:var(--color-fg)] hover:text-[color:var(--color-accent)]"
                    >
                      {m.make ?? "(unknown)"}
                    </Link>
                  </td>
                  <td className="text-right tabular-nums text-[color:var(--color-fg)]">
                    {m.n.toLocaleString()}
                  </td>
                  <td className="text-right tabular-nums text-[color:var(--color-fg-2)]">
                    {fmtPrice(m.avg_p)}
                  </td>
                  <td className="text-right tabular-nums text-[color:var(--color-fg-3)] text-xs">
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

        <Card title={tr(loc, "card_year_dist")}>
          <div className="space-y-1.5">
            {years.map((y) => (
              <div key={y.yr4} className="flex items-center gap-3 text-sm">
                <span className="w-12 text-[color:var(--color-fg-2)] tabular-nums">{y.yr4}</span>
                <div className="flex-1">
                  <Bar pct={y.n / maxYearN} />
                </div>
                <span className="w-14 text-right tabular-nums text-[color:var(--color-fg)]">
                  {y.n.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section>
        <Card title={tr(loc, "card_recent_runs")}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[color:var(--color-fg-3)] text-xs uppercase tracking-wide">
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
                <tr key={r.run_id} className="border-t border-[color:var(--color-line)]">
                  <td className="py-2 text-[color:var(--color-fg-3)] tabular-nums">#{r.run_id}</td>
                  <td className="text-[color:var(--color-fg)] tabular-nums text-xs">
                    {fmtTs(r.started_at)}
                  </td>
                  <td className="text-right tabular-nums text-[color:var(--color-fg-2)]">
                    {r.queries_run ?? "-"}
                  </td>
                  <td className="text-right tabular-nums text-[color:var(--color-fg-2)]">
                    {r.cars_unique?.toLocaleString() ?? "-"}
                  </td>
                  <td className="pl-3">
                    <Status status={r.status} />
                  </td>
                  <td className="pl-3 text-[color:var(--color-fg-3)] text-xs">{r.note ?? ""}</td>
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
    <div className="surface rounded-xl p-4">
      <div className="text-[10px] uppercase tracking-[0.08em] font-semibold text-[color:var(--color-fg-3)]">
        {label}
      </div>
      <div className="text-2xl font-semibold tabular-nums mt-1 tracking-tight">
        {value}
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="surface rounded-xl p-5">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[color:var(--color-fg-3)] mb-3">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Bar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 bg-[color:var(--color-surface-2)] rounded-full overflow-hidden">
      <div
        className="h-full rounded-full"
        style={{
          width: `${Math.max(2, pct * 100)}%`,
          background:
            "linear-gradient(90deg, rgba(10,132,255,0.85), rgba(10,132,255,0.6))",
        }}
      />
    </div>
  );
}

function Status({ status }: { status: string | null }) {
  const cls =
    status === "ok"            ? "pill-pos"
    : status === "running"     ? "pill-warn"
    : status === "error"       ? "pill-neg"
    : status === "interrupted" ? "pill-warn"
    :                            "pill-neutral";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${cls}`}>
      {status ?? "?"}
    </span>
  );
}

function Empty({ msg }: { msg: string }) {
  return (
    <div className="text-center py-24 text-[color:var(--color-fg-2)]">
      <p className="text-sm">{msg}</p>
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
