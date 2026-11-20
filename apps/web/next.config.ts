import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
        { key: "Cache-Control", value: "private, no-store, max-age=0" }
      ]
    }];
  },
  async rewrites() {
    // Preserve existing macOS clients using /api/v1/* after the host moves to Vercel.
    // The separate backend alias still requires its own strong bearer on all private routes.
    if (!process.env.DAEDALUS_LEGACY_API_ORIGIN) return [];
    return [{
      source: "/api/v1/:path*",
      destination: process.env.DAEDALUS_LEGACY_API_ORIGIN + "/api/v1/:path*"
    }];
  }
};
export default nextConfig;
