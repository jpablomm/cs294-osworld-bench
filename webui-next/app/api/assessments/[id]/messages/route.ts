/**
 * Assessment A2A messages endpoint
 * GET /api/assessments/[id]/messages
 *
 * Returns A2A protocol messages from the trajectory
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

    // Extract A2A messages from events
    const events = assessment.events || [];
    const messages: any[] = [];

    for (const event of events) {
      if (event.type === "message_sent" || event.type === "message_received") {
        const messageType = event.type === "message_sent"
          ? (event.direction === "green_to_white" ? "task" : "response")
          : "response";

        messages.push({
          id: `${event.step}_${event.type}_${event.timestamp}`,
          step: event.step,
          timestamp: event.timestamp,
          direction: event.direction,
          type: messageType,
          payload: event.payload || {},
          validation: event.validation || {
            valid: true,
            errors: [],
          },
          latency_ms: event.latency_ms || 0,
          role: event.direction?.includes("green") ? "green_agent" : "white_agent",
        });
      }
    }

    return NextResponse.json({ messages });
  } catch (error) {
    console.error("Error getting messages:", error);
    return NextResponse.json(
      { error: "Failed to get messages" },
      { status: 500 }
    );
  }
}
