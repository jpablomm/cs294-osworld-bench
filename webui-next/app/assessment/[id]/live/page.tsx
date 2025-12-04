"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useAssessment,
  useAssessmentMessages,
  useToolExecutions,
  useAgentState,
} from "@/lib/api/queries";
import { useSSE } from "@/lib/hooks/useSSE";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CompactAgentBar } from "@/components/agents/CompactAgentBar";
import { ProgressStepper } from "@/components/agents/ProgressStepper";
import { StepViewer } from "@/components/agents/StepViewer";
import {
  ArrowLeft,
  Loader2,
  Radio,
  CheckCircle2,
  XCircle,
  Clock,
  Target,
  ExternalLink,
} from "lucide-react";
import { motion } from "framer-motion";

export default function LiveAssessmentPage() {
  const params = useParams();
  const assessmentId = params.id as string;

  // Fetch all data
  const { data: assessment, isLoading } = useAssessment(assessmentId);
  const shouldPollAgentState =
    assessment?.status === "running" ||
    assessment?.status === "pending" ||
    !assessment?.status;
  const { data: messages } = useAssessmentMessages(assessmentId);
  const { data: tools } = useToolExecutions(assessmentId);
  const { data: agentState } = useAgentState(assessmentId, shouldPollAgentState);

  // Real-time updates via SSE
  const { connected: sseConnected } = useSSE(assessmentId, {
    enabled: shouldPollAgentState,
  });

  if (isLoading) {
    return (
      <div className="container py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="container py-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Assessment Not Found</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">
              The assessment with ID "{assessmentId}" could not be found.
            </p>
            <Link href="/results">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Results
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Status detection
  const isPending = assessment.status === "pending" || !assessment.status;
  const isRunning = assessment.status === "running";
  const isCompleted = assessment.status === "completed";
  const isFailed = assessment.status === "failed";
  const isActive = isPending || isRunning;

  // Extract state from agent data
  const vmProgress = agentState?.vm_progress || { stage: "pending" };
  const setupProgress = agentState?.setup_progress;
  const evaluationProgress = agentState?.evaluation_progress;
  const taskContext = agentState?.task_context;
  const greenAgent = agentState?.green_agent;
  const whiteAgent = agentState?.white_agent;

  // Get status message for stepper
  const getStatusMessage = () => {
    if (isCompleted) return "Assessment completed";
    if (isFailed) return assessment.failure_reason || "Assessment failed";
    if (greenAgent?.latest_message) return greenAgent.latest_message;
    if (vmProgress.message) return vmProgress.message;
    if (setupProgress?.message) return setupProgress.message;
    return "Initializing...";
  };


  return (
    <div className="container max-w-5xl mx-auto py-6 space-y-4">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href={`/assessment/${assessmentId}`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
          </Link>
          <div className="h-4 w-px bg-border" />
          <h1 className="text-lg font-semibold">Live View</h1>
          {isActive && (
            <motion.div
              className="flex items-center gap-1.5"
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Radio className="h-4 w-4 text-success" />
              <span className="text-xs text-success font-medium">Live</span>
            </motion.div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isPending && (
            <Badge variant="secondary">
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              Starting
            </Badge>
          )}
          {isRunning && (
            <Badge variant="secondary">
              <Clock className="mr-1 h-3 w-3 animate-pulse" />
              Running
            </Badge>
          )}
          {isCompleted && (
            <Badge variant="default">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Completed
            </Badge>
          )}
          {isFailed && (
            <Badge variant="destructive">
              <XCircle className="mr-1 h-3 w-3" />
              Failed
            </Badge>
          )}
        </div>
      </div>

      {/* Task Instruction (collapsible header) */}
      {(taskContext?.instruction || assessment.task_id) && (
        <Card className="bg-muted/30">
          <CardContent className="py-3">
            <div className="flex items-start gap-3">
              <Target className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {assessment.task_id || assessmentId}
                </p>
                {taskContext?.instruction && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                    {taskContext.instruction}
                  </p>
                )}
              </div>
              {taskContext?.max_steps && (
                <Badge variant="outline" className="text-xs flex-shrink-0">
                  {greenAgent?.current_step || 0} / {taskContext.max_steps} steps
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Compact Agent Status Bar */}
      <CompactAgentBar
        greenAgent={greenAgent}
        whiteAgent={whiteAgent}
        isActive={isActive}
      />

      {/* Progress Stepper */}
      <ProgressStepper
        vmStage={vmProgress.stage}
        setupProgress={setupProgress}
        evaluationProgress={evaluationProgress}
        greenAgentStatus={greenAgent?.status}
        statusMessage={getStatusMessage()}
        isError={isFailed}
        isComplete={isCompleted}
      />

      {/* Step Viewer - Full width screenshot with reasoning and actions */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <StepViewer
          messages={messages?.messages || []}
          tools={tools?.executions || []}
          isActive={isActive}
        />
      </motion.div>

      {/* Results Summary - Only shown when completed */}
      {(isCompleted || isFailed) && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className={isCompleted ? "border-success/50" : "border-destructive/50"}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                {isCompleted ? (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                ) : (
                  <XCircle className="h-4 w-4 text-destructive" />
                )}
                Assessment Results
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {evaluationProgress?.score !== undefined && (
                  <div>
                    <p className="text-xs text-muted-foreground">Score</p>
                    <p className="text-lg font-semibold">{evaluationProgress.score}</p>
                  </div>
                )}
                {assessment.steps !== undefined && (
                  <div>
                    <p className="text-xs text-muted-foreground">Steps</p>
                    <p className="text-lg font-semibold">{assessment.steps}</p>
                  </div>
                )}
                {assessment.time_sec !== undefined && (
                  <div>
                    <p className="text-xs text-muted-foreground">Duration</p>
                    <p className="text-lg font-semibold">{assessment.time_sec}s</p>
                  </div>
                )}
                {assessment.vm_cost !== undefined && (
                  <div>
                    <p className="text-xs text-muted-foreground">VM Cost</p>
                    <p className="text-lg font-semibold">${assessment.vm_cost.toFixed(4)}</p>
                  </div>
                )}
              </div>
              {isFailed && assessment.failure_reason && (
                <div className="mt-3 p-2 bg-destructive/10 rounded text-sm text-destructive">
                  {assessment.failure_reason}
                </div>
              )}
              <div className="mt-4 flex gap-2">
                <Link href={`/assessment/${assessmentId}`}>
                  <Button variant="outline" size="sm">
                    <ExternalLink className="mr-1 h-3 w-3" />
                    View Details
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
