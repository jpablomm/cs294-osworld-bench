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
    const assessment = await getAssessment(assessment_id);
    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Initialize events array if it doesn't exist
    if (!assessment.events) {
      assessment.events = [];
    }

    // Store all events for educational transparency
    assessment.events.push(event);

    // Get event type (support both old "event_type" and new "type" fields)
    const eventType = event.event_type || event.type;

    // Update assessment based on event type (legacy format)
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

    // Handle new educational event types
    if (eventType === "tool_execution_complete") {
      // Track step number from tool executions
      if (event.step !== undefined) {
        assessment.steps = Math.max(assessment.steps || 0, event.step + 1);
      }
    } else if (eventType === "white_agent_completed") {
      // Update steps from white agent completion
      if (event.steps_taken !== undefined) {
        assessment.steps = event.steps_taken;
      }
    } else if (eventType === "evaluation_completed") {
      // Update evaluation results
      assessment.success = event.success ? 1 : 0;
      assessment.evaluation_score = event.evaluation_score;
      assessment.evaluation_method = "osworld_benchmark";
    } else if (eventType === "assessment_summary") {
      // Update final metrics
      assessment.success = event.success ? 1 : 0;
      assessment.steps = event.steps;
      assessment.time_sec = event.time_sec;
      assessment.vm_cost = event.vm_cost;
      assessment.evaluation_score = event.evaluation_score;
    } else if (eventType === "assessment_completed") {
      // Mark as completed
      assessment.status = event.success ? "completed" : "failed";
      assessment.completed_at = new Date().toISOString();
    }

    // Save updated assessment
    await saveAssessment(assessment);

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
