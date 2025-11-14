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
    const assessment = getAssessment(id);

    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Return current state (last step of trajectory)
    const trajectory = assessment.trajectory || [];
    const latestState = trajectory.length > 0 ? trajectory[trajectory.length - 1] : null;

    return NextResponse.json({
      assessment_id: id,
      status: assessment.status,
      steps: assessment.steps,
      latest_state: latestState,
      trajectory_length: trajectory.length,
    });
  } catch (error) {
    console.error("Error getting agent state:", error);
    return NextResponse.json(
      { error: "Failed to get agent state" },
      { status: 500 }
    );
  }
}
