/**
 * Health check endpoint
 * GET /api/health
 */

import { NextResponse } from "next/server";
import { getDB } from "@/lib/db/client";
import { GREEN_AGENT_URL } from "@/lib/config";

export async function GET() {
  // Check database health
  let databaseHealthy = false;
  try {
    const db = getDB();
    const { error } = await db.from("assessments").select("id").limit(1);
    databaseHealthy = !error;
  } catch {
    databaseHealthy = false;
  }

  // Check Green Agent health
  let greenAgentHealthy = false;
  try {
    const response = await fetch(`${GREEN_AGENT_URL}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    greenAgentHealthy = response.ok;
  } catch {
    greenAgentHealthy = false;
  }

  return NextResponse.json({
    green_agent: { healthy: greenAgentHealthy },
    white_agent: { healthy: true }, // Not implemented yet
    database: { healthy: databaseHealthy },
  });
}
