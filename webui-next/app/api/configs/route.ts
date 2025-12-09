/**
 * Configs API endpoint
 * GET /api/configs - List all unique agent configurations with stats
 */

import { NextRequest, NextResponse } from "next/server";
import { getAllConfigs } from "@/lib/db/client";

export async function GET(request: NextRequest) {
  try {
    const configs = await getAllConfigs();

    return NextResponse.json({
      configs,
      total: configs.length,
    });
  } catch (error) {
    console.error("Error fetching configs:", error);
    return NextResponse.json(
      { error: "Failed to fetch configs", details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
