"use client";

import { useParams } from "next/navigation";
import { useBatch } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AssessmentTable } from "@/components/dashboard/AssessmentTable";
import { TrendingUp, Activity, Clock, Target, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

export default function BatchDetailPage() {
  const params = useParams();
  const batchId = params.id as string;
  const { data: batch, isLoading } = useBatch(batchId);

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
              <h1 className="text-3xl font-bold tracking-tight">Batch Assessment</h1>
              <p className="text-muted-foreground">Batch ID: {batch.batch_id}</p>
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
              Running multiple assessments for statistical significance
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              Batch assessments run the same task multiple times to get a rolling average
              of the agent's performance. This helps reduce variance and provides more
              reliable metrics.
            </p>
            <p>
              Each run in the batch is independent and uses the same configuration
              (max steps, VM image, etc.).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

