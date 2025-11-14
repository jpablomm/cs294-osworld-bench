/**
 * Unified leaderboard endpoint (redirects to global)
 * GET /api/leaderboard
 */

import { NextRequest, NextResponse } from "next/server";
import { getGlobalLeaderboard } from "@/lib/db/client";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;

    const metric = searchParams.get("metric") || "success_rate";
    const limit = parseInt(searchParams.get("limit") || "50");
    const domain = searchParams.get("domain") || undefined;

    const leaderboard = getGlobalLeaderboard(metric, limit, domain);
    return NextResponse.json(leaderboard);
  } catch (error) {
    console.error("Error getting leaderboard:", error);
    return NextResponse.json(
      {
        error: "Failed to get leaderboard",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
