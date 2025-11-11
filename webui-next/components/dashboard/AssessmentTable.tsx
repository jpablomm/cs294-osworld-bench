"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CheckCircle2, XCircle, Clock, ExternalLink } from "lucide-react";
import type { Assessment } from "@/lib/api/types";
import { formatDistanceToNow } from "date-fns";

interface AssessmentTableProps {
  assessments: Assessment[];
  isLoading?: boolean;
}

export function AssessmentTable({ assessments, isLoading }: AssessmentTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-sm text-muted-foreground">Loading assessments...</p>
      </div>
    );
  }

  if (assessments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-sm text-muted-foreground mb-2">No assessments found</p>
        <p className="text-xs text-muted-foreground">
          Launch your first assessment to get started
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead>
            <TableHead>Task ID</TableHead>
            <TableHead>Domain</TableHead>
            <TableHead className="text-center">Steps</TableHead>
            <TableHead className="text-center">Success</TableHead>
            <TableHead className="text-center">Score</TableHead>
            <TableHead className="text-right">Time</TableHead>
            <TableHead className="text-right">Started</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {assessments.map((assessment) => (
            <TableRow key={assessment.id}>
              {/* Status Icon */}
              <TableCell>
                <div className="flex items-center gap-2">
                  {assessment.status === "completed" && assessment.success ? (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  ) : assessment.status === "failed" ? (
                    <XCircle className="h-4 w-4 text-destructive" />
                  ) : (
                    <Clock className="h-4 w-4 text-warning animate-pulse" />
                  )}
                  <Badge
                    variant={
                      assessment.status === "completed"
                        ? "default"
                        : assessment.status === "failed"
                        ? "destructive"
                        : "secondary"
                    }
                    className="text-xs"
                  >
                    {assessment.status}
                  </Badge>
                </div>
              </TableCell>

              {/* Task ID */}
              <TableCell className="font-medium max-w-[200px]">
                <div className="truncate" title={assessment.task_id}>
                  {assessment.task_id}
                </div>
              </TableCell>

              {/* Domain */}
              <TableCell>
                <Badge variant="outline" className="text-xs">
                  {assessment.domain || "N/A"}
                </Badge>
              </TableCell>

              {/* Steps */}
              <TableCell className="text-center">
                <span className="font-mono text-sm">{assessment.steps}</span>
              </TableCell>

              {/* Success */}
              <TableCell className="text-center">
                {assessment.status === "completed" ? (
                  assessment.success ? (
                    <CheckCircle2 className="h-4 w-4 text-success mx-auto" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive mx-auto" />
                  )
                ) : (
                  <span className="text-muted-foreground text-xs">—</span>
                )}
              </TableCell>

              {/* Evaluation Score */}
              <TableCell className="text-center">
                {assessment.evaluation_score !== null &&
                assessment.evaluation_score !== undefined ? (
                  <span className="font-mono text-sm">
                    {assessment.evaluation_score.toFixed(2)}
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xs">—</span>
                )}
              </TableCell>

              {/* Time */}
              <TableCell className="text-right">
                {assessment.time_sec ? (
                  <span className="font-mono text-sm">
                    {Math.round(assessment.time_sec)}s
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xs">—</span>
                )}
              </TableCell>

              {/* Started At */}
              <TableCell className="text-right">
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(assessment.started_at), {
                    addSuffix: true,
                  })}
                </span>
              </TableCell>

              {/* Actions */}
              <TableCell className="text-right">
                <Link href={`/assessment/${assessment.id}`}>
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
  );
}

