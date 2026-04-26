import Link from "next/link";
import {
  matchGroups,
  matchListings,
  matchSummary,
  type MatchGroup,
} from "@/lib/matches";

export const dynamic = "force-dynamic";

type SearchParams = { spread?: string; sources?: string; expand?: string };

function fmtBaht(x: number | null) {
  if (x == null) return "—";
  return `฿${Math.round(x).toLocaleString()}`;
}

export default async function MatchesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const minSpread = sp.spread ? Number(sp.spread) : 0;
  const minSources = sp.sources ? Number(sp.sources) : 2;

  const summary = matchSummary();
  const groups = matchGroups({
    minSources,
    minSpread,
    limit: 100,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Cross-source matches
        </h1>
        <p className="text-sm text-white/50 mt-1">
          Listings detected on multiple sources via signature{" "}
          <code className="text-white/70">
            (make, model, year, ฿50k bucket, 20k-km bucket)
          </code>
          . Spread = (max − min) / min × 100. Big spread + multiple sources =
          arbitrage signal or a stale listing the seller hasn&apos;t updated.
          {summary.computedAt && (
            <span className="block text-[11px] mt-1 text-white/30">
              computed {new Date(summary.computedAt).toLocaleString("en-GB")} ·{" "}
              re-run with <code>python cross_source.py</code>
            </span>
          )}
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total groups" value={summary.groups.toLocaleString()} />
        <Stat
          label="Cross-source groups"
          value={summary.crossSourceGroups.toLocaleString()}
        />
        <Stat
          label="Listings matched"
          value={summary.listingsMatched.toLocaleString()}
        />
        <Stat label="Showing" value={groups.length.toString()} />
      </div>

      <form
        method="get"
        action="/matches"
        className="flex flex-wrap gap-2 text-sm"
      >
        <select
          name="sources"
          defaultValue={String(minSources)}
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        >
          <option value="1">All groups (incl. single-source)</option>
          <option value="2">Cross-source (≥2 sources)</option>
          <option value="3">Multi-source (≥3 sources)</option>
        </select>
        <select
          name="spread"
          defaultValue={String(minSpread)}
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        >
          <option value="0">Any spread</option>
          <option value="5">≥ 5% spread</option>
          <option value="10">≥ 10% spread</option>
          <option value="20">≥ 20% spread</option>
        </select>
        <button
          type="submit"
          className="bg-[#3ba3ff] hover:bg-[#3ba3ff]/85 rounded text-black font-medium px-4"
        >
          Filter
        </button>
      </form>

      <div className="space-y-3">
        {groups.map((g) => (
          <MatchRow
            key={g.group_id}
            group={g}
            expanded={sp.expand === g.group_id}
          />
        ))}
        {groups.length === 0 && (
          <p className="text-white/40 text-sm">No matches at this filter.</p>
        )}
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

function MatchRow({
  group,
  expanded,
}: {
  group: MatchGroup;
  expanded: boolean;
}) {
  const listings = expanded ? matchListings(group.group_id) : [];

  const spreadColor =
    group.spread_pct >= 15
      ? "text-emerald-300"
      : group.spread_pct >= 8
        ? "text-amber-300"
        : "text-white/60";

  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02]">
      <Link
        href={
          expanded
            ? `/matches`
            : `/matches?expand=${encodeURIComponent(group.group_id)}`
        }
        className="block p-4 hover:bg-white/[0.03] transition"
      >
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="font-medium text-white/90">
            {group.yr4} {group.make} {group.model}
          </span>
          <span className="text-xs text-white/40 tabular-nums">
            n={group.n_listings} · {group.n_sources} source
            {group.n_sources > 1 ? "s" : ""}
          </span>
          <span className="ml-auto flex items-baseline gap-3">
            <span className="text-sm tabular-nums text-white/70">
              {fmtBaht(group.cheapest_prc)} → {fmtBaht(group.dearest_prc)}
            </span>
            <span className={`text-sm font-semibold tabular-nums ${spreadColor}`}>
              {group.spread_pct.toFixed(1)}%
            </span>
          </span>
        </div>
        <div className="text-[11px] text-white/30 mt-1 font-mono">
          {group.group_id}
        </div>
      </Link>

      {expanded && (
        <div className="border-t border-white/5 p-4 space-y-2">
          {listings.map((l) => {
            const url =
              l.url ??
              (l.source === "taladrod"
                ? `https://www.taladrod.com/w40/iCar/CarDet.aspx?cid=${l.cid.replace(/^[^:]+:/, "")}`
                : "#");
            const deltaColor =
              l.delta_pct === 0
                ? "text-emerald-300"
                : l.delta_pct >= 10
                  ? "text-rose-300"
                  : "text-amber-300";
            return (
              <a
                key={l.cid}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block rounded px-3 py-2 hover:bg-white/[0.03] text-sm"
              >
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-white/40 bg-white/5 px-1.5 py-0.5 rounded">
                    {l.source}
                  </span>
                  <span className="text-white/85 truncate flex-1">
                    {l.title ?? l.cid}
                  </span>
                  <span className="font-semibold tabular-nums text-[#3ba3ff]">
                    {fmtBaht(l.prc)}
                  </span>
                  <span className={`tabular-nums w-16 text-right ${deltaColor}`}>
                    {l.delta_pct === 0
                      ? "cheapest"
                      : `+${l.delta_pct.toFixed(0)}%`}
                  </span>
                </div>
                <div className="text-[11px] text-white/35 mt-0.5">
                  cid {l.cid}
                  {l.mileage_km != null && (
                    <> · {l.mileage_km.toLocaleString()} km</>
                  )}
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
