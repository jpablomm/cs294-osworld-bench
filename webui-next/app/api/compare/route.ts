/**
 * Compare API endpoint
 * GET /api/compare?config1=hash&config2=hash - Compare two configurations
 */

import { NextRequest, NextResponse } from "next/server";
import { compareConfigs } from "@/lib/db/client";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const config1 = searchParams.get("config1");
    const config2 = searchParams.get("config2");

    if (!config1 || !config2) {
      return NextResponse.json(
        { error: "Missing required parameters: config1 and config2" },
        { status: 400 }
      );
    }

    if (config1 === config2) {
      return NextResponse.json(
        { error: "Cannot compare a config with itself" },
        { status: 400 }
      );
    }

    const comparison = await compareConfigs(config1, config2);

    return NextResponse.json(comparison);
  } catch (error) {
    console.error("Error comparing configs:", error);

    // Handle specific "not found" errors
    if (error instanceof Error && error.message.includes("not found")) {
      return NextResponse.json(
        { error: error.message },
        { status: 404 }
      );
    }

    return NextResponse.json(
      { error: "Failed to compare configs", details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
