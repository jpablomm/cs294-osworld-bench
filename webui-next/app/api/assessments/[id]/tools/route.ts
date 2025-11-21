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
    const assessment = await getAssessment(id);

    if (!assessment) {
      return NextResponse.json(
        { error: "Assessment not found" },
        { status: 404 }
      );
    }

    // Extract tool executions from events
    const events = assessment.events || [];
    const executions: any[] = [];
    const toolMap = new Map<string, any>();

    for (const event of events) {
      if (event.type === "tool_execution_start") {
        const key = `${event.step}_${event.tool}`;
        toolMap.set(key, {
          step: event.step,
          tool: event.tool,
          parameters: event.parameters,
          start_timestamp: event.timestamp,
          status: "running",
        });
      } else if (event.type === "tool_execution_complete") {
        const key = `${event.step}_${event.tool}`;
        const execution = toolMap.get(key);
        if (execution) {
          execution.status = event.status;
          execution.end_timestamp = event.timestamp;
          execution.duration_ms = event.duration_ms;
          execution.result = event.result;
          execution.screenshot_before = event.screenshot_before;
          execution.screenshot_after = event.screenshot_after;
          execution.timestamp = event.timestamp;
          executions.push(execution);
          toolMap.delete(key);
        } else {
          // Tool complete without start event
          executions.push({
            step: event.step,
            tool: event.tool,
            status: event.status,
            end_timestamp: event.timestamp,
            duration_ms: event.duration_ms,
            result: event.result,
            screenshot_before: event.screenshot_before,
            screenshot_after: event.screenshot_after,
            timestamp: event.timestamp,
          });
        }
      }
    }

    // Add any tools that started but haven't completed yet
    for (const execution of toolMap.values()) {
      executions.push(execution);
    }

    // Sort by step
    executions.sort((a, b) => (a.step || 0) - (b.step || 0));

    return NextResponse.json({ executions });
  } catch (error) {
    console.error("Error getting tools:", error);
    return NextResponse.json(
      { error: "Failed to get tools" },
      { status: 500 }
    );
  }
}
