/**
 * Assessments endpoints
 * GET  /api/assessments - List assessments with filtering
 * POST /api/assessments - Launch new assessment
 */

import { NextRequest, NextResponse } from "next/server";
import { listAssessments, saveAssessment } from "@/lib/db/client";
import { GREEN_AGENT_URL, GREEN_AGENT_API_KEY } from "@/lib/config";
import type { LaunchAssessmentRequest } from "@/lib/types";

/**
 * GET /api/assessments
 * List assessments with optional filtering
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;

    const params = {
      limit: parseInt(searchParams.get("limit") || "100"),
      offset: parseInt(searchParams.get("offset") || "0"),
      status: searchParams.get("status") || undefined,
      domain: searchParams.get("domain") || undefined,
      task_id: searchParams.get("task_id") || undefined,
    };

    const assessments = await listAssessments(params);
    return NextResponse.json(assessments);
  } catch (error) {
    console.error("Error listing assessments:", error);
    return NextResponse.json(
      { error: "Failed to list assessments" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/assessments
 * Launch new assessment
 */
export async function POST(request: NextRequest) {
  try {
    const body: LaunchAssessmentRequest = await request.json();

    // Generate assessment ID
    const assessmentId = `assessment_${Date.now()}_${Math.random().toString(36).substring(7)}`;

    // Create initial assessment record
    const assessment = {
      id: assessmentId,
      task_id: body.task_id,
      status: "running" as const,
      started_at: new Date().toISOString(),
      completed_at: null,
      steps: 0,
      success: null,
      config: body.agent_config,
      run_number: body.run_number || 1,
      batch_id: body.batch_id || null,
      domain: null,
      evaluation_score: null,
      evaluation_method: null,
      failure_reason: null,
      time_sec: null,
      vm_cost: null,
      result: null,
      trajectory: null,
    };

    // Save to database
    await saveAssessment(assessment);

    // Launch assessment on Green Agent using A2A protocol
    // The Green Agent expects the A2A task format
    const a2aTask = {
      task_id: assessmentId,
      message: `Launch OSWorld assessment for task ${body.task_id}`,
      metadata: {
        osworld_task_id: body.task_id,
        white_agent_url: body.agent_config?.white_agent_url || "http://localhost:9002",
        callback_url: `${process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"}/api/internal/events/${assessmentId}`,
        config: body.agent_config,
      },
    };

    const greenAgentResponse = await fetch(`${GREEN_AGENT_URL}/task`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": GREEN_AGENT_API_KEY,
      },
      body: JSON.stringify(a2aTask),
    });

    if (!greenAgentResponse.ok) {
      const errorText = await greenAgentResponse.text();
      throw new Error(`Green Agent failed: ${errorText}`);
    }

    return NextResponse.json({
      assessment_id: assessmentId,
      status: "running",
      message: "Assessment launched successfully",
    });
  } catch (error) {
    console.error("Error launching assessment:", error);
    return NextResponse.json(
      {
        error: "Failed to launch assessment",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
