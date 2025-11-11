"use client";

import { useState } from "react";
import { useGlobalLeaderboard } from "@/lib/api/queries";
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
import { Trophy, TrendingUp, Clock, Target, Award } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

type MetricType = "success_rate" | "avg_steps" | "avg_time_sec" | "avg_evaluation_score";

export default function LeaderboardPage() {
  const [metric, setMetric] = useState<MetricType>("success_rate");
  const [domainFilter, setDomainFilter] = useState<string | undefined>(undefined);

  const { data, isLoading } = useGlobalLeaderboard(metric, 50, domainFilter);

  const getMetricDisplay = (entry: any, metricType: MetricType) => {
    switch (metricType) {
      case "success_rate":
        return `${entry.success_rate.toFixed(1)}%`;
      case "avg_steps":
        return entry.avg_steps.toFixed(1);
      case "avg_time_sec":
        return `${entry.avg_time_sec.toFixed(1)}s`;
      case "avg_evaluation_score":
        return entry.avg_evaluation_score?.toFixed(3) || "N/A";
      default:
        return "—";
    }
  };

  const getMetricIcon = (metricType: MetricType) => {
    switch (metricType) {
      case "success_rate":
        return <Trophy className="h-4 w-4" />;
      case "avg_steps":
        return <Target className="h-4 w-4" />;
      case "avg_time_sec":
        return <Clock className="h-4 w-4" />;
      case "avg_evaluation_score":
        return <Award className="h-4 w-4" />;
    }
  };

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return (
        <Badge className="bg-yellow-500 hover:bg-yellow-600 text-white">
          🥇 #{rank}
        </Badge>
      );
    } else if (rank === 2) {
      return (
        <Badge className="bg-gray-400 hover:bg-gray-500 text-white">
          🥈 #{rank}
        </Badge>
      );
    } else if (rank === 3) {
      return (
        <Badge className="bg-orange-600 hover:bg-orange-700 text-white">
          🥉 #{rank}
        </Badge>
      );
    } else {
      return (
        <Badge variant="outline">
          #{rank}
        </Badge>
      );
    }
  };

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Leaderboard</h1>
          <p className="text-muted-foreground">
            Top performing assessments ranked by various metrics
          </p>
        </div>

        {/* Metric Selector */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Ranking Metric
            </CardTitle>
            <CardDescription>
              Select which metric to rank assessments by
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Metric Buttons */}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={metric === "success_rate" ? "default" : "outline"}
                onClick={() => setMetric("success_rate")}
              >
                <Trophy className="mr-2 h-4 w-4" />
                Success Rate
              </Button>
              <Button
                size="sm"
                variant={metric === "avg_steps" ? "default" : "outline"}
                onClick={() => setMetric("avg_steps")}
              >
                <Target className="mr-2 h-4 w-4" />
                Avg Steps
              </Button>
              <Button
                size="sm"
                variant={metric === "avg_time_sec" ? "default" : "outline"}
                onClick={() => setMetric("avg_time_sec")}
              >
                <Clock className="mr-2 h-4 w-4" />
                Avg Time
              </Button>
              <Button
                size="sm"
                variant={metric === "avg_evaluation_score" ? "default" : "outline"}
                onClick={() => setMetric("avg_evaluation_score")}
              >
                <Award className="mr-2 h-4 w-4" />
                Evaluation Score
              </Button>
            </div>

            {/* Domain Filter */}
            {/* <div className="space-y-2">
              <label className="text-sm font-medium">Filter by Domain</label>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={domainFilter === undefined ? "default" : "outline"}
                  onClick={() => setDomainFilter(undefined)}
                >
                  All Domains
                </Button>
              </div>
            </div> */}
          </CardContent>
        </Card>

        {/* Leaderboard Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getMetricIcon(metric)}
              Top Performers
            </CardTitle>
            <CardDescription>
              Ranked by {metric.replace(/_/g, " ")}
              {domainFilter && ` in ${domainFilter}`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <p className="text-sm text-muted-foreground">Loading leaderboard...</p>
              </div>
            ) : !data?.leaderboard || data.leaderboard.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <p className="text-sm text-muted-foreground mb-2">No entries yet</p>
                <p className="text-xs text-muted-foreground">
                  Complete assessments to appear on the leaderboard
                </p>
              </div>
            ) : (
              <div className="relative w-full overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[80px]">Rank</TableHead>
                      <TableHead>Task ID</TableHead>
                      <TableHead>Domain</TableHead>
                      <TableHead className="text-center">Runs</TableHead>
                      <TableHead className="text-center">Success Rate</TableHead>
                      <TableHead className="text-center">Avg Steps</TableHead>
                      <TableHead className="text-center">Avg Time</TableHead>
                      <TableHead className="text-right">
                        {metric === "avg_evaluation_score" ? "Score" : "Metric Value"}
                      </TableHead>
                      <TableHead className="text-right">Last Run</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.leaderboard.map((entry) => (
                      <TableRow key={entry.assessment_id}>
                        {/* Rank */}
                        <TableCell>{getRankBadge(entry.rank)}</TableCell>

                        {/* Task ID */}
                        <TableCell className="font-medium max-w-[200px]">
                          <div className="truncate" title={entry.task_id}>
                            {entry.task_id}
                          </div>
                        </TableCell>

                        {/* Domain */}
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {entry.domain}
                          </Badge>
                        </TableCell>

                        {/* Number of Runs */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">{entry.num_runs}</span>
                        </TableCell>

                        {/* Success Rate */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm" style={{ color: "var(--success)" }}>
                            {entry.success_rate.toFixed(1)}%
                          </span>
                        </TableCell>

                        {/* Avg Steps */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">
                            {entry.avg_steps.toFixed(1)}
                          </span>
                        </TableCell>

                        {/* Avg Time */}
                        <TableCell className="text-center">
                          <span className="font-mono text-sm">
                            {entry.avg_time_sec.toFixed(1)}s
                          </span>
                        </TableCell>

                        {/* Primary Metric Value */}
                        <TableCell className="text-right">
                          <span className="font-mono text-sm font-bold">
                            {getMetricDisplay(entry, metric)}
                          </span>
                        </TableCell>

                        {/* Timestamp */}
                        <TableCell className="text-right">
                          <span className="text-xs text-muted-foreground">
                            {formatDistanceToNow(new Date(entry.timestamp), {
                              addSuffix: true,
                            })}
                          </span>
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

