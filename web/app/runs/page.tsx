import { dbExists, listRuns } from "@/lib/db";

export const dynamic = "force-dynamic";

export default function RunsPage() {
  if (!dbExists()) {
    return <p className="text-white/50">No data yet. Run the scraper.</p>;
  }
  const runs = listRuns(100);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Scrape runs</h1>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-white/40 text-xs uppercase tracking-wide">
            <th className="text-left font-medium pb-2">#</th>
            <th className="text-left font-medium pb-2">Started</th>
            <th className="text-left font-medium pb-2">Finished</th>
            <th className="text-right font-medium pb-2">Queries</th>
            <th className="text-right font-medium pb-2">Unique</th>
            <th className="text-left font-medium pb-2 pl-3">Status</th>
            <th className="text-left font-medium pb-2 pl-3">Note</th>
            <th className="text-left font-medium pb-2 pl-3">Error</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const dur =
              r.started_at && r.finished_at
                ? Math.max(
                    0,
                    Math.round(
                      (new Date(r.finished_at).getTime() -
                        new Date(r.started_at).getTime()) /
                        1000,
                    ),
                  )
                : null;
            return (
              <tr key={r.run_id} className="border-t border-white/5 align-top">
                <td className="py-2 text-white/40 tabular-nums">#{r.run_id}</td>
                <td className="text-white/80 tabular-nums text-xs">
                  {r.started_at}
                </td>
                <td className="text-white/60 tabular-nums text-xs">
                  {r.finished_at ?? "…"}
                  {dur != null && (
                    <span className="text-white/30 ml-2">({dur}s)</span>
                  )}
                </td>
                <td className="text-right tabular-nums text-white/70">
                  {r.queries_run ?? "-"}
                </td>
                <td className="text-right tabular-nums text-white/70">
                  {r.cars_unique?.toLocaleString() ?? "-"}
                </td>
                <td className="pl-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs ${
                      r.status === "ok"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : r.status === "running"
                          ? "bg-amber-500/15 text-amber-300"
                          : r.status === "error"
                            ? "bg-rose-500/15 text-rose-300"
                            : "bg-white/10 text-white/60"
                    }`}
                  >
                    {r.status ?? "?"}
                  </span>
                </td>
                <td className="pl-3 text-white/50 text-xs">{r.note ?? ""}</td>
                <td className="pl-3 text-rose-300/80 text-xs">{r.error ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
