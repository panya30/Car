import ReactMarkdown from "react-markdown";

import {
  fetchCachedStories,
  topStories,
  type CachedStory,
  type Classification,
  type PhotoAnalysis,
  type Story,
} from "@/lib/stories";
import { getLocale, t as tr, type Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const BADGE_CSS: Record<Classification, string> = {
  deal:       "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  anomaly:    "bg-rose-500/15 text-rose-300 border-rose-500/30",
  fair:       "bg-amber-500/15 text-amber-300 border-amber-500/30",
  overpriced: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
};

const BADGE_KEY: Record<Classification, string> = {
  deal: "badge_deal",
  anomaly: "badge_anomaly",
  fair: "badge_fair",
  overpriced: "badge_overpriced",
};

function fmtBaht(x: number | null) {
  if (x == null || isNaN(x)) return "—";
  return `฿${Math.round(x).toLocaleString()}`;
}

function fmtKm(x: number | null) {
  if (x == null || isNaN(x)) return "—";
  return `${Math.round(x).toLocaleString()} km`;
}

export default async function StoriesPage() {
  const loc = await getLocale();
  // Prefer cached stories (precomputed by `python regenerate_stories.py`).
  // Fall back to live compute if the cache is empty.
  const cached = fetchCachedStories({ limit: 30 });
  const stories: (Story | CachedStory)[] =
    cached.length > 0 ? cached : topStories(8);
  const cachedAt = cached[0]?.generated_at;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          {tr(loc, "stories_title")}
        </h1>
        <p className="text-sm text-white/50 mt-1">
          {tr(loc, "stories_intro")}
          {cachedAt && (
            <span className="block text-[11px] text-white/30 mt-1">
              {tr(loc, "stories_cached_at")}{" "}
              {new Date(cachedAt).toLocaleString(loc === "th" ? "th-TH" : "en-GB")}{" "}
              · {tr(loc, "stories_regen_with")}{" "}
              <code className="text-white/60">python regenerate_stories.py</code>
            </span>
          )}
        </p>
      </header>

      {stories.length === 0 && (
        <p className="text-white/50 text-sm">
          {tr(loc, "stories_empty")}{" "}
          <code className="text-white/70">python pipeline.py</code>.
        </p>
      )}

      <div className="space-y-8">
        {stories.map((s, i) => {
          const cs = s as CachedStory;
          return (
            <StoryCard
              key={`${s.cohort.make}-${s.cohort.model}-${s.cohort.year}-${(s.cohort as any).engine_size ?? "x"}-${i}`}
              story={s}
              loc={loc}
              photoAnalysis={"photoAnalysis" in s ? s.photoAnalysis : undefined}
              polished={cs.llmPolished}
            />
          );
        })}
      </div>
    </div>
  );
}

