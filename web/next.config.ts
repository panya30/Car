import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin Turbopack workspace root — X/ has no parent package.json,
  // otherwise Turbopack walks up to / and cold compiles are ~80x slower.
  turbopack: { root: __dirname },
  serverExternalPackages: ["better-sqlite3"],
  images: {
    remotePatterns: [{ protocol: "https", hostname: "imgc2.taladrod.com" }],
  },
};

export default nextConfig;
