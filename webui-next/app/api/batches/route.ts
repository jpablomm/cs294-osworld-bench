/**
 * Batches listing endpoint
 * GET /api/batches - List all batches with summary statistics
 */

import { NextRequest, NextResponse } from "next/server";
import { listBatches } from "@/lib/db/client";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;

    const params = {
      limit: parseInt(searchParams.get("limit") || "50"),
      offset: parseInt(searchParams.get("offset") || "0"),
      status: searchParams.get("status") || undefined,
    };

    const result = await listBatches(params);

    return NextResponse.json(result);
  } catch (error) {
    console.error("Error listing batches:", error);
    return NextResponse.json(
      { error: "Failed to list batches" },
      { status: 500 }
    );
  }
}
