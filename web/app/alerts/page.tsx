import { alertSummary, listAlerts, type Alert } from "@/lib/alerts";
import { getLocale, t as tr, type Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const SEVERITY: Record<string, string> = {
  red:  "bg-rose-500/15 text-rose-300 border-rose-500/30",
  warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  info: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
};

const KIND_ICON: Record<string, string> = {
  anomaly: "⚠️",
  deal: "🟢",
  spread: "↔️",
};

export default async function AlertsPage() {
  const loc = await getLocale();
  const alerts = listAlerts({ limit: 80 });
  const sum = alertSummary();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          {tr(loc, "alerts_title")}
        </h1>
        <p className="text-sm text-white/50 mt-1">
          {tr(loc, "alerts_intro")}{" "}
          <code className="text-white/70">python line_alerts.py</code>{" "}
          {tr(loc, "alerts_intro_after")}{" "}
          <code className="text-white/70">LINE_CHANNEL_ACCESS_TOKEN</code> +{" "}
          <code className="text-white/70">LINE_TARGET_USER_ID</code>.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label={tr(loc, "alert_total")} value={sum.total.toLocaleString()} />
        <Stat label={tr(loc, "alert_unseen")} value={sum.unseen.toLocaleString()} />
        <Stat
          label={tr(loc, "alert_pushed")}
          value={sum.notified.toLocaleString()}
        />
        <Stat
          label={tr(loc, "alert_unseen_anomalies")}
          value={sum.anomaliesUnseen.toLocaleString()}
        />
      </div>

      <div className="space-y-2">
        {alerts.length === 0 && (
          <p className="text-white/40 text-sm">
            {tr(loc, "alerts_empty")}{" "}
            <code className="text-white/70">python regenerate_stories.py</code>{" "}
            {tr(loc, "alerts_to_generate")}
          </p>
        )}
        {alerts.map((a) => (
          <AlertRow key={a.alert_id} alert={a} loc={loc} />
        ))}
      </div>
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

function AlertRow({ alert: a, loc }: { alert: Alert; loc: Locale }) {
  const cls = SEVERITY[a.severity ?? "info"] ?? SEVERITY.info;
  const icon = KIND_ICON[a.kind] ?? "•";
  const payload = a.payload_json ? safeParse(a.payload_json) : null;
  const url = payload?.deal?.url;
  return (
    <div
      className={`rounded-lg border bg-white/[0.02] p-4 ${cls.replace("text-", "")}`}
      style={{ borderColor: cls.includes("rose") ? "rgba(244,63,94,.3)" :
                            cls.includes("amber") ? "rgba(245,158,11,.3)" :
                            "rgba(16,185,129,.3)" }}
    >
      <div className="flex items-start gap-3 flex-wrap">
        <span
          className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded border ${cls}`}
        >
          {icon} {a.kind}
        </span>
        <span className="text-white/90 font-medium flex-1">{a.title}</span>
        <span className="text-[11px] text-white/40 tabular-nums">
          {new Date(a.created_at).toLocaleString(
            loc === "th" ? "th-TH" : "en-GB",
          )}
        </span>
        {a.notified_at && (
          <span className="text-[10px] text-emerald-400/70">
            📲 {tr(loc, "alert_pushed_label")}
          </span>
        )}
      </div>
      {a.detail && (
        <p className="mt-2 text-sm text-white/65 leading-relaxed">{a.detail}</p>
      )}
      {payload?.deal && (
        <div className="mt-2 text-xs text-white/45 flex items-baseline gap-3 flex-wrap">
          <span className="tabular-nums">฿{(payload.deal.prc ?? 0).toLocaleString()}</span>
          {payload.deal.mileage_km && (
            <span className="tabular-nums">
              {payload.deal.mileage_km.toLocaleString()} km
            </span>
          )}
          {payload.deal.color && <span>{payload.deal.color}</span>}
          {payload.deal.location && <span>{payload.deal.location}</span>}
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-[#3ba3ff] hover:underline"
            >
              view listing →
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function safeParse(s: string): any {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}
