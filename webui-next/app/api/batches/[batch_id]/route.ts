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
    const assessments = await getBatchAssessments(batch_id);

    if (assessments.length === 0) {
      return NextResponse.json(
        { error: "Batch not found" },
        { status: 404 }
      );
    }

    // Calculate aggregate statistics (matching BatchResponse type)
    const completedAssessments = assessments.filter((a) => a.status === "completed");
    const completedCount = completedAssessments.length;
    const successCount = completedAssessments.filter((a) => a.success === true).length;

    const aggregate_stats = {
      success_rate: completedCount > 0 ? (successCount / completedCount) * 100 : 0,
      avg_steps: completedCount > 0
        ? completedAssessments.reduce((sum, a) => sum + (a.steps || 0), 0) / completedCount
        : 0,
      avg_time_sec: completedCount > 0
        ? completedAssessments.reduce((sum, a) => sum + (a.time_sec || 0), 0) / completedCount
        : 0,
      avg_evaluation_score: completedCount > 0
        ? completedAssessments.reduce((sum, a) => sum + (a.evaluation_score || 0), 0) / completedCount
        : null,
    };

    return NextResponse.json({
      batch_id,
      total_runs: assessments.length,
      completed_runs: completedCount,
      assessments,
      aggregate_stats,
    });
  } catch (error) {
    console.error("Error getting batch:", error);
    return NextResponse.json(
      { error: "Failed to get batch" },
      { status: 500 }
    );
  }
}
