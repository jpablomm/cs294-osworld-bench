/**
 * Tasks list endpoint
 * GET /api/tasks
 */

import { NextRequest, NextResponse } from "next/server";
import { loadTasks } from "@/lib/tasks";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const domain = searchParams.get("domain");

    let tasks = await loadTasks();

    // Filter by domain if specified
    if (domain) {
      tasks = tasks.filter((t) => t.domain === domain);
    }

    return NextResponse.json(tasks);
  } catch (error) {
    console.error("Error loading tasks:", error);
    return NextResponse.json(
      {
        error: "Failed to load tasks",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
