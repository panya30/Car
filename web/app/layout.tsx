import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { getLocale, t, type Locale } from "@/lib/i18n";
import { totals, allSources } from "@/lib/db";
import "./globals.css";

export const metadata: Metadata = {
  title: "Car — Taladrod stats",
  description: "Refreshable view of Taladrod listings, scraped to SQLite.",
};

const SECTIONS = [
  {
    label_th: "เริ่มต้น",
    label_en: "Browse",
    items: [
      { href: "/", icon: "▦", key: "nav_overview" },
      { href: "/listings", icon: "▤", key: "nav_listings" },
    ],
  },
  {
    label_th: "ข้อมูลเชิงลึก",
    label_en: "Insights",
    items: [
      { href: "/stories", icon: "✦", key: "nav_stories" },
      { href: "/matches", icon: "⇆", key: "nav_matches" },
      { href: "/alerts", icon: "◉", key: "nav_alerts" },
    ],
  },
  {
    label_th: "ระบบ",
    label_en: "System",
    items: [{ href: "/runs", icon: "◷", key: "nav_runs" }],
  },
] as const;


export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const loc = await getLocale();
  const hdrs = await headers();
  const path = hdrs.get("x-pathname") ?? "/";

  // Sidebar counts (graceful zero if DB empty)
  let totalsData = { inLatest: 0 };
  let sources: { source: string; n: number }[] = [];
  try {
    totalsData = totals();
    sources = allSources();
  } catch {}

  return (
    <html lang={loc}>
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar
            loc={loc}
            currentPath={path}
            sources={sources}
            totalCars={totalsData.inLatest}
          />
          <div className="flex-1 flex flex-col min-w-0">
            <Toolbar loc={loc} currentPath={path} />
            <main className="flex-1 px-8 py-8 max-w-[1400px] w-full">
              {children}
            </main>
            <footer className="px-8 py-6 text-[11px] text-[color:var(--color-text-3)]">
              {t(loc, "footer_data")}{" "}
              <code className="text-[color:var(--color-text-2)]">
                python scraper.py
              </code>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}

function Sidebar({
  loc,
  currentPath,
  sources,
  totalCars,
}: {
  loc: Locale;
  currentPath: string;
  sources: { source: string; n: number }[];
  totalCars: number;
}) {
  return (
    <aside className="sidebar w-[230px] shrink-0 sticky top-0 h-screen overflow-y-auto py-3 hidden md:block">
      <div className="px-4 py-2 mb-2">
        <Link href="/" className="flex items-baseline gap-1.5">
          <span className="text-[15px] font-semibold tracking-tight text-[color:var(--color-text)]">
            Car
          </span>
          <span className="text-[11px] text-[color:var(--color-text-3)]">
            {t(loc, "brand_subtitle").replace("/ ", "")}
          </span>
        </Link>
        {totalCars > 0 && (
          <p className="text-[11px] text-[color:var(--color-text-3)] mt-0.5 tabular-nums">
            {totalCars.toLocaleString()} {t(loc, "listings_count_one")}
          </p>
        )}
      </div>

      {SECTIONS.map((section) => (
        <div key={section.label_en} className="mb-4">
          <div className="px-4 mb-1 text-[10px] font-semibold tracking-[0.08em] uppercase text-[color:var(--color-text-3)]">
            {loc === "th" ? section.label_th : section.label_en}
          </div>
          <nav>
            {section.items.map((item) => {
              const active =
                item.href === "/"
                  ? currentPath === "/"
                  : currentPath.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative flex items-center gap-2.5 mx-2 px-2.5 py-1.5 rounded-md text-[13px] transition-colors ${
                    active
                      ? "sidebar-item-active text-[color:var(--color-text)]"
                      : "text-[color:var(--color-text-2)] hover:text-[color:var(--color-text)] hover:bg-white/[0.035]"
                  }`}
                >
                  <span className="text-[color:var(--color-text-3)] w-4 text-center text-[11px]">
                    {item.icon}
                  </span>
                  <span className="font-medium">{t(loc, item.key)}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      ))}

      {sources.length > 0 && (
        <div className="mb-4">
          <div className="px-4 mb-1 text-[10px] font-semibold tracking-[0.08em] uppercase text-[color:var(--color-text-3)]">
            {loc === "th" ? "แหล่งข้อมูล" : "Sources"}
          </div>
          <nav>
            {sources.map((s) => (
              <Link
                key={s.source}
                href={`/listings?source=${encodeURIComponent(s.source)}`}
                className="flex items-center mx-2 px-2.5 py-1 rounded-md text-[12px] text-[color:var(--color-text-2)] hover:text-[color:var(--color-text)] hover:bg-white/[0.035]"
              >
                <span className="font-medium truncate">{s.source}</span>
                <span className="ml-auto tabular-nums text-[11px] text-[color:var(--color-text-3)]">
                  {s.n.toLocaleString()}
                </span>
              </Link>
            ))}
          </nav>
        </div>
      )}
    </aside>
  );
}

function Toolbar({ loc, currentPath }: { loc: Locale; currentPath: string }) {
  return (
    <div className="toolbar sticky top-0 z-10 px-8 h-12 flex items-center gap-3">
      <Breadcrumb loc={loc} path={currentPath} />
      <span className="ml-auto" />
      <LangSwitch loc={loc} />
    </div>
  );
}

function Breadcrumb({ loc, path }: { loc: Locale; path: string }) {
  const map: Record<string, string> = {
    "/":         t(loc, "nav_overview"),
    "/listings": t(loc, "nav_listings"),
    "/stories":  t(loc, "nav_stories"),
    "/matches":  t(loc, "nav_matches"),
    "/alerts":   t(loc, "nav_alerts"),
    "/runs":     t(loc, "nav_runs"),
  };
  const top = "/" + (path.split("/")[1] || "");
  const label = map[top] ?? map["/"];
  return (
    <div className="flex items-center gap-2 text-[13px]">
      <span className="text-[color:var(--color-text-3)]">Car</span>
      <span className="text-[color:var(--color-text-3)]">›</span>
      <span className="font-semibold text-[color:var(--color-text)]">{label}</span>
    </div>
  );
}

function LangSwitch({ loc }: { loc: Locale }) {
  return (
    <div className="segmented">
      <Link
        href="/api/lang/th"
        prefetch={false}
        className={loc === "th" ? "seg-active" : ""}
      >
        TH
      </Link>
      <Link
        href="/api/lang/en"
        prefetch={false}
        className={loc === "en" ? "seg-active" : ""}
      >
        EN
      </Link>
    </div>
  );
}
