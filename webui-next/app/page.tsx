"use client";

import { useStats, useAssessments } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, CheckCircle2, XCircle, Clock, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useStats();
  const { data: assessments, isLoading: assessmentsLoading } = useAssessments({ limit: 10 });

  if (statsError) {
    return (
      <div className="container py-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Connection Error</CardTitle>
            <CardDescription>
              Failed to connect to the API. Make sure the webui server is running on http://localhost:3001
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="text-sm text-muted-foreground">
              {statsError instanceof Error ? statsError.message : "Unknown error"}
            </pre>
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
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of OSWorld agent assessments and performance
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Total Assessments */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Assessments</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {statsLoading ? "..." : stats?.total_assessments || 0}
              </div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? " " : `${stats?.total_running || 0} running`}
              </p>
            </CardContent>
          </Card>

          {/* Success Rate */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold" style={{ color: "var(--success)" }}>
                {statsLoading ? "..." : `${Math.round(stats?.success_rate || 0)}%`}
              </div>
              <p className="text-xs text-muted-foreground">
                {statsLoading ? " " : `${stats?.total_successes || 0} successful`}
              </p>
            </CardContent>
          </Card>

          {/* Avg Steps */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Steps</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {statsLoading ? "..." : Math.round(stats?.avg_steps || 0)}
              </div>
              <p className="text-xs text-muted-foreground">per assessment</p>
            </CardContent>
          </Card>

          {/* Avg Time */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Time</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {statsLoading ? "..." : `${Math.round(stats?.avg_time_sec || 0)}s`}
              </div>
              <p className="text-xs text-muted-foreground">per assessment</p>
            </CardContent>
          </Card>
        </div>

        {/* Recent Assessments */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Assessments</CardTitle>
            <CardDescription>Latest assessment runs</CardDescription>
          </CardHeader>
          <CardContent>
            {assessmentsLoading ? (
              <p className="text-sm text-muted-foreground">Loading assessments...</p>
            ) : assessments?.assessments && assessments.assessments.length > 0 ? (
              <div className="space-y-4">
                {assessments.assessments.slice(0, 5).map((assessment) => (
                  <div
                    key={assessment.id}
                    className="flex items-center justify-between border-b border-border pb-4 last:border-0 last:pb-0"
                  >
                    <div className="flex items-center gap-4">
                      {assessment.status === "completed" && assessment.success ? (
                        <CheckCircle2 className="h-5 w-5 text-success" />
                      ) : assessment.status === "failed" ? (
                        <XCircle className="h-5 w-5 text-destructive" />
                      ) : (
                        <Clock className="h-5 w-5 text-warning animate-pulse" />
                      )}
                      <div>
                        <p className="font-medium">{assessment.task_id}</p>
                        <p className="text-sm text-muted-foreground">
                          {assessment.domain || "Unknown domain"} • {assessment.steps} steps
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant={
                        assessment.status === "completed"
                          ? "default"
                          : assessment.status === "failed"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {assessment.status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No assessments yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
