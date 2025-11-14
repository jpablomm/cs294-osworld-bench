/**
 * Assessment tool executions endpoint
 * GET /api/assessments/[id]/tools
 *
 * Returns tool executions from the trajectory
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

    // Extract tool executions from trajectory
    const trajectory = assessment.trajectory || [];
    const tools = trajectory.filter((step: any) => step.action?.includes("tool"));

    return NextResponse.json(tools);
  } catch (error) {
    console.error("Error getting tools:", error);
    return NextResponse.json(
      { error: "Failed to get tools" },
      { status: 500 }
    );
  }
}
