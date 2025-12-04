/**
 * Task statistics endpoint
 * GET /api/tasks/[task_id]/stats
 */

import { NextRequest, NextResponse } from "next/server";
import { getTaskStatistics } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ task_id: string }> }
) {
  try {
    const { task_id } = await context.params;
    const stats = await getTaskStatistics(task_id);

    return NextResponse.json(stats);
  } catch (error) {
    console.error("Error getting task stats:", error);
    return NextResponse.json(
      { error: "Failed to get task stats" },
      { status: 500 }
    );
  }
}
