/**
 * Server-Sent Events (SSE) stream for assessment updates
 * GET /api/stream/[assessment_id]
 */

import { NextRequest } from "next/server";
import { getAssessment } from "@/lib/db/client";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ assessment_id: string }> }
) {
  const { assessment_id } = await context.params;

  // Set up SSE headers
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        // Check if assessment exists
        const initialAssessment = await getAssessment(assessment_id);
        if (!initialAssessment) {
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ type: "error", error: "Assessment not found" })}\n\n`
            )
          );
          controller.close();
          return;
        }

        // Send initial status
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "status", data: initialAssessment })}\n\n`
          )
        );

        // Poll for updates every 2 seconds
        const intervalId = setInterval(async () => {
          const assessment = await getAssessment(assessment_id);
          if (!assessment) {
            clearInterval(intervalId);
            controller.close();
            return;
          }

          // Send update
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ type: "status", data: assessment })}\n\n`
            )
          );

          // Close stream if assessment is complete
          if (assessment.status === "completed" || assessment.status === "failed") {
            clearInterval(intervalId);
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ type: "complete", data: assessment })}\n\n`
              )
            );
            controller.close();
          }
        }, 2000);

        // Clean up on abort
        request.signal.addEventListener("abort", () => {
          clearInterval(intervalId);
          controller.close();
        });
      } catch (error) {
        console.error("SSE error:", error);
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ type: "error", error: String(error) })}\n\n`
          )
        );
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
