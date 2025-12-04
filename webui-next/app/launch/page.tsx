"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTasks, useLaunchAssessment, useTaskStats } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  PlayCircle,
  Search,
  Loader2,
  CheckCircle2,
  TrendingUp,
  Clock,
  Zap,
  BarChart3,
  FlaskConical,
} from "lucide-react";
import type { Task } from "@/lib/api/types";

export default function LaunchPage() {
  const router = useRouter();
  const { data: tasks, isLoading: tasksLoading } = useTasks();
  const launchMutation = useLaunchAssessment();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  // Configuration state with validation
  const [maxSteps, setMaxSteps] = useState(15);
  const [numRuns, setNumRuns] = useState(1);

  // Fetch stats for selected task
  const { data: taskStats, isLoading: statsLoading } = useTaskStats(
    selectedTask?.id || null
  );

  // Get unique domains
  const domains = useMemo(() => {
    if (!tasks) return [];
    const domainSet = new Set(tasks.map((t) => t.domain));
    return Array.from(domainSet).sort();
  }, [tasks]);

  // Filter tasks
  const filteredTasks = useMemo(() => {
    if (!tasks) return [];

    let filtered = tasks;

    // Filter by domain
    if (selectedDomain) {
      filtered = filtered.filter((t) => t.domain === selectedDomain);
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.id?.toLowerCase().includes(query) ||
          t.instruction?.toLowerCase().includes(query) ||
          t.domain?.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [tasks, selectedDomain, searchQuery]);

  // Input validation
  const handleMaxStepsChange = (value: string) => {
    const num = parseInt(value);
    if (isNaN(num)) return;
    setMaxSteps(Math.min(50, Math.max(1, num)));
  };

  const handleNumRunsChange = (value: string) => {
    const num = parseInt(value);
    if (isNaN(num)) return;
    setNumRuns(Math.min(10, Math.max(1, num)));
  };

  const handleLaunch = useCallback(async () => {
    if (!selectedTask || launchMutation.isPending) return;

    try {
      const result = await launchMutation.mutateAsync({
        task_id: selectedTask.id,
        domain: selectedTask.domain,
        max_steps: maxSteps,
        vm_image: "osworld-gnome-v6",
        num_runs: numRuns,
      });

      // Redirect based on number of runs
      if (numRuns === 1 && result.assessment_id) {
        router.push(`/assessment/${result.assessment_id}/live`);
      } else if (result.batch_id) {
        router.push(`/batch/${result.batch_id}`);
      }
    } catch (error) {
      console.error("Launch failed:", error);
    }
  }, [selectedTask, launchMutation, maxSteps, numRuns, router]);

  // Keyboard shortcut: Enter to launch
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter" && selectedTask && !launchMutation.isPending) {
        // Don't trigger if typing in an input
        if (
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLSelectElement
        ) {
          return;
        }
        handleLaunch();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedTask, launchMutation.isPending, handleLaunch]);

  return (
    <div className="container max-w-5xl mx-auto py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Launch Assessment</h1>
          <p className="text-muted-foreground">
            Select a task and configure the assessment parameters
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left: Task Selector */}
          <div className="lg:col-span-2 space-y-4">
            {/* Search and Filters */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Select Task</CardTitle>
                    <CardDescription>
                      Choose an OSWorld task to assess the agent on
                    </CardDescription>
                  </div>
                  {/* Task count badge */}
                  <Badge variant="secondary" className="text-xs">
                    {filteredTasks.length} {filteredTasks.length === 1 ? "task" : "tasks"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Search tasks by name or instruction..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>

                {/* Domain Filter */}
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant={selectedDomain === null ? "default" : "outline"}
                    onClick={() => setSelectedDomain(null)}
                  >
                    All Domains
                  </Button>
                  {domains.map((domain) => (
                    <Button
                      key={domain}
                      size="sm"
                      variant={selectedDomain === domain ? "default" : "outline"}
                      onClick={() => setSelectedDomain(domain)}
                    >
                      {domain}
                    </Button>
                  ))}
                </div>

                <Separator />

                {/* Task List */}
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                  {tasksLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : filteredTasks.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No tasks found. Try a different search or domain filter.
                    </p>
                  ) : (
                    filteredTasks.map((task) => (
                      <button
                        key={task.id}
                        onClick={() => setSelectedTask(task)}
                        className={`w-full text-left p-4 rounded-lg border transition-colors ${
                          selectedTask?.id === task.id
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50 hover:bg-accent/50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-medium text-sm">{task.id}</p>
                              <Badge variant="secondary" className="text-xs">
                                {task.domain}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-2">
                              {task.instruction}
                            </p>
                          </div>
                          {selectedTask?.id === task.id && (
                            <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0" />
                          )}
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: Configuration */}
          <div className="space-y-4">
            {/* Configuration Card */}
            <Card>
              <CardHeader>
                <CardTitle>Configuration</CardTitle>
                <CardDescription>Assessment parameters</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Max Steps */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Steps</label>
                  <Input
                    type="number"
                    min={1}
                    max={50}
                    value={maxSteps}
                    onChange={(e) => handleMaxStepsChange(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum number of agent actions (1-50)
                  </p>
                </div>

                {/* Number of Runs */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Number of Runs</label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={numRuns}
                    onChange={(e) => handleNumRunsChange(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Run task multiple times for rolling average (1-10)
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Selected Task Preview with Stats */}
            {selectedTask && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Selected Task</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Task ID</p>
                    <p className="text-sm font-medium">{selectedTask.id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Domain</p>
                    <Badge variant="secondary">{selectedTask.domain}</Badge>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Instruction</p>
                    <p className="text-sm">{selectedTask.instruction}</p>
                  </div>

                  {/* Evaluator Info */}
                  {selectedTask.evaluator && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                        <FlaskConical className="h-3 w-3" />
                        Evaluation Method
                      </p>
                      <Badge variant="outline" className="font-mono text-xs">
                        {selectedTask.evaluator.func}
                      </Badge>
                    </div>
                  )}

                  {/* Historical Stats */}
                  {statsLoading ? (
                    <div className="pt-2">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : taskStats && taskStats.total_runs > 0 ? (
                    <>
                      <Separator />
                      <div>
                        <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                          <BarChart3 className="h-3 w-3" />
                          Historical Performance ({taskStats.total_runs} runs)
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="flex items-center gap-1.5 text-xs">
                            <TrendingUp className="h-3 w-3 text-success" />
                            <span className="text-muted-foreground">Success:</span>
                            <span className="font-medium">{taskStats.success_rate}%</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs">
                            <Zap className="h-3 w-3 text-primary" />
                            <span className="text-muted-foreground">Avg steps:</span>
                            <span className="font-medium">{taskStats.avg_steps}</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs">
                            <Clock className="h-3 w-3 text-warning" />
                            <span className="text-muted-foreground">Avg time:</span>
                            <span className="font-medium">{taskStats.avg_time_sec}s</span>
                          </div>
                        </div>
                      </div>
                    </>
                  ) : taskStats?.total_runs === 0 ? (
                    <>
                      <Separator />
                      <p className="text-xs text-muted-foreground italic">
                        No previous runs for this task
                      </p>
                    </>
                  ) : null}
                </CardContent>
              </Card>
            )}

            {/* Launch Button */}
            <Button
              size="lg"
              className="w-full"
              disabled={!selectedTask || launchMutation.isPending}
              onClick={handleLaunch}
            >
              {launchMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Launching...
                </>
              ) : (
                <>
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Launch Assessment
                </>
              )}
            </Button>

            {/* Keyboard hint */}
            {selectedTask && !launchMutation.isPending && (
              <p className="text-xs text-muted-foreground text-center">
                Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-mono">Enter</kbd> to launch
              </p>
            )}

            {launchMutation.isError && (
              <p className="text-sm text-destructive">
                Failed to launch assessment. Please try again.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
