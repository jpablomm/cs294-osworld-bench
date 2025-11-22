/**
 * Health check endpoint
 * GET /api/health
 */

import { NextResponse } from "next/server";
import { getDB } from "@/lib/db/client";
import { GREEN_AGENT_URL, WHITE_AGENT_URL } from "@/lib/config";

export async function GET() {
  // Check database health
  let databaseHealthy = false;
  let databaseError = "";
  try {
    const db = getDB();
    const { error } = await db.from("assessments").select("id").limit(1);
    databaseHealthy = !error;
    if (error) {
      databaseError = error.message;
    }
  } catch (err) {
    databaseHealthy = false;
    databaseError = err instanceof Error ? err.message : "Connection failed";
  }

  // Check Green Agent health
  let greenAgentHealthy = false;
  let greenAgentError = "";
  try {
    const response = await fetch(`${GREEN_AGENT_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    greenAgentHealthy = response.ok;
    if (!response.ok) {
      greenAgentError = `HTTP ${response.status}`;
    }
  } catch (err) {
    greenAgentHealthy = false;
    greenAgentError = err instanceof Error ? err.message : "Connection failed";
  }

  // Check White Agent health
  let whiteAgentHealthy = false;
  let whiteAgentError = "";
  try {
    const response = await fetch(`${WHITE_AGENT_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    whiteAgentHealthy = response.ok;
    if (!response.ok) {
      whiteAgentError = `HTTP ${response.status}`;
    }
  } catch (err) {
    whiteAgentHealthy = false;
    whiteAgentError = err instanceof Error ? err.message : "Connection failed";
  }

  return NextResponse.json({
    green_agent: { healthy: greenAgentHealthy, error: greenAgentError || undefined },
    white_agent: { healthy: whiteAgentHealthy, error: whiteAgentError || undefined },
    database: { healthy: databaseHealthy, error: databaseError || undefined },
  });
}
