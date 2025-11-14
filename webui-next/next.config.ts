import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */

  // Proxy /api/* requests to FastAPI backend
  // In production (Cloud Run), FastAPI runs on localhost:8081
  // This allows external clients to hit /api/* on the same port as Next.js (8080)
  async rewrites() {
    const backendPort = process.env.BACKEND_PORT || '8081';
    const backendUrl = process.env.BACKEND_URL || `http://localhost:${backendPort}`;

    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
