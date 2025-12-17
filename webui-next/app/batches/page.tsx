"use client";

import { useState } from "react";
import Link from "next/link";
import { useBatches } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Select } from "@/components/ui/select";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  Layers,
  Activity,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function BatchesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data, isLoading } = useBatches({
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 100,
  });

  const batches = data?.batches || [];
  const total = data?.total || 0;

  // Calculate summary stats
  const runningCount = batches.filter((b) => b.status === "running").length;
  const completedCount = batches.filter((b) => b.status === "completed").length;

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Batches</h1>
            <p className="text-muted-foreground">
              All assessment batches with aggregate statistics
            </p>
          </div>
          <Link href="/launch">
            <Button>
              <Layers className="mr-2 h-4 w-4" />
              New Batch
            </Button>
          </Link>
        </div>

        {/* Summary Cards */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Batches</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{total}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Running</CardTitle>
              <Clock className="h-4 w-4 text-warning" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-warning">{runningCount}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Completed</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-success" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-success">{completedCount}</div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <CardTitle>Batch List</CardTitle>
            <CardDescription>
              Click on a batch to view detailed assessments
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Status:</span>
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-[150px]"
                >
                  <option value="all">All</option>
                  <option value="running">Running</option>
                  <option value="completed">Completed</option>
                  <option value="partial">Partial</option>
                </Select>
              </div>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : batches.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <p className="text-sm text-muted-foreground mb-2">No batches found</p>
                <p className="text-xs text-muted-foreground">
                  Launch your first batch assessment to get started
                </p>
              </div>
            ) : (
              <div className="relative w-full overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Status</TableHead>
                      <TableHead>Batch ID</TableHead>
                      <TableHead className="text-center">Tasks</TableHead>
                      <TableHead className="text-center">Runs</TableHead>
                      <TableHead className="text-center">Success Rate</TableHead>
                      <TableHead className="text-center">Avg Steps</TableHead>
                      <TableHead className="text-center">Avg Time</TableHead>
                      <TableHead>Domains</TableHead>
                      <TableHead className="text-right">Started</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {batches.map((batch) => (
                      <TableRow key={batch.batch_id}>
                        {/* Status */}
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {batch.status === "completed" ? (
                              <CheckCircle2 className="h-4 w-4 text-success" />
                            ) : batch.status === "running" ? (
                              <Clock className="h-4 w-4 text-warning animate-pulse" />
                            ) : (
                              <XCircle className="h-4 w-4 text-muted-foreground" />
                            )}
                            <Badge
                              variant={
                                batch.status === "completed"
                                  ? "default"
                                  : batch.status === "running"
                                  ? "secondary"
                                  : "outline"
                              }
                              className="text-xs"
                            >
                              {batch.status}
                            </Badge>
                          </div>
                        </TableCell>

                        {/* Batch ID */}
                        <TableCell className="font-mono text-xs max-w-[200px]">
                          <div className="truncate" title={batch.batch_id}>
                            {batch.batch_id}
                          </div>
                        </TableCell>

                        {/* Tasks */}
                        <TableCell className="text-center">
                          <Badge variant="outline" className="text-xs">
                            {batch.task_count}
                          </Badge>
                        </TableCell>

                        {/* Runs */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">
                            {batch.completed_runs}/{batch.total_runs}
                          </span>
                          {batch.running_runs > 0 && (
                            <span className="text-xs text-warning ml-1">
                              ({batch.running_runs} running)
                            </span>
                          )}
                        </TableCell>

                        {/* Success Rate */}
                        <TableCell className="text-center">
                          <span
                            className="font-semibold"
                            style={{
                              color: batch.success_rate >= 50 ? "var(--success)" : "var(--destructive)",
                            }}
                          >
                            {batch.success_rate.toFixed(1)}%
                          </span>
                        </TableCell>

                        {/* Avg Steps */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">
                            {batch.avg_steps.toFixed(1)}
                          </span>
                        </TableCell>

                        {/* Avg Time */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">
                            {batch.avg_time_sec.toFixed(0)}s
                          </span>
                        </TableCell>

                        {/* Domains */}
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {batch.domains.slice(0, 2).map((domain) => (
                              <Badge key={domain} variant="outline" className="text-xs">
                                {domain}
                              </Badge>
                            ))}
                            {batch.domains.length > 2 && (
                              <Badge variant="outline" className="text-xs">
                                +{batch.domains.length - 2}
                              </Badge>
                            )}
                          </div>
                        </TableCell>

                        {/* Started */}
                        <TableCell className="text-right">
                          <span className="text-xs text-muted-foreground">
                            {batch.started_at
                              ? formatDistanceToNow(new Date(batch.started_at), {
                                  addSuffix: true,
                                })
                              : "—"}
                          </span>
                        </TableCell>

                        {/* Actions */}
                        <TableCell className="text-right">
                          <Link href={`/batch/${batch.batch_id}`}>
                            <Button variant="ghost" size="sm">
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
