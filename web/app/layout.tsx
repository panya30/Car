import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Car — Taladrod stats",
  description: "Refreshable view of Taladrod listings, scraped to SQLite.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-white/5 sticky top-0 z-10 backdrop-blur bg-[#0b0d10]/80">
          <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-1 text-sm">
            <Link href="/" className="font-semibold tracking-tight text-base mr-6">
              <span className="text-[#3ba3ff]">Car</span>
              <span className="text-white/50 font-normal ml-1.5">/ taladrod</span>
            </Link>
            <NavLink href="/">Overview</NavLink>
            <NavLink href="/listings">Listings</NavLink>
            <NavLink href="/stories">Stories</NavLink>
            <NavLink href="/matches">Matches</NavLink>
            <NavLink href="/alerts">Alerts</NavLink>
            <NavLink href="/runs">Runs</NavLink>
          </nav>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
        <footer className="max-w-7xl mx-auto px-6 py-10 text-xs text-white/30">
          data: SQLite snapshot · refresh: <code className="text-white/50">python scraper.py</code>
        </footer>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 rounded-md text-white/70 hover:text-white hover:bg-white/5 transition"
    >
      {children}
    </Link>
  );
}
