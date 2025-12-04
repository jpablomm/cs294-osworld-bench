"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";
import {
  Server,
  HardDrive,
  Loader2,
  CheckCircle2,
  Circle,
  Settings,
  Play,
  FlaskConical,
  Trash2,
  XCircle,
  Clock,
  Cpu,
  Network,
  Rocket,
} from "lucide-react";

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
  current_step?: number;
}

interface EvaluationProgress {
  started: boolean;
  completed: boolean;
  success?: boolean;
  score?: number;
  message?: string;
}

interface GreenAgentState {
  status?: string;
  current_step?: number;
  max_steps?: number;
  latest_message?: string;
  current_action?: string;
  vm_status?: string;
}

interface VMProgressPanelProps {
  vmProgress: VMProgress;
  setupProgress?: SetupProgress;
  evaluationProgress?: EvaluationProgress;
  assessmentStatus?: string;
  greenAgentState?: GreenAgentState;
}

const stages = [
  { key: "creating", label: "Creating VM", icon: HardDrive, description: "Provisioning cloud VM" },
  { key: "booting", label: "Booting", icon: Cpu, description: "Starting OS & services" },
  { key: "ready", label: "VM Ready", icon: Network, description: "Server responding" },
  { key: "setup", label: "Task Setup", icon: Settings, description: "Configuring environment" },
  { key: "running", label: "Running", icon: Play, description: "Agent executing" },
  { key: "evaluating", label: "Evaluating", icon: FlaskConical, description: "Checking results" },
  { key: "cleanup", label: "Cleanup", icon: Trash2, description: "Deleting VM" },
];

function getStageIndex(
  vmStage: VMStage,
  setupProgress?: SetupProgress,
  evaluationProgress?: EvaluationProgress,
  greenAgentStatus?: string
): number {
  // Final states
  if (vmStage === "done" || vmStage === "cleanup") {
    if (evaluationProgress?.completed) return 6; // cleanup
    return 5; // evaluating
  }

  // Check evaluation
  if (evaluationProgress?.started) return 5;

  // Check if white agent is running (setup must be complete)
  if (greenAgentStatus === "orchestrating" || greenAgentStatus === "waiting_for_response" ||
      greenAgentStatus === "processing_response") return 4; // running

  // Check setup
  if (setupProgress?.completed || greenAgentStatus === "setup_complete") return 4; // running
  if (setupProgress?.started || greenAgentStatus === "setting_up") return 3; // setup

  // VM stages
  if (vmStage === "ready") return 2;
  if (vmStage === "booting") return 1;
  if (vmStage === "creating") return 0;

  return -1; // pending
}

function StageIcon({
  stage,
  currentIndex,
  stageIndex,
  isError,
}: {
  stage: (typeof stages)[0];
  currentIndex: number;
  stageIndex: number;
  isError?: boolean;
}) {
  const Icon = stage.icon;
  const isActive = currentIndex === stageIndex;
  const isComplete = currentIndex > stageIndex;

  if (isError && isActive) {
    return (
      <div className="h-10 w-10 rounded-full bg-destructive/20 flex items-center justify-center border-2 border-destructive">
        <XCircle className="h-5 w-5 text-destructive" />
      </div>
    );
  }

  if (isComplete) {
    return (
      <motion.div
        initial={{ scale: 0.8 }}
        animate={{ scale: 1 }}
        className="h-10 w-10 rounded-full bg-success/20 flex items-center justify-center border-2 border-success"
      >
        <CheckCircle2 className="h-5 w-5 text-success" />
      </motion.div>
    );
  }

  if (isActive) {
    return (
      <motion.div
        className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center border-2 border-primary relative"
      >
        <Icon className="h-5 w-5 text-primary" />
        {/* Spinning ring */}
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-primary border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        />
      </motion.div>
    );
  }

  return (
    <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center border-2 border-muted-foreground/20">
      <Icon className="h-5 w-5 text-muted-foreground/50" />
    </div>
  );
}

function StatusMessage({ message, isActive }: { message: string; isActive: boolean }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={message}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={`flex items-center gap-2 text-sm ${isActive ? "text-primary" : "text-muted-foreground"}`}
      >
        {isActive && <Loader2 className="h-4 w-4 animate-spin" />}
        <span>{message}</span>
      </motion.div>
    </AnimatePresence>
  );
}

