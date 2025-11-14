/**
 * Available metrics endpoint
 * GET /api/metrics
 */

import { NextResponse } from "next/server";
import { getAvailableMetrics } from "@/lib/db/client";

export async function GET() {
  try {
    const metrics = getAvailableMetrics();
    return NextResponse.json(metrics);
  } catch (error) {
    console.error("Error getting metrics:", error);
    return NextResponse.json(
      { error: "Failed to get metrics" },
      { status: 500 }
    );
  }
}
