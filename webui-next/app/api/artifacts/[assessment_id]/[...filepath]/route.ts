/**
 * Assessment artifacts endpoint
 * GET /api/artifacts/[assessment_id]/[...filepath]
 *
 * Serves artifacts (screenshots, recordings) from GCS bucket
 */

import { NextRequest, NextResponse } from "next/server";
import { Storage } from "@google-cloud/storage";
import { GCS_BUCKET_NAME } from "@/lib/config";

const storage = new Storage();

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ assessment_id: string; filepath: string[] }> }
) {
  try {
    const { assessment_id, filepath } = await context.params;
    const filePath = filepath.join("/");

    // Construct GCS path: gs://bucket/assessment_id/filepath
    const gcsPath = `${assessment_id}/${filePath}`;

    // Download file from GCS
    const bucket = storage.bucket(GCS_BUCKET_NAME);
    const file = bucket.file(gcsPath);

    // Check if file exists
    const [exists] = await file.exists();
    if (!exists) {
      return NextResponse.json(
        { error: "Artifact not found" },
        { status: 404 }
      );
    }

    // Stream file content
    const [fileBuffer] = await file.download();

    // Determine content type based on extension
    const ext = filePath.split(".").pop()?.toLowerCase();
    const contentTypeMap: Record<string, string> = {
      png: "image/png",
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      gif: "image/gif",
      webm: "video/webm",
      mp4: "video/mp4",
      json: "application/json",
      txt: "text/plain",
    };
    const contentType = contentTypeMap[ext || ""] || "application/octet-stream";

    return new NextResponse(fileBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch (error) {
    console.error("Error serving artifact:", error);
    return NextResponse.json(
      {
        error: "Failed to serve artifact",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
