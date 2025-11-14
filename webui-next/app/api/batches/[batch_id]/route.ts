/**
 * Batch assessments endpoint
 * GET /api/batches/[batch_id]
 */

import { NextRequest, NextResponse } from "next/server";
import { getBatchAssessments } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ batch_id: string }> }
) {
  try {
    const { batch_id } = await context.params;
    const assessments = getBatchAssessments(batch_id);

    if (assessments.length === 0) {
      return NextResponse.json(
        { error: "Batch not found" },
        { status: 404 }
      );
    }

    // Calculate summary statistics
    const summary = {
      total_runs: assessments.length,
      completed: assessments.filter((a) => a.status === "completed").length,
      running: assessments.filter((a) => a.status === "running").length,
      failed: assessments.filter((a) => a.status === "failed").length,
      success_rate:
        assessments.filter((a) => a.success === true).length /
        assessments.filter((a) => a.status === "completed").length *
        100 || 0,
    };

    return NextResponse.json({
      batch_id,
      assessments,
      summary,
    });
  } catch (error) {
    console.error("Error getting batch:", error);
    return NextResponse.json(
      { error: "Failed to get batch" },
      { status: 500 }
    );
  }
}
