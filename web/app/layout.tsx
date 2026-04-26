import type { Metadata } from "next";
import Link from "next/link";
import { getLocale, t, type Locale } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Car — Taladrod stats",
  description: "Refreshable view of Taladrod listings, scraped to SQLite.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const loc = await getLocale();
  return (
    <html lang={loc}>
      <body className="min-h-screen">
        <header className="border-b border-white/5 sticky top-0 z-10 backdrop-blur bg-[#0b0d10]/80">
          <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-1 text-sm">
            <Link
              href="/"
              className="font-semibold tracking-tight text-base mr-6"
            >
              <span className="text-[#3ba3ff]">Car</span>
              <span className="text-white/50 font-normal ml-1.5">
                {t(loc, "brand_subtitle")}
              </span>
            </Link>
            <NavLink href="/">{t(loc, "nav_overview")}</NavLink>
            <NavLink href="/listings">{t(loc, "nav_listings")}</NavLink>
            <NavLink href="/stories">{t(loc, "nav_stories")}</NavLink>
            <NavLink href="/matches">{t(loc, "nav_matches")}</NavLink>
            <NavLink href="/alerts">{t(loc, "nav_alerts")}</NavLink>
            <NavLink href="/runs">{t(loc, "nav_runs")}</NavLink>
            <span className="ml-auto" />
            <LangSwitch loc={loc} />
          </nav>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
        <footer className="max-w-7xl mx-auto px-6 py-10 text-xs text-white/30">
          {t(loc, "footer_data")}{" "}
          <code className="text-white/50">python scraper.py</code>
        </footer>
      </body>
    </html>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition"
    >
      {children}
    </Link>
  );
}

function LangSwitch({ loc }: { loc: Locale }) {
  const cls = (active: boolean) =>
    `px-2 py-1 text-xs font-mono uppercase tracking-wider rounded transition ${
      active
        ? "bg-[#3ba3ff]/20 text-[#9ed1ff]"
        : "text-white/40 hover:text-white/70 hover:bg-white/5"
    }`;
  return (
    <div className="flex items-center gap-0.5 border border-white/10 rounded p-0.5">
      <Link href="/api/lang/th" prefetch={false} className={cls(loc === "th")}>
        TH
      </Link>
      <Link href="/api/lang/en" prefetch={false} className={cls(loc === "en")}>
        EN
      </Link>
    </div>
  );
}
