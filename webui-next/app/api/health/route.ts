/**
 * Health check endpoint
 * GET /api/health
 */

import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "healthy",
    service: "osworld-webui",
    timestamp: new Date().toISOString(),
  });
}
