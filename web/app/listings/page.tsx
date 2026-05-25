import Link from "next/link";
import {
  allMakeNames,
  allSources,
  bodyFacet,
  colorFacet,
  dbExists,
  fuelFacet,
  listLatestListings,
  transmissionFacet,
  type ListingsQuery,
} from "@/lib/db";
import { getLocale, t as tr } from "@/lib/i18n";

export const dynamic = "force-dynamic";

type SearchParams = {
  source?: string;
  make?: string;
  year?: string;
  min?: string;
  max?: string;
  fuel?: string;
  trans?: string;
  body?: string;
  color?: string;
  maxkm?: string;
  q?: string;
  sort?: ListingsQuery["sort"];
  page?: string;
};

const PER_PAGE = 60;

export default async function ListingsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const loc = await getLocale();
  if (!dbExists()) {
    return <p className="text-fg-2">{tr(loc, "no_data")}</p>;
  }
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const offset = (page - 1) * PER_PAGE;

  const q: ListingsQuery = {
    source: sp.source || undefined,
    make: sp.make || undefined,
    year: sp.year ? Number(sp.year) : undefined,
    minPrice: sp.min ? Number(sp.min) : undefined,
    maxPrice: sp.max ? Number(sp.max) : undefined,
    fuel: sp.fuel || undefined,
    transmission: sp.trans || undefined,
    body: sp.body || undefined,
    color: sp.color || undefined,
    maxMileage: sp.maxkm ? Number(sp.maxkm) : undefined,
    search: sp.q || undefined,
    sort: sp.sort,
    limit: PER_PAGE,
    offset,
  };

  const { rows, total } = listLatestListings(q);
  const makes = allMakeNames();
  const sources = allSources();
  const fuels = fuelFacet();
  const transmissions = transmissionFacet();
  const bodies = bodyFacet();
  const colors = colorFacet().slice(0, 30); // colors can be very long-tail
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="space-y-6">
      <div>
        <h1
          className="text-3xl font-semibold tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {tr(loc, "listings_title")}
        </h1>
        <p className="text-sm text-fg-2 mt-1">
          {total.toLocaleString()} {tr(loc, "listings_count_one")} ·{" "}
          {tr(loc, "page_of")} {page} {tr(loc, "of")} {totalPages}
        </p>
      </div>

      <form
        action="/listings"
        method="get"
        className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm"
      >
        <select
          name="source"
          defaultValue={sp.source ?? ""}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="">{tr(loc, "all_sources")}</option>
          {sources.map((s) => (
            <option key={s.source} value={s.source}>
              {s.source} ({s.n.toLocaleString()})
            </option>
          ))}
        </select>
        <select
          name="make"
          defaultValue={sp.make ?? ""}
          className="field px-2.5 py-2 text-[13px] col-span-2"
        >
          <option value="">{tr(loc, "all_makes")}</option>
          {makes.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <input
          name="year"
          defaultValue={sp.year ?? ""}
          placeholder={tr(loc, "placeholder_year")}
          inputMode="numeric"
          className="field px-2.5 py-2 text-[13px]"
        />
        <input
          name="min"
          defaultValue={sp.min ?? ""}
          placeholder={tr(loc, "placeholder_min")}
          inputMode="numeric"
          className="field px-2.5 py-2 text-[13px]"
        />
        <input
          name="max"
          defaultValue={sp.max ?? ""}
          placeholder={tr(loc, "placeholder_max")}
          inputMode="numeric"
          className="field px-2.5 py-2 text-[13px]"
        />
        <select
          name="sort"
          defaultValue={sp.sort ?? "year_desc"}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="year_desc">{tr(loc, "sort_year_desc")}</option>
          <option value="price_desc">{tr(loc, "sort_price_desc")}</option>
          <option value="price_asc">{tr(loc, "sort_price_asc")}</option>
          <option value="mileage_asc">{tr(loc, "sort_mileage_asc")}</option>
          <option value="views_desc">{tr(loc, "sort_views_desc")}</option>
        </select>
        <select
          name="fuel"
          defaultValue={sp.fuel ?? ""}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="">{tr(loc, "any_fuel")}</option>
          {fuels.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.n.toLocaleString()})
            </option>
          ))}
        </select>
        <select
          name="trans"
          defaultValue={sp.trans ?? ""}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="">{tr(loc, "any_transmission")}</option>
          {transmissions.map((t) => (
            <option key={t.value} value={t.value}>
              {t.value.length > 22 ? t.value.slice(0, 22) + "…" : t.value} ({t.n.toLocaleString()})
            </option>
          ))}
        </select>
        <select
          name="body"
          defaultValue={sp.body ?? ""}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="">{tr(loc, "any_body")}</option>
          {bodies.map((b) => (
            <option key={b.value} value={b.value}>
              {b.value} ({b.n.toLocaleString()})
            </option>
          ))}
        </select>
        <select
          name="color"
          defaultValue={sp.color ?? ""}
          className="field px-2.5 py-2 text-[13px]"
        >
          <option value="">{tr(loc, "any_color")}</option>
          {colors.map((c) => (
            <option key={c.value} value={c.value}>
              {c.value} ({c.n.toLocaleString()})
            </option>
          ))}
        </select>
        <input
          name="maxkm"
          defaultValue={sp.maxkm ?? ""}
          placeholder={tr(loc, "placeholder_max_km")}
          inputMode="numeric"
          className="field px-2.5 py-2 text-[13px]"
        />
        <input
          name="q"
          defaultValue={sp.q ?? ""}
          placeholder={tr(loc, "placeholder_search")}
          className="field px-2.5 py-2 text-[13px] col-span-3 md:col-span-5"
        />
        <button
          type="submit"
          className="btn-primary px-4 text-[13px] font-medium"
        >
          {tr(loc, "btn_filter")}
        </button>
      </form>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.map((r) => {
          const cdHref =
            r.url ??
            (r.source === "taladrod"
              ? `https://www.taladrod.com/w40/iCar/CarDet.aspx?cid=${r.cid}`
              : "#");
          const titleParts = [r.yr4, r.make_name, r.model_name].filter(Boolean);
          return (
            <a
              key={r.cid}
              href={cdHref}
              target="_blank"
              rel="noreferrer"
              className="group surface rounded-xl hover:bg-surface-2 transition-colors overflow-hidden"
            >
              {r.img && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={r.img}
                  alt={r.namemmt ?? ""}
                  loading="lazy"
                  className="w-full aspect-[4/3] object-cover bg-black/30"
                />
              )}
              <div className="p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <div className="font-medium text-fg truncate">
                    {titleParts.join(" ") || r.namemmt}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className="text-[10px] uppercase tracking-wide text-fg-3 bg-surface-2 px-1.5 py-0.5 rounded">
                      {r.source}
                    </span>
                    {r.ishot === "Y" && (
                      <span className="text-[10px] uppercase tracking-wide text-rose-300 bg-rose-500/15 px-1.5 py-0.5 rounded">
                        hot
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-fg-2 truncate mt-0.5">
                  {r.title || r.namemmt}
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <div className="text-lg font-semibold tabular-nums text-accent">
                    {r.prc != null ? `฿${r.prc.toLocaleString()}` : "—"}
                  </div>
                  <div className="text-xs text-fg-3 tabular-nums">
                    {r.mileage_km != null
                      ? `${r.mileage_km.toLocaleString()} km`
                      : r.ipgvw != null
                        ? `${r.ipgvw.toLocaleString()} ${tr(loc, "suffix_views")}`
                        : ""}
                  </div>
                </div>
                {r.prvprc && (
                  <div className="mt-1 text-xs text-emerald-400/80">
                    was ฿{r.prvprc} · {r.pcdisc != null ? `-${r.pcdisc}%` : ""}
                  </div>
                )}
                <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-fg-2">
                  {r.fuel && <Spec label={r.fuel} />}
                  {r.transmission && (
                    <Spec
                      label={
                        r.transmission.length > 14
                          ? r.transmission.slice(0, 14) + "…"
                          : r.transmission
                      }
                    />
                  )}
                  {r.body_type && <Spec label={r.body_type} />}
                  {r.color && <Spec label={r.color} accent />}
                </div>
                {(r.seller_name || r.location) && (
                  <div className="mt-1.5 text-[11px] text-fg-3 truncate">
                    {[r.seller_name, r.location].filter(Boolean).join(" · ")}
                  </div>
                )}
              </div>
            </a>
          );
        })}
      </div>

      {rows.length === 0 && (
        <p className="text-fg-3 text-sm">{tr(loc, "no_matches")}</p>
      )}

      <Pagination
        current={page}
        total={totalPages}
        sp={sp}
        prevLabel={tr(loc, "pagination_prev")}
        nextLabel={tr(loc, "pagination_next")}
        pageLabel={tr(loc, "page_of")}
      />
    </div>
  );
}

