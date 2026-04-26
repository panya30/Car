import { dbExists, listRuns } from "@/lib/db";
import { getLocale, t as tr } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const loc = await getLocale();
  if (!dbExists()) {
    return <p className="text-white/50">{tr(loc, "no_data")}</p>;
  }
  const runs = listRuns(100);
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{tr(loc, "runs_title")}</h1>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-white/40 text-xs uppercase tracking-wide">
            <th className="text-left font-medium pb-2">{tr(loc, "th_run")}</th>
            <th className="text-left font-medium pb-2">{tr(loc, "th_started")}</th>
            <th className="text-left font-medium pb-2">{tr(loc, "th_finished")}</th>
            <th className="text-right font-medium pb-2">{tr(loc, "th_queries")}</th>
            <th className="text-right font-medium pb-2">{tr(loc, "th_unique")}</th>
            <th className="text-left font-medium pb-2 pl-3">{tr(loc, "th_status")}</th>
            <th className="text-left font-medium pb-2 pl-3">{tr(loc, "th_note")}</th>
            <th className="text-left font-medium pb-2 pl-3">{tr(loc, "th_error")}</th>
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
