"use client";

import { useParams } from "next/navigation";
import { useAssessment } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Clock, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

export default function AssessmentDetailPage() {
  const params = useParams();
  const assessmentId = params.id as string;
  const { data: assessment, isLoading } = useAssessment(assessmentId);

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
            <CardDescription>
              The assessment with ID "{assessmentId}" could not be found.
            </CardDescription>
          </CardHeader>
          <CardContent>
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

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <Link href="/results">
            <Button variant="ghost" size="sm" className="mb-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Results
            </Button>
          </Link>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{assessment.task_id}</h1>
              <p className="text-muted-foreground">Assessment ID: {assessment.id}</p>
            </div>
            <Badge
              variant={
                assessment.status === "completed"
                  ? "default"
                  : assessment.status === "failed"
                  ? "destructive"
                  : "secondary"
              }
              className="h-8 px-4"
            >
              {assessment.status === "completed" && assessment.success && (
                <CheckCircle2 className="mr-2 h-4 w-4" />
              )}
              {assessment.status === "failed" && <XCircle className="mr-2 h-4 w-4" />}
              {assessment.status === "running" && <Clock className="mr-2 h-4 w-4 animate-pulse" />}
              {assessment.status}
            </Badge>
          </div>
        </div>

        {/* Overview */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Domain</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge variant="outline">{assessment.domain || "N/A"}</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Steps Taken</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{assessment.steps}</div>
              <p className="text-xs text-muted-foreground">
                Max: {assessment.config.max_steps}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Execution Time</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {assessment.time_sec ? `${Math.round(assessment.time_sec)}s` : "—"}
              </div>
              <p className="text-xs text-muted-foreground">Total duration</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Evaluation Score</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {assessment.evaluation_score !== null
                  ? assessment.evaluation_score.toFixed(2)
                  : "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                {assessment.evaluation_method || "N/A"}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Coming Soon Banner */}
        <Card className="border-primary/50 bg-primary/5">
          <CardHeader>
            <CardTitle>🚧 Agent Interaction View - Coming in Phase 4</CardTitle>
            <CardDescription>
              This page will show real-time agent interactions, A2A messages, tool executions,
              and trajectory visualization. Currently in development.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>✨ <strong>Planned features:</strong></p>
              <ul className="list-disc list-inside space-y-1 ml-4">
                <li>Live agent status cards (Green Agent ↔ White Agent)</li>
                <li>A2A message history with validation details</li>
                <li>Tool execution timeline with before/after screenshots</li>
                <li>Agent reasoning and thinking process</li>
                <li>Interactive trajectory playback</li>
                <li>Real-time SSE updates</li>
              </ul>
            </div>
          </CardContent>
        </Card>

        {/* Trajectory */}
        {assessment.trajectory && assessment.trajectory.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Trajectory</CardTitle>
              <CardDescription>
                Action sequence taken by the agent
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {assessment.trajectory.map((step, index) => (
                  <div
                    key={index}
                    className="flex gap-4 border-l-2 border-primary/30 pl-4 pb-4 last:pb-0"
                  >
                    <div className="flex-shrink-0">
                      <Badge variant="outline" className="font-mono">
                        Step {step.step}
                      </Badge>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm mb-1">
                        Action: <code className="text-primary">{step.action.op}</code>
                      </p>
                      <p className="text-sm text-muted-foreground line-clamp-3">
                        {step.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Failure Reason */}
        {assessment.failure_reason && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Failure Reason</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{assessment.failure_reason}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

