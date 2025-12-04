"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import {
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
  MousePointer,
  Keyboard,
  Eye,
  Image,
  ChevronDown,
  ChevronUp,
  Terminal,
  Command,
  Timer,
  Scroll,
} from "lucide-react";

interface ToolExecution {
  step: number;
  timestamp: string;
  tool: string;
  parameters: Record<string, any>;
  status: "success" | "failed" | "executing" | "running";
  duration_ms: number;
  result?: any;
  screenshot_before?: string;
  screenshot_after?: string;
  error?: string;
}

interface ToolExecutionTimelineProps {
  executions: ToolExecution[];
  isLoading?: boolean;
}

const getToolIcon = (tool: string) => {
  switch (tool.toLowerCase()) {
    case "click":
    case "mouse_click":
    case "double_click":
    case "right_click":
      return MousePointer;
    case "type":
    case "type_text":
      return Keyboard;
    case "screenshot":
    case "capture":
      return Eye;
    case "hotkey":
      return Command;
    case "wait":
      return Timer;
    case "scroll":
      return Scroll;
    case "execute_python":
    case "execute_command":
      return Terminal;
    default:
      return Wrench;
  }
};

// Screenshot viewer component with loading state
function ScreenshotViewer({ url, label }: { url: string; label: string }) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  if (!url) return null;

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground font-medium">{label}</p>
      <div className="relative rounded-lg border overflow-hidden bg-muted/50">
        {isLoading && !hasError && (
          <div className="absolute inset-0 flex items-center justify-center bg-muted">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Image className="h-4 w-4 animate-pulse" />
              Loading...
            </div>
          </div>
        )}
        {hasError ? (
          <div className="flex items-center justify-center h-24 text-xs text-muted-foreground">
            <XCircle className="h-4 w-4 mr-1" />
            Failed to load
          </div>
        ) : (
          <img
            src={url}
            alt={label}
            className={`w-full h-auto transition-opacity duration-200 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
            onLoad={() => setIsLoading(false)}
            onError={() => {
              setIsLoading(false);
              setHasError(true);
            }}
          />
        )}
      </div>
    </div>
  );
}

export function ToolExecutionTimeline({ executions, isLoading }: ToolExecutionTimelineProps) {
  const [expandedScreenshots, setExpandedScreenshots] = useState<Set<number>>(new Set());

  const toggleScreenshots = (index: number) => {
    setExpandedScreenshots((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          Loading tool executions...
        </CardContent>
      </Card>
    );
  }

  if (executions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          No tool executions available
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="h-5 w-5" />
          Tool Execution Timeline
        </CardTitle>
        <CardDescription>
          Chronological log of all tool calls and results ({executions.length} executions)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Timeline Line */}
          <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-border" />

          {/* Executions */}
          <div className="space-y-6">
            {executions.map((execution, index) => {
              const ToolIcon = getToolIcon(execution.tool);
              const isSuccess = execution.status === "success";
              const isFailed = execution.status === "failed";
              const isExecuting = execution.status === "executing" || execution.status === "running";
              const hasScreenshots = execution.screenshot_before || execution.screenshot_after;
              const isExpanded = expandedScreenshots.has(index);

              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(index * 0.05, 0.5) }}
                  className="relative pl-16"
                >
                  {/* Timeline Dot */}
                  <div
                    className="absolute left-6 top-4 h-5 w-5 rounded-full border-2 bg-background flex items-center justify-center"
                    style={{
                      borderColor: isSuccess
                        ? "var(--success)"
                        : isFailed
                        ? "var(--error)"
                        : "var(--warning)",
                    }}
                  >
                    {isSuccess && (
                      <CheckCircle2 className="h-3 w-3" style={{ color: "var(--success)" }} />
                    )}
                    {isFailed && (
                      <XCircle className="h-3 w-3" style={{ color: "var(--error)" }} />
                    )}
                    {isExecuting && (
                      <motion.div
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: "var(--warning)" }}
                        animate={{
                          scale: [1, 1.3, 1],
                          opacity: [1, 0.7, 1],
                        }}
                        transition={{
                          duration: 1,
                          repeat: Infinity,
                        }}
                      />
                    )}
                  </div>

                  {/* Content Card */}
                  <Card className={`${isFailed ? "border-destructive" : ""}`}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="font-mono">
                            Step {execution.step}
                          </Badge>
                          <div className="flex items-center gap-1">
                            <ToolIcon className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{execution.tool}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {hasScreenshots && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs"
                              onClick={() => toggleScreenshots(index)}
                            >
                              <Image className="h-3 w-3 mr-1" />
                              {isExpanded ? (
                                <>
                                  Hide
                                  <ChevronUp className="h-3 w-3 ml-1" />
                                </>
                              ) : (
                                <>
                                  Screenshots
                                  <ChevronDown className="h-3 w-3 ml-1" />
                                </>
                              )}
                            </Button>
                          )}
                          <Badge
                            variant={
                              isSuccess
                                ? "default"
                                : isFailed
                                ? "destructive"
                                : "secondary"
                            }
                          >
                            {execution.status}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {/* Timestamp & Duration */}
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {execution.duration_ms > 0 && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            <span className="font-mono">{execution.duration_ms}ms</span>
                          </div>
                        )}
                        <span>{new Date(execution.timestamp).toLocaleTimeString()}</span>
                      </div>

                      {/* Parameters */}
                      {execution.parameters && Object.keys(execution.parameters).length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">
                            Parameters:
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(execution.parameters).map(([key, value]) => (
                              <div
                                key={key}
                                className="text-xs bg-muted px-2 py-1 rounded font-mono"
                              >
                                <span className="text-muted-foreground">{key}:</span>{" "}
                                <span className="break-all">
                                  {typeof value === "object" && value !== null
                                    ? JSON.stringify(value).slice(0, 50)
                                    : String(value).slice(0, 50)}
                                  {String(value).length > 50 ? "..." : ""}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Error message */}
                      {execution.error && (
                        <div className="p-2 bg-destructive/10 rounded border border-destructive/20">
                          <p className="text-xs font-medium text-destructive">Error:</p>
                          <p className="text-xs text-destructive/80 mt-1">{execution.error}</p>
                        </div>
                      )}

                      {/* Result */}
                      {execution.result && (
                        <details className="text-xs">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            View Result
                          </summary>
                          <pre className="mt-2 p-2 bg-muted rounded overflow-auto max-h-40">
                            {JSON.stringify(execution.result, null, 2)}
                          </pre>
                        </details>
                      )}

                      {/* Screenshots (collapsible) */}
                      <AnimatePresence>
                        {hasScreenshots && isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                              {execution.screenshot_before && (
                                <ScreenshotViewer
                                  url={execution.screenshot_before}
                                  label="Before Action"
                                />
                              )}
                              {execution.screenshot_after && (
                                <ScreenshotViewer
                                  url={execution.screenshot_after}
                                  label="After Action"
                                />
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

