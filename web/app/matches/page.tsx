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
        <h1
          className="text-3xl font-semibold tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {tr(loc, "matches_title")}
        </h1>
        <p className="text-sm text-[color:var(--color-fg-2)] mt-1">
          {tr(loc, "matches_intro")}
          <code className="text-[color:var(--color-fg-2)]">
            (make, model, year, ฿50k, 20k-km)
          </code>
          {tr(loc, "matches_intro_continued")}
          {summary.computedAt && (
            <span className="block text-[11px] mt-1 text-[color:var(--color-fg-3)]">
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
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="1">{tr(loc, "filter_all_groups")}</option>
          <option value="2">{tr(loc, "filter_cross_source")}</option>
          <option value="3">{tr(loc, "filter_multi_source")}</option>
        </select>
        <select
          name="spread"
          defaultValue={String(minSpread)}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="0">{tr(loc, "filter_any_spread")}</option>
          <option value="5">{tr(loc, "filter_spread_5")}</option>
          <option value="10">{tr(loc, "filter_spread_10")}</option>
          <option value="20">{tr(loc, "filter_spread_20")}</option>
        </select>
        <button
          type="submit"
          className="btn-primary px-4 text-[13px] font-medium"
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
          <p className="text-[color:var(--color-fg-3)] text-sm">{tr(loc, "matches_no_results")}</p>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface rounded-xl p-4">
      <div className="text-xs uppercase tracking-wide text-[color:var(--color-fg-3)]">{label}</div>
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
      ? "text-[color:var(--color-pos)]"
      : group.spread_pct >= 8
        ? "text-[color:var(--color-warn)]"
        : "text-[color:var(--color-fg-2)]";

  return (
    <div className="surface rounded-xl">
      <Link
        href={
          expanded
            ? `/matches`
            : `/matches?expand=${encodeURIComponent(group.group_id)}`
        }
        className="block p-4 hover:bg-[color:var(--color-surface)] transition"
      >
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="font-medium text-[color:var(--color-fg)]">
            {group.yr4} {group.make} {group.model}
          </span>
          <span className="text-xs text-[color:var(--color-fg-3)] tabular-nums">
            n={group.n_listings} · {group.n_sources}{" "}
            {tr(
              loc,
              group.n_sources > 1
                ? "matches_n_sources_many"
                : "matches_n_sources_one",
            )}
          </span>
          <span className="ml-auto flex items-baseline gap-3">
            <span className="text-sm tabular-nums text-[color:var(--color-fg-2)]">
              {fmtBaht(group.cheapest_prc)} → {fmtBaht(group.dearest_prc)}
            </span>
            <span className={`text-sm font-semibold tabular-nums ${spreadColor}`}>
              {group.spread_pct.toFixed(1)}%
            </span>
          </span>
        </div>
        <div className="text-[11px] text-[color:var(--color-fg-3)] mt-1 font-mono">
          {group.group_id}
        </div>
      </Link>

      {expanded && (
        <div className="border-t border-[color:var(--color-line)] p-4 space-y-2">
          {listings.map((l) => {
            const url =
              l.url ??
              (l.source === "taladrod"
                ? `https://www.taladrod.com/w40/iCar/CarDet.aspx?cid=${l.cid.replace(/^[^:]+:/, "")}`
                : "#");
            const deltaColor =
              l.delta_pct === 0
                ? "text-[color:var(--color-pos)]"
                : l.delta_pct >= 10
                  ? "text-[color:var(--color-neg)]"
                  : "text-[color:var(--color-warn)]";
            return (
              <a
                key={l.cid}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="block rounded px-3 py-2 hover:bg-[color:var(--color-surface)] text-sm"
              >
                <div className="flex items-baseline gap-3 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[color:var(--color-fg-3)] bg-[color:var(--color-surface-2)] px-1.5 py-0.5 rounded">
                    {l.source}
                  </span>
                  <span className="text-[color:var(--color-fg)] truncate flex-1">
                    {l.title ?? l.cid}
                  </span>
                  <span className="font-semibold tabular-nums text-[color:var(--color-accent)]">
                    {fmtBaht(l.prc)}
                  </span>
                  <span className={`tabular-nums w-16 text-right ${deltaColor}`}>
                    {l.delta_pct === 0
                      ? tr(loc, "matches_cheapest")
                      : `+${l.delta_pct.toFixed(0)}%`}
                  </span>
                </div>
                <div className="text-[11px] text-[color:var(--color-fg-3)] mt-0.5">
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
