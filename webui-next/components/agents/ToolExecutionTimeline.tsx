"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { 
  Wrench, 
  CheckCircle2, 
  XCircle, 
  Clock,
  MousePointer,
  Keyboard,
  Eye,
  ArrowRight,
} from "lucide-react";

interface ToolExecution {
  step: number;
  timestamp: string;
  tool: string;
  parameters: Record<string, any>;
  status: "success" | "failed" | "executing";
  duration_ms: number;
  result?: any;
  screenshot_before?: string;
  screenshot_after?: string;
}

interface ToolExecutionTimelineProps {
  executions: ToolExecution[];
  isLoading?: boolean;
}

const getToolIcon = (tool: string) => {
  switch (tool.toLowerCase()) {
    case "click":
    case "mouse_click":
      return MousePointer;
    case "type":
    case "type_text":
    case "keyboard":
      return Keyboard;
    case "screenshot":
    case "capture":
      return Eye;
    default:
      return Wrench;
  }
};

export function ToolExecutionTimeline({ executions, isLoading }: ToolExecutionTimelineProps) {
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
          Chronological log of all tool calls and results
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
              const isExecuting = execution.status === "executing";

              return (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
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
                      {Object.keys(execution.parameters).length > 0 && (
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
                                <span>{String(value)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Result */}
                      {execution.result && (
                        <details className="text-xs">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            View Result
                          </summary>
                          <pre className="mt-2 p-2 bg-muted rounded overflow-auto">
                            {JSON.stringify(execution.result, null, 2)}
                          </pre>
                        </details>
                      )}

                      {/* Screenshots */}
                      {(execution.screenshot_before || execution.screenshot_after) && (
                        <div className="grid grid-cols-2 gap-2">
                          {execution.screenshot_before && (
                            <div>
                              <p className="text-xs text-muted-foreground mb-1">Before</p>
                              <img
                                src={execution.screenshot_before}
                                alt="Before"
                                className="rounded border w-full"
                              />
                            </div>
                          )}
                          {execution.screenshot_after && (
                            <div>
                              <p className="text-xs text-muted-foreground mb-1">After</p>
                              <img
                                src={execution.screenshot_after}
                                alt="After"
                                className="rounded border w-full"
                              />
                            </div>
                          )}
                        </div>
                      )}
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

