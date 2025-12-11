"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useAssessment,
  useAssessmentMessages,
  useToolExecutions,
  useTask,
} from "@/lib/api/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StepViewer } from "@/components/agents/StepViewer";
import {
  CheckCircle2,
  XCircle,
  Clock,
  ArrowLeft,
  Loader2,
  Activity,
  Zap,
  Timer,
  Target,
  FlaskConical,
  TrendingUp,
  AlertTriangle,
  Bot,
  BarChart3,
  RefreshCcw,
  MousePointer,
} from "lucide-react";
import { motion } from "framer-motion";
import type { EvaluationResult, TrajectoryAnalysis, LLMJudgment } from "@/lib/types";

export default function AssessmentDetailPage() {
  const params = useParams();
  const assessmentId = params.id as string;

  // Fetch assessment data
  const { data: assessment, isLoading } = useAssessment(assessmentId);
  const { data: messages } = useAssessmentMessages(assessmentId);
  const { data: tools } = useToolExecutions(assessmentId);

  // Fetch task data to get evaluator info
  const { data: task } = useTask(assessment?.task_id || "", assessment?.domain || undefined);

  // Extract enhanced evaluation data
  const evalResult = assessment?.result as EvaluationResult | undefined;
  const efficiency = evalResult?.efficiency;
  const trajectoryAnalysis = evalResult?.trajectory_analysis;
  const llmJudgment = evalResult?.llm_judgment;
  const evaluationMethod = assessment?.evaluation_method || evalResult?.evaluation_method;

  if (isLoading) {
    return (
      <div className="container max-w-5xl mx-auto py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="container max-w-5xl mx-auto py-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Assessment Not Found</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">
              The assessment with ID &quot;{assessmentId}&quot; could not be found.
            </p>
            <Link href="/">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Dashboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isRunning = assessment.status === "running";
  const isCompleted = assessment.status === "completed";
  const isFailed = assessment.status === "failed";
  const isSuccess = isCompleted && assessment.success;
  const isLLMOverride = evaluationMethod === "llm_judge_override";

  return (
    <div className="container max-w-5xl mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="space-y-4">
        <Link href="/">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight truncate">
              {assessment.task_id}
            </h1>
            {task?.instruction && (
              <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                {task.instruction}
              </p>
            )}
            <p className="text-xs text-muted-foreground/70 mt-1 font-mono">
              {assessmentId}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {isRunning && (
              <Link href={`/assessment/${assessmentId}/live`}>
                <Button variant="outline" size="sm">
                  <Activity className="mr-2 h-4 w-4" />
                  Live View
                </Button>
              </Link>
            )}
            {isLLMOverride && (
              <Badge variant="outline" className="bg-purple-500/10 text-purple-400 border-purple-500/30">
                <Bot className="mr-1 h-3 w-3" />
                LLM Override
              </Badge>
            )}
            <Badge
              variant={isSuccess ? "default" : isFailed ? "destructive" : "secondary"}
              className="h-7 px-3"
            >
              {isSuccess && <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />}
              {isFailed && <XCircle className="mr-1.5 h-3.5 w-3.5" />}
              {isRunning && <Clock className="mr-1.5 h-3.5 w-3.5 animate-pulse" />}
              {assessment.status}
            </Badge>
          </div>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
                  <Target className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Domain</p>
                  <p className="font-medium">{assessment.domain || "N/A"}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
                  <Zap className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Steps</p>
                  <p className="font-medium">
                    {assessment.steps}
                    <span className="text-muted-foreground font-normal">
                      {" "}/ {assessment.config?.max_steps || 15}
                    </span>
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
                  <Timer className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Duration</p>
                  <p className="font-medium">
                    {assessment.time_sec ? `${Math.round(assessment.time_sec)}s` : "—"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center gap-3">
                <div className={`h-9 w-9 rounded-full flex items-center justify-center ${
                  isSuccess ? "bg-success/10" : isFailed ? "bg-destructive/10" : "bg-primary/10"
                }`}>
                  <FlaskConical className={`h-4 w-4 ${
                    isSuccess ? "text-success" : isFailed ? "text-destructive" : "text-primary"
                  }`} />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    {task?.evaluator?.func || "Evaluation"}
                  </p>
                  <p className="font-medium">
                    {typeof assessment.evaluation_score === "number"
                      ? assessment.evaluation_score.toFixed(2)
                      : "—"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Efficiency Breakdown (if available) */}
      {efficiency && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Efficiency Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Base Score</p>
                  <p className="text-lg font-semibold">{efficiency.base_score.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Adjusted Score</p>
                  <p className="text-lg font-semibold">{efficiency.adjusted_score.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Efficiency Ratio</p>
                  <p className="text-lg font-semibold">
                    {(efficiency.efficiency_ratio * 100).toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Steps vs Expected</p>
                  <p className="text-lg font-semibold">
                    {efficiency.steps_taken} / {efficiency.expected_steps}
                  </p>
                </div>
              </div>
              {efficiency.efficiency_ratio < 1.0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  Score reduced by {((1 - efficiency.adjusted_score / efficiency.base_score) * 100).toFixed(0)}% due to inefficiency
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Trajectory Analysis (if available) */}
      {trajectoryAnalysis && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Trajectory Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-4">
              {/* Warnings */}
              {trajectoryAnalysis.warnings && trajectoryAnalysis.warnings.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {trajectoryAnalysis.warnings.map((warning, idx) => (
                    <Badge key={idx} variant="outline" className="bg-warning/10 text-warning border-warning/30">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      {warning}
                    </Badge>
                  ))}
                </div>
              )}

              {/* Action Breakdown */}
              <div>
                <p className="text-xs text-muted-foreground mb-2">Action Breakdown</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(trajectoryAnalysis.action_counts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([action, count]) => (
                      <div
                        key={action}
                        className="flex items-center gap-1.5 px-2 py-1 bg-muted rounded text-sm"
                      >
                        <ActionIcon action={action} />
                        <span className="font-medium">{action}</span>
                        <span className="text-muted-foreground">×{count}</span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2 border-t">
                <div>
                  <p className="text-xs text-muted-foreground">Total Steps</p>
                  <p className="font-medium">{trajectoryAnalysis.total_steps}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Unique Actions</p>
                  <p className="font-medium">{trajectoryAnalysis.unique_actions}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Screenshot Ratio</p>
                  <p className={`font-medium ${trajectoryAnalysis.screenshot_ratio > 0.5 ? "text-warning" : ""}`}>
                    {(trajectoryAnalysis.screenshot_ratio * 100).toFixed(0)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Errors</p>
                  <p className={`font-medium ${trajectoryAnalysis.error_count > 0 ? "text-destructive" : ""}`}>
                    {trajectoryAnalysis.error_count}
                  </p>
                </div>
              </div>

              {/* Loop Details */}
              {trajectoryAnalysis.has_loops && trajectoryAnalysis.loop_details && (
                <div className="pt-2 border-t">
                  <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                    <RefreshCcw className="h-3 w-3" />
                    Detected Loops
                  </p>
                  <div className="space-y-1">
                    {trajectoryAnalysis.loop_details.map((loop, idx) => (
                      <div key={idx} className="text-sm text-muted-foreground">
                        {loop.type === "consecutive_repeat" ? (
                          <span>
                            <code className="bg-muted px-1 rounded">{loop.action}</code> repeated {loop.repeat_count}× at step {loop.start_index}
                          </span>
                        ) : (
                          <span>
                            Pattern <code className="bg-muted px-1 rounded">{loop.pattern?.join(" → ")}</code> repeated {loop.repeat_count}×
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* LLM Judgment (if available) */}
      {llmJudgment && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <Card className={llmJudgment.success ? "border-purple-500/30 bg-purple-500/5" : ""}>
            <CardHeader className="py-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Bot className="h-4 w-4" />
                  LLM Judge Analysis
                </CardTitle>
                <div className="flex items-center gap-2">
                  {llmJudgment.provider && llmJudgment.model && (
                    <Badge variant="outline" className="text-xs">
                      {llmJudgment.provider}/{llmJudgment.model}
                    </Badge>
                  )}
                  <Badge
                    variant={llmJudgment.success ? "default" : "secondary"}
                    className={llmJudgment.success ? "bg-purple-500" : ""}
                  >
                    {llmJudgment.success ? "Success" : "Failure"}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              {/* Confidence */}
              <div className="flex items-center gap-3">
                <p className="text-xs text-muted-foreground">Confidence:</p>
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{ width: `${llmJudgment.confidence * 100}%` }}
                  />
                </div>
                <p className="text-sm font-medium">{(llmJudgment.confidence * 100).toFixed(0)}%</p>
              </div>

              {/* Reasoning */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Reasoning:</p>
                <p className="text-sm bg-muted/50 p-3 rounded-lg">
                  {llmJudgment.reasoning}
                </p>
              </div>

              {/* Evidence Used */}
              {llmJudgment.evidence_used && llmJudgment.evidence_used.length > 0 && (
                <div className="flex items-center gap-2">
                  <p className="text-xs text-muted-foreground">Evidence used:</p>
                  {llmJudgment.evidence_used.map((evidence) => (
                    <Badge key={evidence} variant="outline" className="text-xs">
                      {evidence.replace(/_/g, " ")}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Failure Reason */}
      {assessment.failure_reason && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="border-destructive/50 bg-destructive/5">
            <CardContent className="py-3">
              <div className="flex items-start gap-3">
                <XCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-destructive">Failure Reason</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {assessment.failure_reason}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Step Viewer */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <StepViewer
          messages={messages?.messages || []}
          tools={tools?.executions || []}
          isActive={isRunning}
        />
      </motion.div>
    </div>
  );
}

/**
 * Helper component to show action-specific icons
 */
function ActionIcon({ action }: { action: string }) {
  switch (action.toLowerCase()) {
    case "click":
      return <MousePointer className="h-3 w-3" />;
    case "type":
      return <span className="text-xs">⌨</span>;
    case "screenshot":
      return <span className="text-xs">📷</span>;
    case "scroll":
      return <span className="text-xs">↕</span>;
    case "hotkey":
      return <span className="text-xs">⌘</span>;
    case "done":
      return <CheckCircle2 className="h-3 w-3 text-success" />;
    default:
      return <Zap className="h-3 w-3" />;
  }
}
