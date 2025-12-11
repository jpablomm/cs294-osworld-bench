/**
 * Assessments endpoints
 * GET  /api/assessments - List assessments with filtering
 * POST /api/assessments - Launch new assessment(s) - supports multi-task
 */

import { NextRequest, NextResponse } from "next/server";
import { listAssessments, saveAssessment, getDB } from "@/lib/db/client";
import { GREEN_AGENT_URL, GREEN_AGENT_API_KEY, WHITE_AGENT_URL } from "@/lib/config";
import type { LaunchAssessmentRequest } from "@/lib/types";

const MAX_TASKS_PER_BATCH = 20;

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
    return NextResponse.json({
      assessments,
      limit: params.limit,
      offset: params.offset,
    });
  } catch (error) {
    console.error("Error listing assessments:", error);
    return NextResponse.json(
      { error: "Failed to list assessments" },
      { status: 500 }
    );
  }
}

/**
 * Launch a single task to the Green Agent
 */
async function launchTaskToGreenAgent(
  task: any,
  assessmentId: string,
  agentConfig: any
): Promise<void> {
  const a2aRequest = {
    jsonrpc: "2.0",
    id: assessmentId,
    method: "message/send",
    params: {
      message: {
        role: "user",
        parts: [
          {
            type: "text",
            text: `Launch OSWorld assessment for task ${task.source_id || task.id}`,
          },
        ],
        messageId: assessmentId,
      },
      configuration: {
        blocking: false,  // Return immediately, don't wait for task completion
      },
      metadata: {
        osworld_task_id: task.source_id || task.id,
        osworld_task: {
          id: task.source_id || task.id,
          instruction: task.instruction,
          config: task.config,
          evaluator: task.evaluator,
        },
        white_agent_url: agentConfig?.white_agent_url || WHITE_AGENT_URL,
        callback_url: `${process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"}/api/internal/events/${assessmentId}`,
        agent_config: agentConfig,  // Renamed from 'config' to avoid collision with executor's config parsing
      },
    },
  };

  // Fire-and-forget: Send the request but don't wait for the response
  // The A2A server may not support non-blocking mode, so we just fire the request
  // and let the callback_url handle status updates
  fetch(`${GREEN_AGENT_URL}/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": GREEN_AGENT_API_KEY,
    },
    body: JSON.stringify(a2aRequest),
  }).catch((error) => {
    console.error(`Green Agent request failed for ${assessmentId}:`, error.message);
  });
}

/**
 * POST /api/assessments
 * Launch new assessment(s) - supports both single task and multi-task
 */
export async function POST(request: NextRequest) {
  try {
    const body: LaunchAssessmentRequest = await request.json();

    // Normalize to array (backward compatible)
    const taskIds = body.task_ids || (body.task_id ? [body.task_id] : []);

    if (taskIds.length === 0) {
      return NextResponse.json(
        { error: "No tasks specified", details: "Provide task_id or task_ids" },
        { status: 400 }
      );
    }

    if (taskIds.length > MAX_TASKS_PER_BATCH) {
      return NextResponse.json(
        { error: `Maximum ${MAX_TASKS_PER_BATCH} tasks allowed per batch` },
        { status: 400 }
      );
    }

    // Look up all tasks from Supabase
    const db = getDB();
    const { data: tasks, error: taskError } = await db
      .from("tasks")
      .select("*")
      .in("id", taskIds);

    if (taskError) {
      return NextResponse.json(
        { error: "Failed to fetch tasks", details: taskError.message },
        { status: 500 }
      );
    }

    if (!tasks || tasks.length === 0) {
      return NextResponse.json(
        { error: "No tasks found", details: `Tasks ${taskIds.join(", ")} not found in database` },
        { status: 404 }
      );
    }

    // Check for missing tasks
    const foundIds = new Set(tasks.map((t: any) => t.id));
    const missingIds = taskIds.filter((id) => !foundIds.has(id));
    if (missingIds.length > 0) {
      return NextResponse.json(
        { error: "Some tasks not found", details: `Missing tasks: ${missingIds.join(", ")}` },
        { status: 404 }
      );
    }

    // Generate batch ID
    const batchId = body.batch_id || `batch_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;

    // Build agent config from request (support both flat params and nested agent_config)
    const agentConfig = body.agent_config || {
      agent_name: "white_agent",
      model: (body as any).model || "gpt-4o",
      max_steps: (body as any).max_steps || 15,
      white_agent_url: (body as any).white_agent_url || WHITE_AGENT_URL,
      vm_image: (body as any).vm_image || "osworld-gnome-v6",
    };

    const assessmentIds: string[] = [];
    const failedTasks: { task_id: string; error: string }[] = [];

    // Create assessment for each task
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const assessmentId = `assessment_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

      try {
        // Create initial assessment record
        const assessment = {
          id: assessmentId,
          task_id: task.id,
          status: "running" as const,
          started_at: new Date().toISOString(),
          completed_at: null,
          steps: 0,
          success: null,
          config: agentConfig,
          run_number: i + 1,
          batch_id: batchId,
          domain: task.domain || null,
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

        // Launch to Green Agent
        await launchTaskToGreenAgent(task, assessmentId, agentConfig);

        assessmentIds.push(assessmentId);
      } catch (error) {
        console.error(`Failed to launch task ${task.id}:`, error);
        failedTasks.push({
          task_id: task.id,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    // Determine overall status
    let status: "launched" | "partial" | "failed";
    if (assessmentIds.length === 0) {
      status = "failed";
    } else if (failedTasks.length > 0) {
      status = "partial";
    } else {
      status = "launched";
    }

    // Build response
    const response: any = {
      batch_id: batchId,
      assessment_ids: assessmentIds,
      status,
      monitor_url: `/batch/${batchId}`,
    };

    // Backward compatibility: include assessment_id for single task
    if (assessmentIds.length === 1 && taskIds.length === 1) {
      response.assessment_id = assessmentIds[0];
    }

    // Include failed tasks info if any
    if (failedTasks.length > 0) {
      response.failed_tasks = failedTasks;
    }

    // Return appropriate status code
    if (status === "failed") {
      return NextResponse.json(
        { ...response, error: "All tasks failed to launch" },
        { status: 500 }
      );
    }

    return NextResponse.json(response);
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