function StoryCard({
  story: s,
  loc,
  photoAnalysis,
  polished,
}: {
  story: Story;
  loc: Locale;
  photoAnalysis?: PhotoAnalysis;
  polished?: string;
}) {
  const { deal, stats, cohort, classification, discountPct, kmAdvantagePct,
          drivers, counterpoints } = s;
  const badge = {
    label: tr(loc, BADGE_KEY[classification]),
    cls: BADGE_CSS[classification],
  };
  const detailUrl =
    deal.url ??
    (deal.source === "taladrod"
      ? `https://www.taladrod.com/w40/iCar/CarDet.aspx?cid=${deal.cid}`
      : "#");
  const titleParts = [cohort.year, cohort.make, cohort.model].join(" ");
  const anchor = deal.prc * 0.93;
  const walkAway = Math.min(deal.prc * 1.02, stats.p25_prc);
  const headroom = stats.p75_prc - deal.prc;
  const isAnomaly = classification === "anomaly";

  return (
    <article className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden">
      <div className="grid md:grid-cols-[280px_1fr]">
        {deal.img && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={deal.img}
            alt={deal.title ?? ""}
            className="w-full h-full md:max-h-72 object-cover bg-black/30"
            loading="lazy"
          />
        )}
        <div className="p-5">
          <div className="flex items-start gap-3 mb-2 flex-wrap">
            <span
              className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded border ${badge.cls}`}
            >
              {badge.label}
            </span>
            <span className="text-[10px] uppercase tracking-wider text-white/40 bg-white/5 px-2 py-0.5 rounded">
              {deal.source}
            </span>
            <span className="text-xs text-white/40 ml-auto">cid {deal.cid}</span>
          </div>

          <h2 className="text-xl font-semibold tracking-tight">
            <a
              href={detailUrl}
              target="_blank"
              rel="noreferrer"
              className="hover:text-[#3ba3ff]"
            >
              {deal.title ?? titleParts}
            </a>
          </h2>

          <p className="mt-3 text-sm text-white/70 leading-relaxed">
            <span className="font-semibold text-[#3ba3ff]">
              {fmtBaht(deal.prc)}
            </span>{" "}
            {loc === "th" ? "— ต่ำกว่าค่ากลาง " : "— "}
            <span className="font-semibold">{discountPct.toFixed(0)}%</span>{" "}
            {loc === "th"
              ? `(฿${Math.round(stats.median_prc).toLocaleString()}).`
              : `below cohort median ${fmtBaht(stats.median_prc)}.`}
            {kmAdvantagePct !== null && kmAdvantagePct > 0 && (
              <>
                {" "}
                {loc === "th" ? "ไมล์" : "Mileage"}{" "}
                <span className="font-semibold">{fmtKm(deal.mileage_km)}</span>{" "}
                {loc === "th" ? "ต่ำกว่าเฉลี่ยกลุ่ม " : "is "}
                <span className={isAnomaly ? "text-rose-300 font-semibold" : ""}>
                  {kmAdvantagePct.toFixed(0)}%
                </span>
                {loc === "th"
                  ? ` (${fmtKm(stats.median_km)}).`
                  : ` below cohort median ${fmtKm(stats.median_km)}.`}
              </>
            )}
          </p>

          {isAnomaly && (
            <p className="mt-3 text-sm text-rose-300/90 italic">
              ⚠ {tr(loc, "anomaly_subline")}
            </p>
          )}

          {/* Cohort stats table */}
          <div className="mt-4 grid grid-cols-5 gap-2 text-xs">
            <CohortCell pct="P10" prc={stats.p10_prc} />
            <CohortCell pct="P25" prc={stats.p25_prc} km={stats.p25_km} />
            <CohortCell pct="P50" prc={stats.median_prc} km={stats.median_km} highlight />
            <CohortCell pct="P75" prc={stats.p75_prc} km={stats.p75_km} />
            <CohortCell pct="P90" prc={stats.p90_prc} />
          </div>
          <p className="mt-2 text-[11px] text-white/35">
            {tr(loc, "cohort_summary_prefix")} {stats.n}{" "}
            {tr(loc, "cohort_summary_listings")} {stats.n_sources}{" "}
            {tr(
              loc,
              stats.n_sources > 1
                ? "cohort_summary_sources_many"
                : "cohort_summary_sources_one",
            )}
            {stats.topColors.length > 0 && (
              <>
                {" · "}
                {tr(loc, "cohort_summary_top_colors")}{" "}
                {stats.topColors
                  .slice(0, 3)
                  .map((c) => `${c.value} (${c.n})`)
                  .join(", ")}
              </>
            )}
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 border-t border-white/5">
        <Section title={tr(loc, "section_drivers")}>
          {drivers.length === 0 ? (
            <Empty msg={tr(loc, "label_drivers_empty")} />
          ) : (
            <ul className="space-y-1.5">
              {drivers.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
        </Section>
        <Section title={tr(loc, "section_counterpoints")} border>
          <ul className="space-y-1.5">
            {counterpoints.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </Section>
        <Section title={tr(loc, "section_action")} border>
          {isAnomaly ? (
            <ul className="space-y-1.5">
              <li className="text-rose-300/90 font-medium">
                {tr(loc, "anomaly_action_headline")}
              </li>
              <li>
                {tr(loc, "anomaly_action_genuine")
                  .replace("{anchor}", fmtBaht(deal.prc * 0.95))
                  .replace("{walkAway}", fmtBaht(deal.prc * 1.02))}
              </li>
              <li>{tr(loc, "anomaly_action_required")}</li>
              {tr(loc, "anomaly_action_inspection") && (
                <li>{tr(loc, "anomaly_action_inspection")}</li>
              )}
              <li>{tr(loc, "anomaly_action_walk")}</li>
            </ul>
          ) : (
            <ul className="space-y-1.5">
              <li>
                {tr(loc, "pill_anchor")}{" "}
                <span className="text-emerald-300 font-medium">{fmtBaht(anchor)}</span>
              </li>
              <li>
                {tr(loc, "pill_walkaway")}{" "}
                <span className="text-amber-300 font-medium">{fmtBaht(walkAway)}</span>
              </li>
              <li>
                {tr(loc, "pill_headroom")}{" "}
                <span className="text-emerald-300 font-medium">{fmtBaht(headroom)}</span>
                {headroom > 0 && (
                  <span className="text-white/40">
                    {" "}({((headroom / deal.prc) * 100).toFixed(0)}% {tr(loc, "pill_upside")})
                  </span>
                )}
              </li>
              <li>{tr(loc, "inspect_priority")}</li>
            </ul>
          )}
        </Section>
      </div>
      {photoAnalysis && <PhotoAnalysisStrip pa={photoAnalysis} loc={loc} />}
      {polished && <PolishedStrip md={polished} loc={loc} />}
    </article>
  );
}

function PolishedStrip({ md, loc }: { md: string; loc: Locale }) {
  return (
    <details className="border-t border-white/5 bg-white/[0.015]">
      <summary className="cursor-pointer px-5 py-3 text-xs uppercase tracking-wider font-semibold text-[#3ba3ff]/80 hover:bg-white/[0.02] transition list-none flex items-center gap-2">
        <span>{tr(loc, "polish_summary")}</span>
        <span className="text-white/30 normal-case font-normal text-[10px]">
          {tr(loc, "polish_summary_hint")}
        </span>
      </summary>
      <div className="px-5 pb-5 pt-1 prose-polished text-sm leading-relaxed text-white/85 max-w-none">
        <ReactMarkdown
          components={{
            h1: () => null, // hide the title H1; the card already has it
            h2: ({ children }) => (
              <h3 className="mt-4 mb-1 text-[11px] uppercase tracking-wider font-semibold text-white/45">
                {children}
              </h3>
            ),
            table: ({ children }) => (
              <table className="my-2 text-xs border-collapse w-auto">{children}</table>
            ),
            th: ({ children }) => (
              <th className="border border-white/10 px-2 py-1 text-white/50 font-medium">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border border-white/10 px-2 py-1 tabular-nums">{children}</td>
            ),
            ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>,
            strong: ({ children }) => (
              <strong className="text-white font-semibold">{children}</strong>
            ),
            code: ({ children }) => (
              <code className="bg-white/10 rounded px-1 py-0.5 text-[11px]">{children}</code>
            ),
          }}
        >
          {md}
        </ReactMarkdown>
      </div>
    </details>
  );
}

function PhotoAnalysisStrip({ pa, loc }: { pa: PhotoAnalysis; loc: Locale }) {
  let flags: Record<string, boolean> = {};
  try {
    flags = JSON.parse(pa.flags_json);
  } catch {}
  const triggered = Object.entries(flags).filter(([, v]) => v).map(([k]) => k);
  const score = pa.risk_score ?? 0;
  const tone =
    score >= 60
      ? "bg-rose-500/10 border-rose-500/30 text-rose-200"
      : score >= 30
        ? "bg-amber-500/10 border-amber-500/30 text-amber-200"
        : "bg-emerald-500/10 border-emerald-500/30 text-emerald-200";
  return (
    <div className={`border-t border-white/5 px-5 py-4 ${tone} text-sm`}>
      <div className="flex items-baseline gap-3 flex-wrap">
        <span className="text-[11px] uppercase tracking-wider font-semibold">
          {tr(loc, "photo_audit")}
        </span>
        <span className="font-semibold tabular-nums">
          {tr(loc, "photo_audit_score")} {score}/100
        </span>
        {triggered.length > 0 && (
          <span className="text-xs">
            {tr(loc, "photo_audit_flagged")} {triggered.join(", ")}
          </span>
        )}
        <span className="ml-auto text-[11px] opacity-70">
          {new Date(pa.analyzed_at).toLocaleString(
            loc === "th" ? "th-TH" : "en-GB",
          )}
        </span>
      </div>
      {pa.findings && (
        <ul className="mt-2 text-xs space-y-0.5 list-disc list-inside opacity-90">
          {pa.findings.split("\n").map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CohortCell({
  pct,
  prc,
  km,
  highlight = false,
}: {
  pct: string;
  prc: number;
  km?: number | null;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded p-2 text-center ${
        highlight ? "bg-[#3ba3ff]/10 border border-[#3ba3ff]/30" : "bg-white/[0.02]"
      }`}
    >
      <div className="text-[10px] text-white/40 uppercase">{pct}</div>
      <div className="font-semibold tabular-nums">{fmtBaht(prc)}</div>
      {km != null && (
        <div className="text-[10px] text-white/40 tabular-nums mt-0.5">
          {fmtKm(km)}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  border,
}: {
  title: string;
  children: React.ReactNode;
  border?: boolean;
}) {
  return (
    <div
      className={`p-5 text-sm text-white/70 leading-relaxed ${
        border ? "md:border-l border-white/5" : ""
      }`}
    >
      <h3 className="text-[11px] uppercase tracking-wider font-semibold text-white/50 mb-2">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Empty({ msg }: { msg: string }) {
  return <p className="text-white/30 italic text-xs">{msg}</p>;
}
