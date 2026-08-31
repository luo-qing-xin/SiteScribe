import type { NextConfig } from "next";

// Keep API traffic same-origin in the browser. This avoids CORS/cookie failures
// when the frontend is opened through 127.0.0.1, a LAN address, or a preview URL.
const backendUrl = (
  process.env.BACKEND_URL ??
  // Backward compatibility for existing local frontend/.env.local files.
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
