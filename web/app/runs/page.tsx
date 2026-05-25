import { dbExists, listRuns } from "@/lib/db";
import { getLocale, t as tr } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const loc = await getLocale();
  if (!dbExists()) {
    return <p className="text-fg-2">{tr(loc, "no_data")}</p>;
  }
  const runs = listRuns(100);
  return (
    <div className="space-y-6">
      <h1
        className="text-3xl font-semibold tracking-tight"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {tr(loc, "runs_title")}
      </h1>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-fg-3 text-xs uppercase tracking-wide">
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
              <tr key={r.run_id} className="border-t border-line align-top">
                <td className="py-2 text-fg-3 tabular-nums">#{r.run_id}</td>
                <td className="text-fg tabular-nums text-xs">
                  {r.started_at}
                </td>
                <td className="text-fg-2 tabular-nums text-xs">
                  {r.finished_at ?? "…"}
                  {dur != null && (
                    <span className="text-fg-3 ml-2">({dur}s)</span>
                  )}
                </td>
                <td className="text-right tabular-nums text-fg-2">
                  {r.queries_run ?? "-"}
                </td>
                <td className="text-right tabular-nums text-fg-2">
                  {r.cars_unique?.toLocaleString() ?? "-"}
                </td>
                <td className="pl-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                      r.status === "ok"
                        ? "pill-pos"
                        : r.status === "running"
                          ? "pill-warn"
                          : r.status === "error"
                            ? "pill-neg"
                            : "pill-neutral"
                    }`}
                  >
                    {r.status ?? "?"}
                  </span>
                </td>
                <td className="pl-3 text-fg-2 text-xs">{r.note ?? ""}</td>
                <td className="pl-3 text-neg text-xs">{r.error ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
