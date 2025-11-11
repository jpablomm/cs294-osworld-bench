"use client";

import { useState, useMemo } from "react";
import { useAssessments } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AssessmentTable } from "@/components/dashboard/AssessmentTable";
import { Download, Filter } from "lucide-react";
import type { AssessmentStatus } from "@/lib/api/types";

export default function ResultsPage() {
  const [statusFilter, setStatusFilter] = useState<AssessmentStatus | "all">("all");
  const [domainFilter, setDomainFilter] = useState<string | "all">("all");
  const [limit, setLimit] = useState(50);

  const { data, isLoading } = useAssessments({
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

    // Create CSV content
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

    // Download
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `osworld-assessments-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Assessment Results</h1>
            <p className="text-muted-foreground">
              Browse and filter all assessment runs
            </p>
          </div>
          <Button onClick={handleExport} variant="outline" disabled={!data?.assessments}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  Filters
                </CardTitle>
                <CardDescription>
                  Filter assessments by status, domain, or other criteria
                </CardDescription>
              </div>
              {(statusFilter !== "all" || domainFilter !== "all") && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setStatusFilter("all");
                    setDomainFilter("all");
                  }}
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Status Filter */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant={statusFilter === "all" ? "default" : "outline"}
                  onClick={() => setStatusFilter("all")}
                >
                  All
                </Button>
                <Button
                  size="sm"
                  variant={statusFilter === "completed" ? "default" : "outline"}
                  onClick={() => setStatusFilter("completed")}
                >
                  Completed
                </Button>
                <Button
                  size="sm"
                  variant={statusFilter === "running" ? "default" : "outline"}
                  onClick={() => setStatusFilter("running")}
                >
                  Running
                </Button>
                <Button
                  size="sm"
                  variant={statusFilter === "failed" ? "default" : "outline"}
                  onClick={() => setStatusFilter("failed")}
                >
                  Failed
                </Button>
              </div>
            </div>

            {/* Domain Filter */}
            {domains.length > 0 && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Domain</label>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant={domainFilter === "all" ? "default" : "outline"}
                    onClick={() => setDomainFilter("all")}
                  >
                    All Domains
                  </Button>
                  {domains.map((domain) => (
                    <Button
                      key={domain}
                      size="sm"
                      variant={domainFilter === domain ? "default" : "outline"}
                      onClick={() => setDomainFilter(domain)}
                    >
                      {domain}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Results Per Page */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Results Per Page</label>
              <div className="flex gap-2">
                {[25, 50, 100, 200].map((value) => (
                  <Button
                    key={value}
                    size="sm"
                    variant={limit === value ? "default" : "outline"}
                    onClick={() => setLimit(value)}
                  >
                    {value}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results Table */}
        <Card>
          <CardHeader>
            <CardTitle>
              Results{" "}
              {data?.assessments && (
                <span className="text-muted-foreground font-normal">
                  ({data.assessments.length})
                </span>
              )}
            </CardTitle>
            <CardDescription>
              {statusFilter !== "all" && `Filtered by status: ${statusFilter}`}
              {domainFilter !== "all" && ` • Domain: ${domainFilter}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AssessmentTable
              assessments={data?.assessments || []}
              isLoading={isLoading}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

