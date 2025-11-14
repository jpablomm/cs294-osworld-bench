/**
 * Aggregate statistics endpoint
 * GET /api/stats
 */

import { NextResponse } from "next/server";
import { getStats } from "@/lib/db/client";

export async function GET() {
  try {
    const stats = getStats();
    return NextResponse.json(stats);
  } catch (error) {
    console.error("Error getting stats:", error);
    return NextResponse.json(
      { error: "Failed to get stats" },
      { status: 500 }
    );
  }
}
