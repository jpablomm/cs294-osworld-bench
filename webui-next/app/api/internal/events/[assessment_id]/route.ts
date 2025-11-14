/**
 * Internal event callback endpoint (for Green Agent to update assessment status)
 * POST /api/internal/events/[assessment_id]
 */

import { NextRequest, NextResponse } from "next/server";
import { getAssessment, saveAssessment } from "@/lib/db/client";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ assessment_id: string }> }
) {
  try {
    const { assessment_id } = await context.params;
    const event = await request.json();

    // Get current assessment
    const assessment = getAssessment(assessment_id);
    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Update assessment based on event type
    if (event.event_type === "step") {
      assessment.steps = event.data.step_number || assessment.steps;
      if (event.data.trajectory_step) {
        assessment.trajectory = assessment.trajectory || [];
        assessment.trajectory.push(event.data.trajectory_step);
      }
    } else if (event.event_type === "complete") {
      assessment.status = "completed";
      assessment.completed_at = new Date().toISOString();
      assessment.success = event.data.success || false;
      assessment.evaluation_score = event.data.evaluation_score;
      assessment.evaluation_method = event.data.evaluation_method;
      assessment.result = event.data.result;
      assessment.time_sec = event.data.time_sec;
      assessment.vm_cost = event.data.vm_cost;
      assessment.domain = event.data.domain;
    } else if (event.event_type === "error") {
      assessment.status = "failed";
      assessment.completed_at = new Date().toISOString();
      assessment.failure_reason = event.data.error || "Unknown error";
    }

    // Save updated assessment
    saveAssessment(assessment);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error handling event:", error);
    return NextResponse.json(
      {
        error: "Failed to handle event",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
