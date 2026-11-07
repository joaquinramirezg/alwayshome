import type { NextConfig } from "next";

// The browser calls /api/* on this site; Next.js forwards it to the Python API.
// Locally the API runs on :8000. On Vercel, set API_URL to the hosted API (e.g. https://alwayson-api.onrender.com).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
