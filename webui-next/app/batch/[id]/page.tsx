"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { useBatch } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AssessmentTable } from "@/components/dashboard/AssessmentTable";
import { TrendingUp, Activity, Clock, Target, ArrowLeft, Loader2, Layers } from "lucide-react";
import Link from "next/link";

export default function BatchDetailPage() {
  const params = useParams();
  const batchId = params.id as string;
  const { data: batch, isLoading } = useBatch(batchId);

  // Calculate multi-task metrics
  const taskMetrics = useMemo(() => {
    if (!batch?.assessments) return null;

    const taskIds = [...new Set(batch.assessments.map((a) => a.task_id))];
    const isMultiTask = taskIds.length > 1;

    // Group assessments by task
    const byTask = new Map<string, typeof batch.assessments>();
    for (const assessment of batch.assessments) {
      const existing = byTask.get(assessment.task_id) || [];
      existing.push(assessment);
      byTask.set(assessment.task_id, existing);
    }

    // Calculate per-task stats
    const taskStats = Array.from(byTask.entries()).map(([taskId, assessments]) => {
      const completed = assessments.filter((a) => a.status === "completed");
      const successful = completed.filter((a) => a.success === 1);
      const successRate = completed.length > 0 ? (successful.length / completed.length) * 100 : 0;
      const avgSteps = completed.length > 0
        ? completed.reduce((sum, a) => sum + a.steps, 0) / completed.length
        : 0;
      const avgTime = completed.length > 0
        ? completed.reduce((sum, a) => sum + (a.time_sec || 0), 0) / completed.length
        : 0;

      return {
        taskId,
        total: assessments.length,
        completed: completed.length,
        running: assessments.filter((a) => a.status === "running").length,
        successRate,
        avgSteps,
        avgTime,
        domain: assessments[0]?.domain || "unknown",
      };
    });

    // Get unique domains
    const domains = [...new Set(batch.assessments.map((a) => a.domain).filter(Boolean))];

    return {
      isMultiTask,
      taskCount: taskIds.length,
      taskStats,
      domains,
    };
  }, [batch?.assessments]);

  if (isLoading) {
    return (
      <div className="container py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="container py-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Batch Not Found</CardTitle>
            <CardDescription>
              The batch with ID "{batchId}" could not be found.
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
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-bold tracking-tight">Batch Assessment</h1>
                {taskMetrics?.isMultiTask && (
                  <Badge variant="secondary" className="text-sm">
                    <Layers className="h-3 w-3 mr-1" />
                    Multi-Task
                  </Badge>
                )}
              </div>
              <p className="text-muted-foreground">Batch ID: {batch.batch_id}</p>
              {taskMetrics?.isMultiTask && taskMetrics.domains.length > 0 && (
                <p className="text-sm text-muted-foreground mt-1">
                  Domains: {taskMetrics.domains.join(", ")}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Aggregate Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{batch.total_runs}</div>
              <p className="text-xs text-muted-foreground">
                {batch.completed_runs} completed
                {taskMetrics?.isMultiTask && ` across ${taskMetrics.taskCount} tasks`}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" style={{ color: "var(--success)" }}>
                {batch.aggregate_stats.success_rate.toFixed(1)}%
              </div>
              <p className="text-xs text-muted-foreground">Across all runs</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Steps</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {batch.aggregate_stats.avg_steps.toFixed(1)}
              </div>
              <p className="text-xs text-muted-foreground">Per run</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Time</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {batch.aggregate_stats.avg_time_sec.toFixed(1)}s
              </div>
              <p className="text-xs text-muted-foreground">Per run</p>
            </CardContent>
          </Card>
        </div>

        {/* Per-Task Breakdown (Multi-Task Only) */}
        {taskMetrics?.isMultiTask && (
          <Card>
            <CardHeader>
              <CardTitle>Per-Task Breakdown</CardTitle>
              <CardDescription>
                Performance metrics for each task in this batch
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-2 font-medium">Task ID</th>
                      <th className="text-left py-2 px-2 font-medium">Domain</th>
                      <th className="text-center py-2 px-2 font-medium">Runs</th>
                      <th className="text-center py-2 px-2 font-medium">Status</th>
                      <th className="text-center py-2 px-2 font-medium">Success Rate</th>
                      <th className="text-center py-2 px-2 font-medium">Avg Steps</th>
                      <th className="text-center py-2 px-2 font-medium">Avg Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taskMetrics.taskStats.map((stat) => (
                      <tr key={stat.taskId} className="border-b last:border-0">
                        <td className="py-2 px-2 font-mono text-xs">{stat.taskId}</td>
                        <td className="py-2 px-2">
                          <Badge variant="outline" className="text-xs">
                            {stat.domain}
                          </Badge>
                        </td>
                        <td className="py-2 px-2 text-center">{stat.total}</td>
                        <td className="py-2 px-2 text-center">
                          {stat.running > 0 ? (
                            <Badge variant="secondary" className="text-xs">
                              {stat.running} running
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">
                              {stat.completed} done
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-center">
                          <span
                            className="font-medium"
                            style={{
                              color: stat.successRate >= 50 ? "var(--success)" : "var(--destructive)",
                            }}
                          >
                            {stat.successRate.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-2 px-2 text-center">{stat.avgSteps.toFixed(1)}</td>
                        <td className="py-2 px-2 text-center">{stat.avgTime.toFixed(1)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Individual Runs */}
        <Card>
          <CardHeader>
            <CardTitle>Individual Runs</CardTitle>
            <CardDescription>
              All assessment runs in this batch
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AssessmentTable assessments={batch.assessments} />
          </CardContent>
        </Card>

        {/* Info */}
        <Card>
          <CardHeader>
            <CardTitle>About Batch Assessments</CardTitle>
            <CardDescription>
              {taskMetrics?.isMultiTask
                ? "Running multiple tasks in a single batch"
                : "Running multiple assessments for statistical significance"
              }
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            {taskMetrics?.isMultiTask ? (
              <>
                <p>
                  This is a multi-task batch containing {taskMetrics.taskCount} different tasks.
                  Each task may have multiple runs for statistical significance.
                </p>
                <p>
                  The aggregate statistics show overall performance across all tasks and runs.
                  Use the per-task breakdown above to see individual task performance.
                </p>
              </>
            ) : (
              <>
                <p>
                  Batch assessments run the same task multiple times to get a rolling average
                  of the agent's performance. This helps reduce variance and provides more
                  reliable metrics.
                </p>
                <p>
                  Each run in the batch is independent and uses the same configuration
                  (max steps, VM image, etc.).
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
