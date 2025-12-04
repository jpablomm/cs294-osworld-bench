"use client";

import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import {
  HardDrive,
  Cpu,
  Network,
  Settings,
  Play,
  FlaskConical,
  Trash2,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";

type VMStage = "pending" | "creating" | "booting" | "ready" | "cleanup" | "done";

interface SetupProgress {
  started: boolean;
  completed: boolean;
  num_steps?: number;
}

interface EvaluationProgress {
  started: boolean;
  completed: boolean;
  success?: boolean;
  score?: number;
}

interface ProgressStepperProps {
  vmStage: VMStage;
  setupProgress?: SetupProgress;
  evaluationProgress?: EvaluationProgress;
  greenAgentStatus?: string;
  statusMessage?: string;
  isError?: boolean;
  isComplete?: boolean;
}

const stages = [
  { key: "creating", label: "VM", icon: HardDrive },
  { key: "booting", label: "Boot", icon: Cpu },
  { key: "ready", label: "Ready", icon: Network },
  { key: "setup", label: "Setup", icon: Settings },
  { key: "running", label: "Running", icon: Play },
  { key: "evaluating", label: "Eval", icon: FlaskConical },
  { key: "cleanup", label: "Done", icon: Trash2 },
];

function getStageIndex(
  vmStage: VMStage,
  setupProgress?: SetupProgress,
  evaluationProgress?: EvaluationProgress,
  greenAgentStatus?: string
): number {
  if (vmStage === "done" || vmStage === "cleanup") {
    if (evaluationProgress?.completed) return 6;
    return 5;
  }
  if (evaluationProgress?.started) return 5;
  if (greenAgentStatus === "orchestrating" || greenAgentStatus === "waiting_for_response" ||
      greenAgentStatus === "processing_response") return 4;
  if (setupProgress?.completed || greenAgentStatus === "setup_complete") return 4;
  if (setupProgress?.started || greenAgentStatus === "setting_up") return 3;
  if (vmStage === "ready") return 2;
  if (vmStage === "booting") return 1;
  if (vmStage === "creating") return 0;
  return -1;
}

export function ProgressStepper({
  vmStage,
  setupProgress,
  evaluationProgress,
  greenAgentStatus,
  statusMessage,
  isError,
  isComplete,
}: ProgressStepperProps) {
  const currentIndex = getStageIndex(vmStage, setupProgress, evaluationProgress, greenAgentStatus);

  return (
    <div className="bg-card border rounded-lg p-3">
      <div className="flex items-center gap-1">
        {/* Progress dots */}
        <div className="flex items-center gap-1 flex-1">
          {stages.map((stage, index) => {
            const Icon = stage.icon;
            const isActive = currentIndex === index && !isComplete;
            const isDone = currentIndex > index || isComplete;
            const isPending = currentIndex < index && !isComplete;

            return (
              <div key={stage.key} className="flex items-center flex-1">
                {/* Stage indicator */}
                <div className="flex flex-col items-center">
                  <motion.div
                    className={`h-7 w-7 rounded-full flex items-center justify-center text-xs transition-colors ${
                      isDone
                        ? "bg-success/20 text-success"
                        : isActive
                        ? "bg-primary/20 text-primary"
                        : isError && isActive
                        ? "bg-destructive/20 text-destructive"
                        : "bg-muted text-muted-foreground/50"
                    }`}
                    animate={isActive ? { scale: [1, 1.1, 1] } : {}}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    {isDone ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : isActive ? (
                      isError ? (
                        <XCircle className="h-3.5 w-3.5" />
                      ) : (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      )
                    ) : (
                      <Icon className="h-3.5 w-3.5" />
                    )}
                  </motion.div>
                  <span
                    className={`text-[10px] mt-0.5 ${
                      isDone || isActive ? "text-foreground" : "text-muted-foreground/50"
                    }`}
                  >
                    {stage.label}
                  </span>
                </div>

                {/* Connector line */}
                {index < stages.length - 1 && (
                  <div className="flex-1 h-0.5 mx-1 relative">
                    <div className="absolute inset-0 bg-muted rounded" />
                    <motion.div
                      className={`absolute top-0 left-0 h-full rounded ${
                        isError && isActive ? "bg-destructive" : "bg-primary"
                      }`}
                      initial={{ width: 0 }}
                      animate={{
                        width: isDone ? "100%" : isActive ? "50%" : "0%",
                      }}
                      transition={{ duration: 0.3 }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Status message */}
        {statusMessage && (
          <div className="ml-3 flex items-center gap-2 min-w-0">
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground truncate max-w-[200px]">
              {!isComplete && !isError && (
                <Loader2 className="h-3 w-3 animate-spin text-primary flex-shrink-0" />
              )}
              <span className="truncate">{statusMessage}</span>
            </div>
          </div>
        )}

        {/* Score badge for completed */}
        {isComplete && evaluationProgress?.score !== undefined && (
          <Badge
            variant={evaluationProgress.success ? "default" : "destructive"}
            className="ml-2"
          >
            Score: {evaluationProgress.score}
          </Badge>
        )}
      </div>
    </div>
  );
}
