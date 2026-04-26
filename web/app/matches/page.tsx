import Link from "next/link";
import {
  matchGroups,
  matchListings,
  matchSummary,
  type MatchGroup,
} from "@/lib/matches";
import { getLocale, t as tr, type Locale } from "@/lib/i18n";

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
  const loc = await getLocale();
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
          {tr(loc, "matches_title")}
        </h1>
        <p className="text-sm text-white/50 mt-1">
          {tr(loc, "matches_intro")}
          <code className="text-white/70">
            (make, model, year, ฿50k, 20k-km)
          </code>
          {tr(loc, "matches_intro_continued")}
          {summary.computedAt && (
            <span className="block text-[11px] mt-1 text-white/30">
              {tr(loc, "matches_computed_at")}{" "}
              {new Date(summary.computedAt).toLocaleString(
                loc === "th" ? "th-TH" : "en-GB",
              )}{" "}
              · {tr(loc, "matches_rerun_with")}{" "}
              <code>python cross_source.py</code>
            </span>
          )}
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat
          label={tr(loc, "matches_total_groups")}
          value={summary.groups.toLocaleString()}
        />
        <Stat
          label={tr(loc, "matches_cross_source")}
          value={summary.crossSourceGroups.toLocaleString()}
        />
        <Stat
          label={tr(loc, "matches_listings_matched")}
          value={summary.listingsMatched.toLocaleString()}
        />
        <Stat
          label={tr(loc, "matches_showing")}
          value={groups.length.toString()}
        />
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
          <option value="1">{tr(loc, "filter_all_groups")}</option>
          <option value="2">{tr(loc, "filter_cross_source")}</option>
          <option value="3">{tr(loc, "filter_multi_source")}</option>
        </select>
        <select
          name="spread"
          defaultValue={String(minSpread)}
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        >
          <option value="0">{tr(loc, "filter_any_spread")}</option>
          <option value="5">{tr(loc, "filter_spread_5")}</option>
          <option value="10">{tr(loc, "filter_spread_10")}</option>
          <option value="20">{tr(loc, "filter_spread_20")}</option>
        </select>
        <button
          type="submit"
          className="bg-[#3ba3ff] hover:bg-[#3ba3ff]/85 rounded text-black font-medium px-4"
        >
          {tr(loc, "btn_filter")}
        </button>
      </form>

      <div className="space-y-3">
        {groups.map((g) => (
          <MatchRow
            key={g.group_id}
            group={g}
            expanded={sp.expand === g.group_id}
            loc={loc}
          />
        ))}
        {groups.length === 0 && (
          <p className="text-white/40 text-sm">{tr(loc, "matches_no_results")}</p>
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
  loc,
}: {
  group: MatchGroup;
  expanded: boolean;
  loc: Locale;
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
            n={group.n_listings} · {group.n_sources}{" "}
            {tr(
              loc,
              group.n_sources > 1
                ? "matches_n_sources_many"
                : "matches_n_sources_one",
            )}
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
                      ? tr(loc, "matches_cheapest")
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
