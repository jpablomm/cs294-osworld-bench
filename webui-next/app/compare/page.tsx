"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useConfigs, useConfigComparison } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Select } from "@/components/ui/select";
import {
  Loader2,
  ArrowLeftRight,
  Trophy,
  TrendingUp,
  Clock,
  Zap,
  Target,
  CheckCircle2,
  Minus,
  Scale,
} from "lucide-react";
import type { ConfigSummary } from "@/lib/db/client";

export default function ComparePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get initial values from URL params
  const initialConfig1 = searchParams.get("config1") || "";
  const initialConfig2 = searchParams.get("config2") || "";

  const [config1Hash, setConfig1Hash] = useState<string>(initialConfig1);
  const [config2Hash, setConfig2Hash] = useState<string>(initialConfig2);

  const { data: configsData, isLoading: configsLoading } = useConfigs();
  const {
    data: comparison,
    isLoading: comparisonLoading,
    error: comparisonError,
  } = useConfigComparison(
    config1Hash || null,
    config2Hash || null
  );

  const configs = configsData?.configs || [];

  // Update URL when configs change
  const updateUrl = (c1: string, c2: string) => {
    const params = new URLSearchParams();
    if (c1) params.set("config1", c1);
    if (c2) params.set("config2", c2);
    const newUrl = params.toString() ? `?${params.toString()}` : "";
    router.replace(`/compare${newUrl}`, { scroll: false });
  };

  const handleConfig1Change = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setConfig1Hash(value);
    updateUrl(value, config2Hash);
  };

  const handleConfig2Change = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setConfig2Hash(value);
    updateUrl(config1Hash, value);
  };

  const swapConfigs = () => {
    const temp = config1Hash;
    setConfig1Hash(config2Hash);
    setConfig2Hash(temp);
    updateUrl(config2Hash, temp);
  };

  // Get display name for a config
  const getConfigDisplayName = (config: ConfigSummary) => {
    const name = config.config?.agent_name || "Unknown Agent";
    const model = config.config?.model || "";
    return model ? `${name} (${model})` : name;
  };

  // Determine winner for a metric (higher is better for success_rate, lower for steps/time)
  const getMetricWinner = (
    val1: number | null,
    val2: number | null,
    higherIsBetter: boolean
  ): "config1" | "config2" | "tie" => {
    if (val1 === null || val2 === null) return "tie";
    if (val1 === val2) return "tie";
    if (higherIsBetter) {
      return val1 > val2 ? "config1" : "config2";
    } else {
      return val1 < val2 ? "config1" : "config2";
    }
  };

  return (
    <div className="container max-w-6xl mx-auto py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Scale className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">Compare Configs</h1>
          </div>
          <p className="text-muted-foreground">
            Select two agent configurations to compare their performance side-by-side
          </p>
        </div>

        {/* Config Selectors */}
        <Card>
          <CardHeader>
            <CardTitle>Select Configurations</CardTitle>
            <CardDescription>
              Choose two different agent configurations to compare
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              {/* Config 1 Selector */}
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">Configuration 1</label>
                <Select
                  value={config1Hash}
                  onChange={handleConfig1Change}
                  disabled={configsLoading}
                >
                  <option value="">Select first config...</option>
                  {configs.map((config) => (
                    <option
                      key={config.config_hash}
                      value={config.config_hash}
                      disabled={config.config_hash === config2Hash}
                    >
                      [{config.config_hash}] {getConfigDisplayName(config)} ({config.total_runs} runs)
                    </option>
                  ))}
                </Select>
              </div>

              {/* Swap Button */}
              <Button
                variant="outline"
                size="icon"
                className="mt-6"
                onClick={swapConfigs}
                disabled={!config1Hash || !config2Hash}
              >
                <ArrowLeftRight className="h-4 w-4" />
              </Button>

              {/* Config 2 Selector */}
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">Configuration 2</label>
                <Select
                  value={config2Hash}
                  onChange={handleConfig2Change}
                  disabled={configsLoading}
                >
                  <option value="">Select second config...</option>
                  {configs.map((config) => (
                    <option
                      key={config.config_hash}
                      value={config.config_hash}
                      disabled={config.config_hash === config1Hash}
                    >
                      [{config.config_hash}] {getConfigDisplayName(config)} ({config.total_runs} runs)
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            {configsLoading && (
              <div className="flex items-center justify-center py-4 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Loading configurations...
              </div>
            )}
          </CardContent>
        </Card>

        {/* Loading State */}
        {comparisonLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error State */}
        {comparisonError && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <p className="text-destructive">
                Failed to load comparison: {comparisonError instanceof Error ? comparisonError.message : "Unknown error"}
              </p>
            </CardContent>
          </Card>
        )}

        {/* No Selection State */}
        {(!config1Hash || !config2Hash) && !comparisonLoading && (
          <Card>
            <CardContent className="py-12">
              <p className="text-center text-muted-foreground">
                Select two configurations above to see the comparison
              </p>
            </CardContent>
          </Card>
        )}

        {/* Comparison Results */}
        {comparison && !comparisonLoading && (
          <>
            {/* Summary Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="h-5 w-5 text-yellow-500" />
                  Head-to-Head Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-8 text-center">
                  {/* Config 1 Wins */}
                  <div>
                    <div className="text-4xl font-bold text-primary">
                      {comparison.summary.config1_wins}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {comparison.config1.config?.agent_name || "Config 1"} Wins
                    </div>
                  </div>

                  {/* Ties */}
                  <div>
                    <div className="text-4xl font-bold text-muted-foreground">
                      {comparison.summary.ties}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">Ties</div>
                  </div>

                  {/* Config 2 Wins */}
                  <div>
                    <div className="text-4xl font-bold text-primary">
                      {comparison.summary.config2_wins}
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {comparison.config2.config?.agent_name || "Config 2"} Wins
                    </div>
                  </div>
                </div>

                <Separator className="my-6" />

                <div className="text-center text-sm text-muted-foreground">
                  {comparison.summary.common_tasks} tasks compared head-to-head
                </div>
              </CardContent>
            </Card>

            {/* Side-by-Side Metrics */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Config 1 */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">
                      {comparison.config1.config?.agent_name || "Config 1"}
                    </CardTitle>
                    <Badge variant="outline" className="font-mono">
                      {comparison.config1.config_hash}
                    </Badge>
                  </div>
                  {comparison.config1.config?.model && (
                    <CardDescription>
                      Model: {comparison.config1.config.model}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  <MetricRow
                    icon={<TrendingUp className="h-4 w-4" />}
                    label="Success Rate"
                    value={`${comparison.config1.success_rate}%`}
                    winner={getMetricWinner(
                      comparison.config1.success_rate,
                      comparison.config2.success_rate,
                      true
                    )}
                    side="config1"
                  />
                  <MetricRow
                    icon={<Zap className="h-4 w-4" />}
                    label="Avg Steps"
                    value={comparison.config1.avg_steps.toString()}
                    winner={getMetricWinner(
                      comparison.config1.avg_steps,
                      comparison.config2.avg_steps,
                      false
                    )}
                    side="config1"
                  />
                  <MetricRow
                    icon={<Clock className="h-4 w-4" />}
                    label="Avg Time"
                    value={`${comparison.config1.avg_time_sec}s`}
                    winner={getMetricWinner(
                      comparison.config1.avg_time_sec,
                      comparison.config2.avg_time_sec,
                      false
                    )}
                    side="config1"
                  />
                  <MetricRow
                    icon={<Target className="h-4 w-4" />}
                    label="Tasks Attempted"
                    value={comparison.config1.tasks_attempted.toString()}
                    winner="tie"
                    side="config1"
                  />
                  <MetricRow
                    icon={<Target className="h-4 w-4" />}
                    label="Total Runs"
                    value={comparison.config1.total_runs.toString()}
                    winner="tie"
                    side="config1"
                  />
                </CardContent>
              </Card>

              {/* Config 2 */}
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">
                      {comparison.config2.config?.agent_name || "Config 2"}
                    </CardTitle>
                    <Badge variant="outline" className="font-mono">
                      {comparison.config2.config_hash}
                    </Badge>
                  </div>
                  {comparison.config2.config?.model && (
                    <CardDescription>
                      Model: {comparison.config2.config.model}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  <MetricRow
                    icon={<TrendingUp className="h-4 w-4" />}
                    label="Success Rate"
                    value={`${comparison.config2.success_rate}%`}
                    winner={getMetricWinner(
                      comparison.config1.success_rate,
                      comparison.config2.success_rate,
                      true
                    )}
                    side="config2"
                  />
                  <MetricRow
                    icon={<Zap className="h-4 w-4" />}
                    label="Avg Steps"
                    value={comparison.config2.avg_steps.toString()}
                    winner={getMetricWinner(
                      comparison.config1.avg_steps,
                      comparison.config2.avg_steps,
                      false
                    )}
                    side="config2"
                  />
                  <MetricRow
                    icon={<Clock className="h-4 w-4" />}
                    label="Avg Time"
                    value={`${comparison.config2.avg_time_sec}s`}
                    winner={getMetricWinner(
                      comparison.config1.avg_time_sec,
                      comparison.config2.avg_time_sec,
                      false
                    )}
                    side="config2"
                  />
                  <MetricRow
                    icon={<Target className="h-4 w-4" />}
                    label="Tasks Attempted"
                    value={comparison.config2.tasks_attempted.toString()}
                    winner="tie"
                    side="config2"
                  />
                  <MetricRow
                    icon={<Target className="h-4 w-4" />}
                    label="Total Runs"
                    value={comparison.config2.total_runs.toString()}
                    winner="tie"
                    side="config2"
                  />
                </CardContent>
              </Card>
            </div>

            {/* Per-Task Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Per-Task Breakdown</CardTitle>
                <CardDescription>
                  Head-to-head comparison for each task
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-2 font-medium">Task ID</th>
                        <th className="text-left py-3 px-2 font-medium">Domain</th>
                        <th className="text-center py-3 px-2 font-medium" colSpan={3}>
                          {comparison.config1.config?.agent_name || "Config 1"}
                        </th>
                        <th className="text-center py-3 px-2 font-medium" colSpan={3}>
                          {comparison.config2.config?.agent_name || "Config 2"}
                        </th>
                        <th className="text-center py-3 px-2 font-medium">Winner</th>
                      </tr>
                      <tr className="border-b text-xs text-muted-foreground">
                        <th></th>
                        <th></th>
                        <th className="text-center py-1 px-1">Runs</th>
                        <th className="text-center py-1 px-1">Success</th>
                        <th className="text-center py-1 px-1">Steps</th>
                        <th className="text-center py-1 px-1">Runs</th>
                        <th className="text-center py-1 px-1">Success</th>
                        <th className="text-center py-1 px-1">Steps</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.task_breakdown.map((task) => (
                        <tr key={task.task_id} className="border-b last:border-0 hover:bg-muted/50">
                          <td className="py-2 px-2 font-mono text-xs max-w-[200px] truncate">
                            {task.task_id}
                          </td>
                          <td className="py-2 px-2">
                            <Badge variant="outline" className="text-xs">
                              {task.domain || "N/A"}
                            </Badge>
                          </td>
                          {/* Config 1 stats */}
                          <td className="py-2 px-1 text-center">
                            {task.config1_runs || "-"}
                          </td>
                          <td className="py-2 px-1 text-center">
                            {task.config1_runs > 0 ? (
                              <span
                                className="font-medium"
                                style={{
                                  color:
                                    task.config1_success_rate >= 50
                                      ? "var(--success)"
                                      : "var(--destructive)",
                                }}
                              >
                                {task.config1_success_rate}%
                              </span>
                            ) : (
                              "-"
                            )}
                          </td>
                          <td className="py-2 px-1 text-center">
                            {task.config1_runs > 0 ? task.config1_avg_steps : "-"}
                          </td>
                          {/* Config 2 stats */}
                          <td className="py-2 px-1 text-center">
                            {task.config2_runs || "-"}
                          </td>
                          <td className="py-2 px-1 text-center">
                            {task.config2_runs > 0 ? (
                              <span
                                className="font-medium"
                                style={{
                                  color:
                                    task.config2_success_rate >= 50
                                      ? "var(--success)"
                                      : "var(--destructive)",
                                }}
                              >
                                {task.config2_success_rate}%
                              </span>
                            ) : (
                              "-"
                            )}
                          </td>
                          <td className="py-2 px-1 text-center">
                            {task.config2_runs > 0 ? task.config2_avg_steps : "-"}
                          </td>
                          {/* Winner */}
                          <td className="py-2 px-2 text-center">
                            {task.winner === "config1" ? (
                              <Badge variant="outline" className="text-xs bg-primary/10">
                                1
                              </Badge>
                            ) : task.winner === "config2" ? (
                              <Badge variant="outline" className="text-xs bg-primary/10">
                                2
                              </Badge>
                            ) : (
                              <Minus className="h-4 w-4 text-muted-foreground mx-auto" />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {comparison.task_breakdown.length === 0 && (
                  <p className="text-center text-muted-foreground py-8">
                    No tasks to compare
                  </p>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

// Helper component for metric rows with winner highlighting
function MetricRow({
  icon,
  label,
  value,
  winner,
  side,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  winner: "config1" | "config2" | "tie";
  side: "config1" | "config2";
}) {
  const isWinner = winner === side;
  const isLoser = winner !== "tie" && winner !== side;

  return (
    <div
      className={`flex items-center justify-between py-2 px-3 rounded-lg ${
        isWinner ? "bg-primary/10" : isLoser ? "bg-muted/50" : ""
      }`}
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={`font-medium ${isWinner ? "text-primary" : ""}`}>
          {value}
        </span>
        {isWinner && <CheckCircle2 className="h-4 w-4 text-primary" />}
      </div>
    </div>
  );
}