function Spec({ label, accent = false }: { label: string; accent?: boolean }) {
  return (
    <span
      className={`px-1.5 py-0.5 rounded ${
        accent ? "bg-pos-bg text-accent" : "bg-surface-2"
      }`}
    >
      {label}
    </span>
  );
}

function Pagination({
  current,
  total,
  sp,
  prevLabel,
  nextLabel,
  pageLabel,
}: {
  current: number;
  total: number;
  sp: SearchParams;
  prevLabel: string;
  nextLabel: string;
  pageLabel: string;
}) {
  if (total <= 1) return null;
  const pageHref = (p: number) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(sp)) {
      if (v && k !== "page") params.set(k, v);
    }
    params.set("page", String(p));
    return `/listings?${params.toString()}`;
  };
  return (
    <div className="flex items-center justify-between text-sm pt-4">
      <div className="text-fg-3">
        {pageLabel} {current} / {total}
      </div>
      <div className="flex gap-2">
        {current > 1 && (
          <Link
            href={pageHref(current - 1)}
            className="px-3 py-1.5 border border-line rounded hover:bg-surface-2"
          >
            {prevLabel}
          </Link>
        )}
        {current < total && (
          <Link
            href={pageHref(current + 1)}
            className="px-3 py-1.5 border border-line rounded hover:bg-surface-2"
          >
            {nextLabel}
          </Link>
        )}
      </div>
    </div>
  );
}