export function VMProgressPanel({
  vmProgress,
  setupProgress,
  evaluationProgress,
  assessmentStatus,
  greenAgentState,
}: VMProgressPanelProps) {
  const currentIndex = getStageIndex(
    vmProgress.stage,
    setupProgress,
    evaluationProgress,
    greenAgentState?.status
  );
  const isError = assessmentStatus === "failed";
  const isComplete = assessmentStatus === "completed";

  // Get current status message
  const getCurrentStatusMessage = (): string => {
    if (isComplete) return "Assessment completed";
    if (isError) return "Assessment failed";

    // Use green agent's latest message if available
    if (greenAgentState?.latest_message) {
      return greenAgentState.latest_message;
    }

    // Fall back to stage-specific messages
    const currentStage = stages[currentIndex];
    if (currentStage) {
      if (currentIndex === 3 && setupProgress?.message) {
        return setupProgress.message;
      }
      if (currentIndex === 5 && evaluationProgress?.message) {
        return evaluationProgress.message;
      }
      if (vmProgress.message) {
        return vmProgress.message;
      }
      return currentStage.description;
    }

    return "Initializing...";
  };

  const statusMessage = getCurrentStatusMessage();

  return (
    <Card className={isError ? "border-destructive" : isComplete ? "border-success" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Rocket className="h-4 w-4" />
            Assessment Progress
          </CardTitle>
          {assessmentStatus && (
            <Badge
              variant={
                isComplete ? "default" : isError ? "destructive" : "secondary"
              }
            >
              {assessmentStatus}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current Status Message */}
        <div className="p-3 bg-muted/50 rounded-lg border">
          <StatusMessage message={statusMessage} isActive={!isComplete && !isError} />
        </div>

        {/* Progress Steps - Horizontal on larger screens */}
        <div className="hidden md:block">
          <div className="flex items-start justify-between relative">
            {/* Connector lines */}
            <div className="absolute top-5 left-5 right-5 h-0.5 bg-muted" />
            <motion.div
              className="absolute top-5 left-5 h-0.5 bg-primary"
              initial={{ width: 0 }}
              animate={{
                width: isComplete
                  ? "calc(100% - 40px)"
                  : `${Math.max(0, (currentIndex / (stages.length - 1)) * 100)}%`,
              }}
              style={{ maxWidth: "calc(100% - 40px)" }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />

            {stages.map((stage, index) => (
              <div
                key={stage.key}
                className="flex flex-col items-center z-10 flex-1"
              >
                <StageIcon
                  stage={stage}
                  currentIndex={isComplete ? stages.length : currentIndex}
                  stageIndex={index}
                  isError={isError && currentIndex === index}
                />
                <span
                  className={`text-xs mt-2 text-center font-medium ${
                    currentIndex >= index
                      ? currentIndex === index
                        ? "text-primary"
                        : "text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Progress Steps - Vertical on mobile */}
        <div className="md:hidden space-y-2">
          {stages.map((stage, index) => {
            const isActive = currentIndex === index && !isComplete;
            const isDone = currentIndex > index || isComplete;
            const Icon = stage.icon;

            return (
              <motion.div
                key={stage.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className={`flex items-center gap-3 p-2 rounded ${
                  isActive ? "bg-primary/10" : isDone ? "bg-success/5" : ""
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center ${
                    isDone
                      ? "bg-success/20 text-success"
                      : isActive
                      ? "bg-primary/20 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                <div className="flex-1">
                  <p
                    className={`text-sm font-medium ${
                      isDone || isActive ? "text-foreground" : "text-muted-foreground"
                    }`}
                  >
                    {stage.label}
                  </p>
                  {isActive && (
                    <p className="text-xs text-muted-foreground">{stage.description}</p>
                  )}
                </div>
                {isDone && (
                  <CheckCircle2 className="h-4 w-4 text-success" />
                )}
              </motion.div>
            );
          })}
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-2 gap-2 pt-2">
          {vmProgress.vm_name && (
            <div className="text-xs">
              <span className="text-muted-foreground">VM:</span>
              <p className="font-mono truncate" title={vmProgress.vm_name}>
                {vmProgress.vm_name.replace("osworld-assessment-", "").slice(0, 20)}
              </p>
            </div>
          )}
          {vmProgress.vm_ip && (
            <div className="text-xs">
              <span className="text-muted-foreground">IP:</span>
              <p className="font-mono">{vmProgress.vm_ip}</p>
            </div>
          )}
          {vmProgress.vm_image && (
            <div className="text-xs">
              <span className="text-muted-foreground">Image:</span>
              <p className="truncate" title={vmProgress.vm_image}>
                {vmProgress.vm_image}
              </p>
            </div>
          )}
          {setupProgress?.started && (
            <div className="text-xs">
              <span className="text-muted-foreground">Setup:</span>
              <p className={setupProgress.completed ? "text-success" : "text-primary"}>
                {setupProgress.completed
                  ? "Complete"
                  : setupProgress.num_steps
                  ? `Running (${setupProgress.num_steps} steps)`
                  : "In progress"}
              </p>
            </div>
          )}
          {evaluationProgress?.started && (
            <div className="text-xs col-span-2">
              <span className="text-muted-foreground">Evaluation:</span>
              <p
                className={
                  evaluationProgress.completed
                    ? evaluationProgress.success
                      ? "text-success"
                      : "text-destructive"
                    : "text-primary"
                }
              >
                {evaluationProgress.completed
                  ? evaluationProgress.score !== undefined
                    ? `Score: ${evaluationProgress.score}${evaluationProgress.success ? " (Passed)" : " (Failed)"}`
                    : evaluationProgress.success
                    ? "Passed"
                    : "Failed"
                  : "Running..."}
              </p>
            </div>
          )}
          {greenAgentState?.current_step !== undefined && greenAgentState.current_step > 0 && (
            <div className="text-xs">
              <span className="text-muted-foreground">Step:</span>
              <p>
                {greenAgentState.current_step}
                {greenAgentState.max_steps ? ` / ${greenAgentState.max_steps}` : ""}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
