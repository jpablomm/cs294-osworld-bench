/**
 * Assessment evaluation details endpoint
 * GET /api/assessments/[id]/evaluation
 *
 * Returns detailed evaluation results
 */

import { NextRequest, NextResponse } from "next/server";
import { getAssessment } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    const assessment = getAssessment(id);

    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Return evaluation details
    return NextResponse.json({
      assessment_id: id,
      task_id: assessment.task_id,
      success: assessment.success,
      evaluation_score: assessment.evaluation_score,
      evaluation_method: assessment.evaluation_method,
      result: assessment.result,
      steps: assessment.steps,
      time_sec: assessment.time_sec,
      vm_cost: assessment.vm_cost,
    });
  } catch (error) {
    console.error("Error getting evaluation:", error);
    return NextResponse.json(
      { error: "Failed to get evaluation" },
      { status: 500 }
    );
  }
}
