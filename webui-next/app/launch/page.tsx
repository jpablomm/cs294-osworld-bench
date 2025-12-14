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
  Check,
  X,
  TrendingUp,
  Clock,
  Zap,
  BarChart3,
  FlaskConical,
  Square,
  CheckSquare,
} from "lucide-react";
import type { Task } from "@/lib/api/types";

const MAX_TASKS_PER_BATCH = 20;

export default function LaunchPage() {
  const router = useRouter();
  const { data: tasks, isLoading: tasksLoading } = useTasks();
  const launchMutation = useLaunchAssessment();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  // Configuration state with validation
  const [maxSteps, setMaxSteps] = useState(15);
  const [numRuns, setNumRuns] = useState(1);
  const [model, setModel] = useState("gpt-5.1");

  // Available models for selection
  // Model names must match what white_agent/prompt_agent.py supports
  const availableModels = [
    { value: "gpt-5.1", label: "GPT-5.1", description: "OpenAI GPT-5.1 (recommended)" },
    { value: "gpt-5", label: "GPT-5", description: "OpenAI GPT-5" },
    { value: "gpt-5-mini-2025-08-07", label: "GPT-5 Mini", description: "OpenAI GPT-5 Mini (faster, cheaper)" },
    { value: "gpt-4o", label: "GPT-4o", description: "OpenAI GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini", description: "OpenAI GPT-4o Mini (faster, cheaper)" },
    { value: "claude-opus-4-5", label: "Claude Opus 4.5", description: "Anthropic Claude Opus 4.5 (most capable)" },
    { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5", description: "Anthropic Claude Sonnet 4.5" },
    { value: "claude-sonnet-4", label: "Claude Sonnet 4", description: "Anthropic Claude Sonnet 4" },
    { value: "qwen-vl-max", label: "Qwen VL Max", description: "Alibaba Qwen Vision-Language" },
    // Groq models (Llama 4 with vision)
    { value: "groq-llama4-scout", label: "Groq Llama 4 Scout", description: "Llama 4 Scout 17B - 750 t/s, vision" },
    { value: "groq-llama4-maverick", label: "Groq Llama 4 Maverick", description: "Llama 4 Maverick 17B - 600 t/s, vision (more capable)" },
    // Qwen3-VL on Vertex AI (requires deployment)
    { value: "qwen3-vl-235b-instruct", label: "Qwen3-VL 235B", description: "Qwen3-VL 235B on Vertex AI - vision, GUI automation" },
    { value: "qwen3-vl-30b-instruct", label: "Qwen3-VL 30B", description: "Qwen3-VL 30B on Vertex AI - faster, cheaper" },
    // Experimental models
    { value: "langchain-gpt-5.1", label: "⚗️ LangChain GPT-5.1", description: "EXPERIMENTAL: GPT-5.1 + web search", experimental: true },
  ];

  // Get selected tasks array from IDs
  const selectedTasks = useMemo(() => {
    if (!tasks) return [];
    return tasks.filter((t) => selectedTaskIds.has(t.id));
  }, [tasks, selectedTaskIds]);

  // Fetch stats for first selected task (for preview)
  const { data: taskStats, isLoading: statsLoading } = useTaskStats(
    selectedTasks.length === 1 ? selectedTasks[0]?.id : null
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

  // Selection helpers
  const toggleTaskSelection = useCallback((task: Task) => {
    setSelectedTaskIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(task.id)) {
        newSet.delete(task.id);
      } else if (newSet.size < MAX_TASKS_PER_BATCH) {
        newSet.add(task.id);
      }
      return newSet;
    });
  }, []);

  const selectAllTasks = useCallback(() => {
    const tasksToSelect = filteredTasks.slice(0, MAX_TASKS_PER_BATCH);
    setSelectedTaskIds(new Set(tasksToSelect.map((t) => t.id)));
  }, [filteredTasks]);

  const clearSelection = useCallback(() => {
    setSelectedTaskIds(new Set());
  }, []);

  const isTaskSelected = useCallback(
    (taskId: string) => selectedTaskIds.has(taskId),
    [selectedTaskIds]
  );

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
    if (selectedTasks.length === 0 || launchMutation.isPending) return;

    try {
      const result = await launchMutation.mutateAsync({
        task_ids: selectedTasks.map((t) => t.id),
        domain: selectedTasks[0]?.domain,
        max_steps: maxSteps,
        vm_image: "osworld-gnome-v6",
        num_runs: numRuns,
        model: model,
      });

      // Always redirect to batch view for multi-task or if batch_id is present
      if (result.batch_id) {
        router.push(`/batch/${result.batch_id}`);
      } else if (result.assessment_id) {
        router.push(`/assessment/${result.assessment_id}/live`);
      }
    } catch (error) {
      console.error("Launch failed:", error);
    }
  }, [selectedTasks, launchMutation, maxSteps, numRuns, model, router]);

  // Keyboard shortcut: Enter to launch
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter" && selectedTasks.length > 0 && !launchMutation.isPending) {
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
  }, [selectedTasks.length, launchMutation.isPending, handleLaunch]);

  return (
    <div className="container max-w-5xl mx-auto py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Launch Assessment</h1>
          <p className="text-muted-foreground">
            Select one or more tasks and configure the assessment parameters
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
                    <CardTitle>Select Tasks</CardTitle>
                    <CardDescription>
                      Choose one or more OSWorld tasks to assess the agent on
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

                {/* Selection Controls */}
                <div className="flex items-center justify-between">
                  <div className="text-sm text-muted-foreground">
                    {selectedTaskIds.size} task{selectedTaskIds.size !== 1 ? "s" : ""} selected
                    {selectedTaskIds.size >= MAX_TASKS_PER_BATCH && (
                      <span className="text-warning ml-2">(max {MAX_TASKS_PER_BATCH})</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={selectAllTasks}
                      disabled={
                        filteredTasks.length === 0 ||
                        (filteredTasks.length <= MAX_TASKS_PER_BATCH &&
                          filteredTasks.every((t) => selectedTaskIds.has(t.id)))
                      }
                    >
                      Select All ({Math.min(filteredTasks.length, MAX_TASKS_PER_BATCH)})
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={clearSelection}
                      disabled={selectedTaskIds.size === 0}
                    >
                      Clear
                    </Button>
                  </div>
                </div>

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
                      <div
                        key={task.id}
                        onClick={() => toggleTaskSelection(task)}
                        className={`w-full text-left p-4 rounded-lg border transition-colors cursor-pointer ${
                          isTaskSelected(task.id)
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50 hover:bg-accent/50"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          {/* Checkbox */}
                          <div
                            className={`mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                              isTaskSelected(task.id)
                                ? "bg-primary border-primary"
                                : "border-muted-foreground/30"
                            }`}
                          >
                            {isTaskSelected(task.id) && (
                              <Check className="h-3 w-3 text-primary-foreground" />
                            )}
                          </div>

                          {/* Task content */}
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
                        </div>
                      </div>
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
                  <label className="text-sm font-medium">Runs per Task</label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={numRuns}
                    onChange={(e) => handleNumRunsChange(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Run each task multiple times (1-10)
                  </p>
                </div>

                {/* Model Selection */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {availableModels.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    {availableModels.find((m) => m.value === model)?.description}
                  </p>
                  {availableModels.find((m) => m.value === model)?.experimental && (
                    <p className="text-xs text-yellow-600 dark:text-yellow-400">
                      ⚠️ Experimental: Not recommended for production use
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Selected Tasks Preview */}
            {selectedTasks.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">
                    Selected Tasks ({selectedTasks.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Task list */}
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {selectedTasks.map((task, index) => (
                      <div
                        key={task.id}
                        className="flex items-center gap-2 text-sm group"
                      >
                        <span className="text-muted-foreground w-5 text-right">
                          {index + 1}.
                        </span>
                        <span className="truncate flex-1" title={task.instruction}>
                          {task.id}
                        </span>
                        <Badge variant="outline" className="text-xs flex-shrink-0">
                          {task.domain}
                        </Badge>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleTaskSelection(task);
                          }}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Domain summary */}
                  <div className="text-xs text-muted-foreground">
                    Domains:{" "}
                    {[...new Set(selectedTasks.map((t) => t.domain))].join(", ")}
                  </div>

                  {/* Single task stats */}
                  {selectedTasks.length === 1 && (
                    <>
                      {/* Evaluator Info */}
                      {selectedTasks[0].evaluator && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                            <FlaskConical className="h-3 w-3" />
                            Evaluation Method
                          </p>
                          <Badge variant="outline" className="font-mono text-xs">
                            {selectedTasks[0].evaluator.func}
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
                    </>
                  )}

                  {/* Multi-task summary */}
                  {selectedTasks.length > 1 && (
                    <>
                      <Separator />
                      <div className="text-xs text-muted-foreground">
                        Total assessments: {selectedTasks.length * numRuns}
                        {numRuns > 1 && ` (${selectedTasks.length} tasks × ${numRuns} runs)`}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {/* No selection placeholder */}
            {selectedTasks.length === 0 && (
              <Card>
                <CardContent className="py-8">
                  <p className="text-sm text-muted-foreground text-center">
                    Select tasks from the list to launch
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Launch Button */}
            <Button
              size="lg"
              className="w-full"
              disabled={selectedTasks.length === 0 || launchMutation.isPending}
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
                  Launch {selectedTasks.length} Task{selectedTasks.length !== 1 ? "s" : ""}
                </>
              )}
            </Button>

            {/* Keyboard hint */}
            {selectedTasks.length > 0 && !launchMutation.isPending && (
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
