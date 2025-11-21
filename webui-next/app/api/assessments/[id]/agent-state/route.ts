/**
 * Assessment agent state endpoint
 * GET /api/assessments/[id]/agent-state
 *
 * Returns the current agent state from trajectory
 */

import { NextRequest, NextResponse } from "next/server";
import { getAssessment } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    const assessment = await getAssessment(id);

    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Get educational events for transparency
    const events = assessment.events || [];
    const latestEvent = events.length > 0 ? events[events.length - 1] : null;

    // Extract agent states from events
    let greenAgentStatus = "idle";
    let whiteAgentStatus = "idle";
    let currentStep = 0;
    let totalSteps = 20; // Default
    const toolsUsed = new Set<string>();

    // Parse events to determine current agent states
    for (const event of events) {
      if (event.type === "green_agent_step" || event.type === "step") {
        greenAgentStatus = "processing";
        if (event.data?.step !== undefined) {
          currentStep = event.data.step;
        }
        if (event.data?.total_steps !== undefined) {
          totalSteps = event.data.total_steps;
        }
      } else if (event.type === "white_agent_action" || event.type === "action") {
        whiteAgentStatus = "processing";
        if (event.data?.action) {
          toolsUsed.add(event.data.action);
        }
      } else if (event.type === "completed") {
        greenAgentStatus = "idle";
        whiteAgentStatus = "idle";
      }
    }

    // If assessment is completed or failed, both agents are idle
    if (assessment.status === "completed" || assessment.status === "failed") {
      greenAgentStatus = "idle";
      whiteAgentStatus = "idle";
    } else if (assessment.status === "running") {
      // If running but no recent events, assume green agent is processing
      if (greenAgentStatus === "idle") {
        greenAgentStatus = "processing";
      }
    }

    return NextResponse.json({
      assessment_id: id,
      status: assessment.status,
      green_agent: {
        status: greenAgentStatus,
        step: currentStep,
        total_steps: totalSteps,
        latest_message: latestEvent?.message || null,
      },
      white_agent: {
        status: whiteAgentStatus,
        tools_used: Array.from(toolsUsed),
      },
      events: events,
      latest_event: latestEvent,
      event_count: events.length,
    });
  } catch (error) {
    console.error("Error getting agent state:", error);
    return NextResponse.json(
      { error: "Failed to get agent state" },
      { status: 500 }
    );
  }
}
