"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useTasks, useLaunchAssessment } from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PlayCircle, Search, Loader2, CheckCircle2 } from "lucide-react";
import type { Task } from "@/lib/api/types";

export default function LaunchPage() {
  const router = useRouter();
  const { data: tasks, isLoading: tasksLoading } = useTasks();
  const launchMutation = useLaunchAssessment();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  
  // Configuration state
  const [maxSteps, setMaxSteps] = useState(15);
  const [numRuns, setNumRuns] = useState(1);
  const [vmImage, setVmImage] = useState("osworld-golden-v5-gnome");

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
          t.id.toLowerCase().includes(query) ||
          t.instruction.toLowerCase().includes(query) ||
          t.domain.toLowerCase().includes(query)
      );
    }
    
    return filtered;
  }, [tasks, selectedDomain, searchQuery]);

  const handleLaunch = async () => {
    if (!selectedTask) return;

    try {
      const result = await launchMutation.mutateAsync({
        task_id: selectedTask.id,
        domain: selectedTask.domain,
        max_steps: maxSteps,
        vm_image: vmImage,
        num_runs: numRuns,
      });

      // Redirect based on number of runs
      if (numRuns === 1) {
        router.push(`/assessment/${result.assessment_id}`);
      } else {
        router.push(`/batch/${result.batch_id}`);
      }
    } catch (error) {
      console.error("Launch failed:", error);
    }
  };

  return (
    <div className="container py-8">
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
                <CardTitle>Select Task</CardTitle>
                <CardDescription>
                  Choose an OSWorld task to assess the agent on
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search tasks by name or instruction..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-10 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
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
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={maxSteps}
                    onChange={(e) => setMaxSteps(parseInt(e.target.value) || 15)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum number of agent actions
                  </p>
                </div>

                {/* Number of Runs */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Number of Runs</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={numRuns}
                    onChange={(e) => setNumRuns(parseInt(e.target.value) || 1)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                  <p className="text-xs text-muted-foreground">
                    Run task multiple times for rolling average
                  </p>
                </div>

                {/* VM Image */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">VM Image</label>
                  <select
                    value={vmImage}
                    onChange={(e) => setVmImage(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="osworld-golden-v5-gnome">
                      OSWorld Golden v5 (GNOME)
                    </option>
                    <option value="osworld-golden-v3-gnome">
                      OSWorld Golden v3 (GNOME)
                    </option>
                    <option value="osworld-golden-v2-gnome">
                      OSWorld Golden v2 (GNOME)
                    </option>
                  </select>
                  <p className="text-xs text-muted-foreground">
                    VM image to use for assessment
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Selected Task Preview */}
            {selectedTask && (
              <Card>
                <CardHeader>
                  <CardTitle>Selected Task</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-sm font-medium mb-1">Task ID</p>
                    <p className="text-sm text-muted-foreground">{selectedTask.id}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium mb-1">Domain</p>
                    <Badge variant="secondary">{selectedTask.domain}</Badge>
                  </div>
                  <div>
                    <p className="text-sm font-medium mb-1">Instruction</p>
                    <p className="text-sm text-muted-foreground">
                      {selectedTask.instruction}
                    </p>
                  </div>
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

