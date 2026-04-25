import Link from "next/link";
import {
  allMakeNames,
  dbExists,
  listLatestListings,
  type ListingsQuery,
} from "@/lib/db";

export const dynamic = "force-dynamic";

type SearchParams = {
  make?: string;
  year?: string;
  min?: string;
  max?: string;
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
  if (!dbExists()) {
    return <p className="text-white/50">No data yet. Run the scraper.</p>;
  }
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const offset = (page - 1) * PER_PAGE;

  const q: ListingsQuery = {
    make: sp.make || undefined,
    year: sp.year ? Number(sp.year) : undefined,
    minPrice: sp.min ? Number(sp.min) : undefined,
    maxPrice: sp.max ? Number(sp.max) : undefined,
    search: sp.q || undefined,
    sort: sp.sort,
    limit: PER_PAGE,
    offset,
  };

  const { rows, total } = listLatestListings(q);
  const makes = allMakeNames();
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Listings</h1>
        <p className="text-sm text-white/50 mt-1">
          {total.toLocaleString()} cars · page {page} of {totalPages}
        </p>
      </div>

      <form
        action="/listings"
        method="get"
        className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm"
      >
        <select
          name="make"
          defaultValue={sp.make ?? ""}
          className="bg-white/5 border border-white/10 rounded px-2 py-2 col-span-2"
        >
          <option value="">All makes</option>
          {makes.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <input
          name="year"
          defaultValue={sp.year ?? ""}
          placeholder="Year"
          inputMode="numeric"
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        />
        <input
          name="min"
          defaultValue={sp.min ?? ""}
          placeholder="Min ฿"
          inputMode="numeric"
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        />
        <input
          name="max"
          defaultValue={sp.max ?? ""}
          placeholder="Max ฿"
          inputMode="numeric"
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        />
        <select
          name="sort"
          defaultValue={sp.sort ?? "year_desc"}
          className="bg-white/5 border border-white/10 rounded px-2 py-2"
        >
          <option value="year_desc">Newest year</option>
          <option value="price_desc">Price ↓</option>
          <option value="price_asc">Price ↑</option>
          <option value="views_desc">Most viewed</option>
        </select>
        <input
          name="q"
          defaultValue={sp.q ?? ""}
          placeholder="Search title…"
          className="bg-white/5 border border-white/10 rounded px-2 py-2 col-span-3 md:col-span-5"
        />
        <button
          type="submit"
          className="bg-[#3ba3ff] hover:bg-[#3ba3ff]/85 rounded text-black font-medium"
        >
          Filter
        </button>
      </form>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.map((r) => {
          const cdHref = `https://www.taladrod.com/w40/iCar/CarDet.aspx?cid=${r.cid}`;
          const titleParts = [r.yr4, r.make_name, r.model_name].filter(Boolean);
          return (
            <a
              key={r.cid}
              href={cdHref}
              target="_blank"
              rel="noreferrer"
              className="group rounded-lg border border-white/5 bg-white/[0.02] hover:border-white/15 transition overflow-hidden"
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
                  <div className="font-medium text-white/90 truncate">
                    {titleParts.join(" ") || r.namemmt}
                  </div>
                  {r.ishot === "Y" && (
                    <span className="text-[10px] uppercase tracking-wide text-rose-300 bg-rose-500/15 px-1.5 py-0.5 rounded">
                      hot
                    </span>
                  )}
                </div>
                <div className="text-xs text-white/50 truncate mt-0.5">
                  {r.title || r.namemmt}
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <div className="text-lg font-semibold tabular-nums text-[#3ba3ff]">
                    {r.prc != null ? `฿${r.prc.toLocaleString()}` : "—"}
                  </div>
                  <div className="text-xs text-white/40">
                    {r.ipgvw != null ? `${r.ipgvw.toLocaleString()} views` : ""}
                  </div>
                </div>
                {r.prvprc && (
                  <div className="mt-1 text-xs text-emerald-400/80">
                    was ฿{r.prvprc} · {r.pcdisc != null ? `-${r.pcdisc}%` : ""}
                  </div>
                )}
              </div>
            </a>
          );
        })}
      </div>

      {rows.length === 0 && (
        <p className="text-white/40 text-sm">No matches.</p>
      )}

      <Pagination current={page} total={totalPages} sp={sp} />
    </div>
  );
}

function Pagination({
  current,
  total,
  sp,
}: {
  current: number;
  total: number;
  sp: SearchParams;
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
      <div className="text-white/40">
        page {current} / {total}
      </div>
      <div className="flex gap-2">
        {current > 1 && (
          <Link
            href={pageHref(current - 1)}
            className="px-3 py-1.5 border border-white/10 rounded hover:bg-white/5"
          >
            ← prev
          </Link>
        )}
        {current < total && (
          <Link
            href={pageHref(current + 1)}
            className="px-3 py-1.5 border border-white/10 rounded hover:bg-white/5"
          >
            next →
          </Link>
        )}
      </div>
    </div>
  );
}
