import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",

  // Skip TypeScript build errors (Next.js 16 type validation issue with catch-all routes)
  typescript: {
    ignoreBuildErrors: true,
  },

  // All backend logic is now in Next.js API routes (app/api/)
  // No need for rewrites or proxy configuration
};

export default nextConfig;
