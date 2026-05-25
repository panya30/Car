import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { getLocale, t, type Locale } from "@/lib/i18n";
import { getTheme, type Theme } from "@/lib/theme";
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
  const theme = await getTheme();
  const hdrs = await headers();
  const path = hdrs.get("x-pathname") ?? "/";

  let totalsData = { inLatest: 0 };
  let sources: { source: string; n: number }[] = [];
  try {
    totalsData = totals();
    sources = allSources();
  } catch {}

  return (
    <html lang={loc} data-theme={theme}>
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar
            loc={loc}
            currentPath={path}
            sources={sources}
            totalCars={totalsData.inLatest}
          />
          <div className="flex-1 flex flex-col min-w-0">
            <Toolbar loc={loc} theme={theme} currentPath={path} />
            <main className="flex-1 px-10 py-10 max-w-[1320px] w-full">
              {children}
            </main>
            <footer className="px-10 py-8 text-[11px] text-fg-3">
              {t(loc, "footer_data")}{" "}
              <code className="text-fg-2 font-mono text-[10px]">
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
    <aside className="sidebar w-[230px] shrink-0 sticky top-0 h-screen overflow-y-auto py-4 hidden md:block">
      <div className="px-5 py-2 mb-3">
        <Link href="/" className="block">
          <div className="text-[15px] font-semibold tracking-tight text-fg"
               style={{ fontFamily: "var(--font-display)" }}>
            Car
          </div>
          <div className="text-[11px] text-fg-3 mt-0.5">
            {t(loc, "brand_subtitle").replace("/ ", "")}
            {totalCars > 0 && (
              <span className="tabular-nums">
                {" · "}
                {totalCars.toLocaleString()} {t(loc, "listings_count_one")}
              </span>
            )}
          </div>
        </Link>
      </div>

      {SECTIONS.map((section) => (
        <div key={section.label_en} className="mb-5">
          <div className="px-5 mb-1 text-[10px] font-semibold tracking-[0.06em] uppercase text-fg-3">
            {loc === "th" ? section.label_th : section.label_en}
          </div>
          <nav className="px-2">
            {section.items.map((item) => {
              const active =
                item.href === "/"
                  ? currentPath === "/"
                  : currentPath.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2.5 px-3 py-1.5 rounded-md text-[13px] transition-colors ${
                    active
                      ? "sidebar-item-active text-fg"
                      : "text-fg-2 hover:text-fg hover:bg-surface"
                  }`}
                >
                  <span className="w-4 text-center text-[11px] text-fg-3">
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
        <div className="mb-5">
          <div className="px-5 mb-1 text-[10px] font-semibold tracking-[0.06em] uppercase text-fg-3">
            {loc === "th" ? "แหล่งข้อมูล" : "Sources"}
          </div>
          <nav className="px-2">
            {sources.map((s) => (
              <Link
                key={s.source}
                href={`/listings?source=${encodeURIComponent(s.source)}`}
                className="flex items-center px-3 py-1 rounded-md text-[12px] text-fg-2 hover:text-fg hover:bg-surface"
              >
                <span className="font-medium truncate">{s.source}</span>
                <span className="ml-auto tabular-nums text-[11px] text-fg-3">
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

function Toolbar({
  loc,
  theme,
  currentPath,
}: {
  loc: Locale;
  theme: Theme;
  currentPath: string;
}) {
  return (
    <div className="toolbar sticky top-0 z-10 px-10 h-12 flex items-center gap-3">
      <Breadcrumb loc={loc} path={currentPath} />
      <span className="ml-auto" />
      <ThemeSwitch theme={theme} />
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
      <span className="text-fg-3">Car</span>
      <span className="text-fg-3">›</span>
      <span className="font-semibold text-fg">{label}</span>
    </div>
  );
}

function ThemeSwitch({ theme }: { theme: Theme }) {
  return (
    <div className="segmented">
      <Link
        href="/api/theme/light"
        prefetch={false}
        className={theme === "light" ? "seg-active" : ""}
        title="Light"
      >
        ☀
      </Link>
      <Link
        href="/api/theme/dark"
        prefetch={false}
        className={theme === "dark" ? "seg-active" : ""}
        title="Dark"
      >
        ☾
      </Link>
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
