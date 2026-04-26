import { topStories, type Classification, type Story } from "@/lib/stories";

export const dynamic = "force-dynamic";

const BADGES: Record<Classification, { label: string; cls: string }> = {
  deal:       { label: "DEAL",       cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" },
  anomaly:    { label: "ANOMALY",    cls: "bg-rose-500/15 text-rose-300 border-rose-500/30" },
  fair:       { label: "FAIR",       cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  overpriced: { label: "OVERPRICED", cls: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30" },
};

function fmtBaht(x: number | null) {
  if (x == null || isNaN(x)) return "—";
  return `฿${Math.round(x).toLocaleString()}`;
}

function fmtKm(x: number | null) {
  if (x == null || isNaN(x)) return "—";
  return `${Math.round(x).toLocaleString()} km`;
}

export default function StoriesPage() {
  const stories = topStories(8);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Story Units</h1>
        <p className="text-sm text-white/50 mt-1">
          Indicator-style 6-section reports. Each is the top-ranked listing in
          its make/model/year cohort, with cohort statistics computed live from
          the SQLite snapshot. <span className="text-rose-300">ANOMALY</span> means
          the price+mileage gap fits the rollback / flood-rebrand signature —
          treat as <em>verify or walk away</em>, not <em>buy</em>.
        </p>
      </header>

      {stories.length === 0 && (
        <p className="text-white/50 text-sm">
          No stories — need at least 10 listings per cohort. Run more scrape
          passes.
        </p>
      )}

      <div className="space-y-8">
        {stories.map((s) => (
          <StoryCard key={`${s.cohort.make}-${s.cohort.model}-${s.cohort.year}`} story={s} />
        ))}
      </div>
    </div>
  );
}

function StoryCard({ story: s }: { story: Story }) {
  const { deal, stats, cohort, classification, discountPct, kmAdvantagePct,
          drivers, counterpoints } = s;
  const badge = BADGES[classification];
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
            — <span className="font-semibold">{discountPct.toFixed(0)}%</span>{" "}
            below cohort median {fmtBaht(stats.median_prc)}.{" "}
            {kmAdvantagePct !== null && kmAdvantagePct > 0 && (
              <>
                Mileage <span className="font-semibold">{fmtKm(deal.mileage_km)}</span> is{" "}
                <span className={isAnomaly ? "text-rose-300 font-semibold" : ""}>
                  {kmAdvantagePct.toFixed(0)}% below
                </span>{" "}
                cohort median {fmtKm(stats.median_km)}.
              </>
            )}
          </p>

          {isAnomaly && (
            <p className="mt-3 text-sm text-rose-300/90 italic">
              ⚠ The combination of price gap + km gap is the rollback / flood
              signature. <strong>Not a recommendation to buy</strong> — recommendation
              to inspect or walk away.
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
            Cohort: {stats.n} listings across {stats.n_sources} source
            {stats.n_sources > 1 ? "s" : ""}
            {stats.topColors.length > 0 && (
              <>
                {" · "}top colors:{" "}
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
        <Section title="Drivers">
          {drivers.length === 0 ? (
            <Empty />
          ) : (
            <ul className="space-y-1.5">
              {drivers.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Counterpoints" border>
          <ul className="space-y-1.5">
            {counterpoints.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </Section>
        <Section title="Action" border>
          {isAnomaly ? (
            <ul className="space-y-1.5">
              <li className="text-rose-300/90 font-medium">
                Verify or walk away — do not deposit blind.
              </li>
              <li>
                If genuine: anchor {fmtBaht(deal.prc * 0.95)}, walk-away above{" "}
                {fmtBaht(deal.prc * 1.02)}
              </li>
              <li>Required: เล่มทะเบียน history, service-book stamps, ECU odometer audit</li>
              <li>Walk away if: any document gap or paint mismatch</li>
            </ul>
          ) : (
            <ul className="space-y-1.5">
              <li>
                Anchor offer:{" "}
                <span className="text-emerald-300 font-medium">{fmtBaht(anchor)}</span>
              </li>
              <li>
                Walk-away above:{" "}
                <span className="text-amber-300 font-medium">{fmtBaht(walkAway)}</span>
              </li>
              <li>
                Headroom to median:{" "}
                <span className="text-emerald-300 font-medium">{fmtBaht(headroom)}</span>
                {headroom > 0 && (
                  <span className="text-white/40">
                    {" "}({((headroom / deal.prc) * 100).toFixed(0)}% upside if resold at P75)
                  </span>
                )}
              </li>
              <li>
                Inspect: undercarriage (flood), engine bay, odometer auth, transmission shift
              </li>
            </ul>
          )}
        </Section>
      </div>
    </article>
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

function Empty() {
  return <p className="text-white/30 italic text-xs">no notable drivers</p>;
}
