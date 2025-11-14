/**
 * Single task endpoint
 * GET /api/tasks/[task_id]
 */

import { NextRequest, NextResponse } from "next/server";
import { getTaskById } from "@/lib/tasks";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ task_id: string }> }
) {
  try {
    const { task_id } = await context.params;
    const task = getTaskById(task_id);

    if (!task) {
      return NextResponse.json(
        { error: "Task not found" },
        { status: 404 }
      );
    }

    return NextResponse.json(task);
  } catch (error) {
    console.error("Error getting task:", error);
    return NextResponse.json(
      { error: "Failed to get task" },
      { status: 500 }
    );
  }
}
