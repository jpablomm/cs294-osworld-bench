"use client";

import { useState, useMemo } from "react";
import { useStats, useAssessments } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AssessmentTable } from "@/components/dashboard/AssessmentTable";
import {
  Activity,
  CheckCircle2,
  TrendingUp,
  Clock,
  Download,
} from "lucide-react";
import type { AssessmentStatus } from "@/lib/api/types";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useStats();

  // Filters
  const [statusFilter, setStatusFilter] = useState<AssessmentStatus | "all">("all");
  const [domainFilter, setDomainFilter] = useState<string | "all">("all");
  const [limit, setLimit] = useState(50);

  const { data, isLoading: assessmentsLoading } = useAssessments({
    limit,
    status: statusFilter !== "all" ? statusFilter : undefined,
    domain: domainFilter !== "all" ? domainFilter : undefined,
  });

  // Get unique domains from assessments
  const domains = useMemo(() => {
    if (!data?.assessments) return [];
    const domainSet = new Set(
      data.assessments.map((a) => a.domain).filter((d): d is string => d !== null)
    );
    return Array.from(domainSet).sort();
  }, [data?.assessments]);

  const handleExport = () => {
    if (!data?.assessments) return;

    const headers = [
      "ID",
      "Task ID",
      "Domain",
      "Status",
      "Steps",
      "Success",
      "Score",
      "Time (s)",
      "Started At",
      "Completed At",
    ];

    const rows = data.assessments.map((a) => [
      a.id,
      a.task_id,
      a.domain || "",
      a.status,
      a.steps,
      a.success,
      a.evaluation_score || "",
      a.time_sec || "",
      a.started_at,
      a.completed_at || "",
    ]);

    const csv = [
      headers.join(","),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(",")),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `osworld-assessments-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (statsError) {
    return (
      <div className="container max-w-6xl mx-auto py-8">
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

  const hasActiveFilters = statusFilter !== "all" || domainFilter !== "all";

  return (
    <div className="container max-w-6xl mx-auto py-8">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground">
              OSWorld agent assessments and performance
            </p>
          </div>
          <Button onClick={handleExport} variant="outline" size="sm" disabled={!data?.assessments}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>

        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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

        {/* Compact Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-4 py-2">
          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Status:</span>
            <div className="flex gap-1">
              {(["all", "completed", "running", "failed"] as const).map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant={statusFilter === status ? "default" : "ghost"}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setStatusFilter(status)}
                >
                  {status === "all" ? "All" : status.charAt(0).toUpperCase() + status.slice(1)}
                </Button>
              ))}
            </div>
          </div>

          {/* Domain Filter */}
          {domains.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Domain:</span>
              <div className="flex gap-1 flex-wrap">
                <Button
                  size="sm"
                  variant={domainFilter === "all" ? "default" : "ghost"}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setDomainFilter("all")}
                >
                  All
                </Button>
                {domains.map((domain) => (
                  <Button
                    key={domain}
                    size="sm"
                    variant={domainFilter === domain ? "default" : "ghost"}
                    className="h-7 px-2.5 text-xs"
                    onClick={() => setDomainFilter(domain)}
                  >
                    {domain}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Page Size */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Show:</span>
            <div className="flex gap-1">
              {[25, 50, 100].map((value) => (
                <Button
                  key={value}
                  size="sm"
                  variant={limit === value ? "default" : "ghost"}
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setLimit(value)}
                >
                  {value}
                </Button>
              ))}
            </div>
          </div>

          {/* Clear Filters */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2.5 text-xs text-muted-foreground"
              onClick={() => {
                setStatusFilter("all");
                setDomainFilter("all");
              }}
            >
              Clear filters
            </Button>
          )}
        </div>

        {/* Results Table */}
        <Card>
          <CardHeader className="py-4">
            <CardTitle className="text-base">
              Assessments{" "}
              {data?.assessments && (
                <span className="text-muted-foreground font-normal">
                  ({data.assessments.length})
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <AssessmentTable
              assessments={data?.assessments || []}
              isLoading={assessmentsLoading}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
