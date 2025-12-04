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
  TrendingUp,
  FlaskConical,
} from "lucide-react";
import { motion } from "framer-motion";

export default function AssessmentDetailPage() {
  const params = useParams();
  const assessmentId = params.id as string;

  // Fetch assessment data
  const { data: assessment, isLoading } = useAssessment(assessmentId);
  const { data: messages } = useAssessmentMessages(assessmentId);
  const { data: tools } = useToolExecutions(assessmentId);

  // Fetch task data to get evaluator info
  const { data: task } = useTask(assessment?.task_id || "", assessment?.domain || undefined);

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

  const isRunning = assessment.status === "running";
  const isCompleted = assessment.status === "completed";
  const isFailed = assessment.status === "failed";
  const isSuccess = isCompleted && assessment.success;

  return (
    <div className="container max-w-5xl mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="space-y-4">
        <Link href="/results">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Results
          </Button>
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight truncate">
              {assessment.task_id}
            </h1>
            <p className="text-sm text-muted-foreground truncate">
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
        transition={{ delay: 0.25 }}
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
