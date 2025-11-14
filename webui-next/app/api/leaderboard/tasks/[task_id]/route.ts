/**
 * Task-specific leaderboard endpoint
 * GET /api/leaderboard/tasks/[task_id]
 */

import { NextRequest, NextResponse } from "next/server";
import { getTaskLeaderboard } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ task_id: string }> }
) {
  try {
    const { task_id } = await context.params;
    const { searchParams } = request.nextUrl;

    const metric = searchParams.get("metric") || "success_rate";
    const limit = parseInt(searchParams.get("limit") || "50");

    const leaderboard = getTaskLeaderboard(task_id, metric, limit);
    return NextResponse.json(leaderboard);
  } catch (error) {
    console.error("Error getting task leaderboard:", error);
    return NextResponse.json(
      {
        error: "Failed to get task leaderboard",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
