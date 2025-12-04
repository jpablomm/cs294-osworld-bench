/**
 * Assessment agent state endpoint
 * GET /api/assessments/[id]/agent-state
 *
 * Returns the current agent state extracted from real event data
 */

import { NextRequest, NextResponse } from "next/server";
import { getAssessment } from "@/lib/db/client";

// VM lifecycle stages for progress tracking
type VMStage = "pending" | "creating" | "booting" | "ready" | "cleanup" | "done";

interface VMProgress {
  stage: VMStage;
  vm_name?: string;
  vm_ip?: string;
  vm_image?: string;
  message?: string;
}

interface SetupProgress {
  started: boolean;
  completed: boolean;
  num_steps?: number;
  message?: string;
}

interface EvaluationProgress {
  started: boolean;
  completed: boolean;
  success?: boolean;
  score?: number;
  message?: string;
}

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

    const events = assessment.events || [];
    const latestEvent = events.length > 0 ? events[events.length - 1] : null;

    // Extract comprehensive state from events
    let greenAgentStatus = "idle";
    let whiteAgentStatus = "idle";
    let currentStep = 0;
    let maxSteps = 15; // Default, will be overwritten from events
    const toolsUsed = new Set<string>();
    let taskInstruction = "";
    let whiteAgentUrl = "";
    let latestMessage = "";
    let currentAction = "";
    let messageCount = 0;
    let thinkingTimeMs = 0;

    // VM progress tracking
    const vmProgress: VMProgress = { stage: "pending" };

    // Setup progress tracking
    const setupProgress: SetupProgress = { started: false, completed: false };

    // Evaluation progress tracking
    const evaluationProgress: EvaluationProgress = { started: false, completed: false };

    // Parse ALL events to build comprehensive state
    for (const event of events) {
      const eventType = event.type || event.event_type;

      // VM lifecycle events
      if (eventType === "vm_creation_started") {
        vmProgress.stage = "creating";
        vmProgress.vm_image = event.vm_image;
        vmProgress.message = "Creating VM from golden image...";
      } else if (eventType === "vm_created") {
        vmProgress.stage = "booting";
        vmProgress.vm_name = event.vm_name;
        vmProgress.vm_ip = event.vm_ip;
        vmProgress.message = "VM created, waiting for boot...";
      } else if (eventType === "vm_waiting") {
        vmProgress.stage = "booting";
        vmProgress.message = event.message || "Waiting for VM to boot...";
      } else if (eventType === "vm_ready") {
        vmProgress.stage = "ready";
        vmProgress.vm_ip = event.vm_ip;
        vmProgress.message = event.message || "VM ready";
      } else if (eventType === "vm_cleanup_started") {
        vmProgress.stage = "cleanup";
        vmProgress.message = event.message || "Cleaning up VM...";
      }

      // Setup events
      else if (eventType === "setup_started") {
        setupProgress.started = true;
        setupProgress.num_steps = event.num_steps;
        setupProgress.message = event.message || `Running ${event.num_steps} setup steps...`;
        greenAgentStatus = "setting_up";
        // Update VM progress to reflect we're past the VM ready stage
        if (vmProgress.stage === "ready" || vmProgress.stage === "booting") {
          vmProgress.stage = "ready"; // Keep as ready, setup is tracked separately
        }
      } else if (eventType === "setup_completed") {
        setupProgress.completed = true;
        setupProgress.message = event.message || "Setup complete";
        greenAgentStatus = "setup_complete";
      }

      // White agent lifecycle
      else if (eventType === "white_agent_started") {
        whiteAgentUrl = event.white_agent_url || "";
        taskInstruction = event.task_instruction || "";
        maxSteps = event.max_steps || maxSteps;
        greenAgentStatus = "orchestrating";
        whiteAgentStatus = "starting";
        latestMessage = event.message || "Starting white agent...";
      } else if (eventType === "white_agent_completed") {
        whiteAgentStatus = "completed";
        currentStep = event.steps_taken || currentStep;
        latestMessage = event.message || "White agent completed";
      }

      // Message events
      else if (eventType === "message_sent") {
        messageCount++;
        greenAgentStatus = "waiting_for_response";
        if (event.direction === "green_to_white") {
          latestMessage = `Sent task to white agent (step ${event.step})`;
        }
      } else if (eventType === "message_received") {
        messageCount++;
        greenAgentStatus = "processing_response";
        whiteAgentStatus = "responded";
        if (event.latency_ms) {
          thinkingTimeMs = event.latency_ms;
        }
        if (event.payload?.action?.op) {
          currentAction = event.payload.action.op;
        }
        currentStep = event.step || currentStep;
      }

      // Tool execution events
      else if (eventType === "tool_execution_start") {
        whiteAgentStatus = "executing_tool";
        currentAction = event.tool;
        currentStep = event.step || currentStep;
        latestMessage = `Executing: ${event.tool}`;
      } else if (eventType === "tool_execution_complete") {
        toolsUsed.add(event.tool);
        currentStep = Math.max(currentStep, (event.step || 0) + 1);
        whiteAgentStatus = event.status === "success" ? "tool_success" : "tool_failed";
        latestMessage = `${event.tool}: ${event.status} (${event.duration_ms}ms)`;
      }

      // Evaluation events
      else if (eventType === "evaluation_started") {
        evaluationProgress.started = true;
        evaluationProgress.message = event.message || "Running evaluation...";
        greenAgentStatus = "evaluating";
        whiteAgentStatus = "idle";
      } else if (eventType === "evaluation_completed") {
        evaluationProgress.completed = true;
        evaluationProgress.success = event.success;
        evaluationProgress.score = event.evaluation_score;
        evaluationProgress.message = event.message || `Score: ${event.evaluation_score}`;
        greenAgentStatus = "evaluation_complete";
      } else if (eventType === "evaluation_error") {
        evaluationProgress.completed = true;
        evaluationProgress.success = false;
        evaluationProgress.message = event.message || event.error;
        greenAgentStatus = "evaluation_failed";
      }

      // Summary events
      else if (eventType === "assessment_summary") {
        latestMessage = event.message || "Assessment complete";
      } else if (eventType === "assessment_completed") {
        vmProgress.stage = "done";
        greenAgentStatus = event.success ? "completed" : "failed";
        whiteAgentStatus = "idle";
      }

      // Legacy event types
      else if (eventType === "step" || eventType === "green_agent_step") {
        greenAgentStatus = "processing";
        if (event.data?.step !== undefined) {
          currentStep = event.data.step;
        }
        if (event.data?.total_steps !== undefined) {
          maxSteps = event.data.total_steps;
        }
      } else if (eventType === "action" || eventType === "white_agent_action") {
        whiteAgentStatus = "processing";
        if (event.data?.action) {
          toolsUsed.add(event.data.action);
          currentAction = event.data.action;
        }
      }
    }

    // Final status adjustments based on assessment status
    if (assessment.status === "completed" || assessment.status === "failed") {
      greenAgentStatus = assessment.status;
      whiteAgentStatus = "idle";
      vmProgress.stage = "done";
    } else if (assessment.status === "running" && greenAgentStatus === "idle") {
      greenAgentStatus = "initializing";
    }

    return NextResponse.json({
      assessment_id: id,
      status: assessment.status,

      // VM progress (NEW)
      vm_progress: vmProgress,

      // Setup progress (NEW)
      setup_progress: setupProgress,

      // Evaluation progress (NEW)
      evaluation_progress: evaluationProgress,

      // Green agent state (ENHANCED)
      green_agent: {
        status: greenAgentStatus,
        current_step: currentStep,
        max_steps: maxSteps,
        latest_message: latestMessage,
        current_action: currentAction,
        vm_status: vmProgress.stage,
      },

      // White agent state (ENHANCED)
      white_agent: {
        status: whiteAgentStatus,
        tools_used: Array.from(toolsUsed),
        message_count: messageCount,
        thinking_time_ms: thinkingTimeMs,
        white_agent_url: whiteAgentUrl,
      },

      // Task context (NEW)
      task_context: {
        instruction: taskInstruction,
        max_steps: maxSteps,
      },

      // Raw event data
      events: events,
      latest_event: latestEvent,
      event_count: events.length,
    });
  } catch (error) {
    console.error("Error getting agent state:", error);
    return NextResponse.json(
      { error: "Failed to get agent state" },
      { status: 500 }
    );
  }
}
