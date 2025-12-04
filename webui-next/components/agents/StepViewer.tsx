"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  Monitor,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  MousePointer,
  Keyboard,
  Eye,
  Brain,
  Zap,
  ImageOff,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";

interface Message {
  id: string;
  step: number;
  timestamp: string;
  direction: "green_to_white" | "white_to_green";
  type?: string;
  payload: any;
  validation?: { valid: boolean; errors?: string[] };
  latency_ms?: number;
}

interface ToolExecution {
  step: number;
  timestamp: string;
  tool: string;
  parameters: Record<string, any>;
  status: "success" | "failed" | "executing" | "running";
  duration_ms: number;
  screenshot_before?: string;
  screenshot_after?: string;
  error?: string;
}

interface StepData {
  step: number;
  timestamp: string;
  // From white agent message
  reasoning?: string;
  action?: {
    op: string;
    [key: string]: any;
  };
  // From tool execution
  tool?: ToolExecution;
  // Screenshot URL
  screenshot?: string;
}

interface StepViewerProps {
  messages: Message[];
  tools: ToolExecution[];
  isActive?: boolean;
}

function getToolIcon(tool: string) {
  const t = tool.toLowerCase();
  if (t.includes("click") || t.includes("mouse")) return MousePointer;
  if (t.includes("type") || t.includes("key")) return Keyboard;
  if (t.includes("screenshot") || t.includes("capture")) return Eye;
  return Zap;
}

function buildStepData(messages: Message[], tools: ToolExecution[]): StepData[] {
  const stepMap = new Map<number, StepData>();

  // Process white agent messages (responses with reasoning)
  messages
    .filter((m) => m.direction === "white_to_green")
    .forEach((msg) => {
      const existing = stepMap.get(msg.step) || { step: msg.step, timestamp: msg.timestamp };

      // Extract reasoning from payload
      if (msg.payload?.content) {
        existing.reasoning = typeof msg.payload.content === "string"
          ? msg.payload.content
          : JSON.stringify(msg.payload.content, null, 2);
      }

      // Extract action from payload
      if (msg.payload?.action) {
        existing.action = msg.payload.action;
      }

      stepMap.set(msg.step, existing);
    });

  // Process tool executions
  tools.forEach((tool) => {
    const existing = stepMap.get(tool.step) || { step: tool.step, timestamp: tool.timestamp };
    existing.tool = tool;
    existing.screenshot = tool.screenshot_after || tool.screenshot_before;

    // Use tool timestamp if earlier
    if (!existing.timestamp || new Date(tool.timestamp) < new Date(existing.timestamp)) {
      existing.timestamp = tool.timestamp;
    }

    stepMap.set(tool.step, existing);
  });

  // Sort by step number
  return Array.from(stepMap.values()).sort((a, b) => a.step - b.step);
}

export function StepViewer({ messages, tools, isActive }: StepViewerProps) {
  const steps = useMemo(() => buildStepData(messages, tools), [messages, tools]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [imageLoading, setImageLoading] = useState(true);
  const [imageError, setImageError] = useState(false);

  // Auto-advance to latest step when active and new steps arrive
  useEffect(() => {
    if (isActive && steps.length > 0) {
      setCurrentIndex(steps.length - 1);
    }
  }, [steps.length, isActive]);

  // Reset image state when step changes
  useEffect(() => {
    setImageLoading(true);
    setImageError(false);
  }, [currentIndex]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        setCurrentIndex((prev) => Math.max(0, prev - 1));
      } else if (e.key === "ArrowRight") {
        setCurrentIndex((prev) => Math.min(steps.length - 1, prev + 1));
      } else if (e.key === "Home") {
        setCurrentIndex(0);
      } else if (e.key === "End") {
        setCurrentIndex(steps.length - 1);
      }
    },
    [steps.length]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const currentStep = steps[currentIndex];
  const canGoPrev = currentIndex > 0;
  const canGoNext = currentIndex < steps.length - 1;

  // Empty state
  if (steps.length === 0) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="flex flex-col items-center justify-center text-center">
            <motion.div
              className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center mb-4"
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Monitor className="h-8 w-8 text-primary" />
            </motion.div>
            <h3 className="text-lg font-medium mb-2">Waiting for agent actions...</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              The step viewer will show each action as the agent executes them.
              You&apos;ll see screenshots, reasoning, and tool executions.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const ToolIcon = currentStep?.tool ? getToolIcon(currentStep.tool.tool) : Zap;
  const isRunning = currentStep?.tool?.status === "executing" || currentStep?.tool?.status === "running";
  const isSuccess = currentStep?.tool?.status === "success";
  const isFailed = currentStep?.tool?.status === "failed";

  return (
    <Card className="overflow-hidden">
      {/* Navigation Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentIndex(0)}
            disabled={!canGoPrev}
            className="h-8 w-8 p-0"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentIndex((prev) => prev - 1)}
            disabled={!canGoPrev}
            className="h-8 w-8 p-0"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">
            Step {currentStep?.step || currentIndex + 1}
          </span>
          <Badge variant="outline" className="font-mono text-xs">
            {currentIndex + 1} / {steps.length}
          </Badge>
          {isActive && currentIndex === steps.length - 1 && (
            <Badge variant="secondary" className="text-xs">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Live
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentIndex((prev) => prev + 1)}
            disabled={!canGoNext}
            className="h-8 w-8 p-0"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentIndex(steps.length - 1)}
            disabled={!canGoNext}
            className="h-8 w-8 p-0"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <CardContent className="p-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="grid lg:grid-cols-2"
          >
            {/* Left: Screenshot Section */}
            <div className="relative bg-black/5 dark:bg-white/5 lg:border-r">
              {currentStep?.screenshot ? (
                <div className="relative">
                  {imageLoading && !imageError && (
                    <div className="absolute inset-0 flex items-center justify-center bg-muted min-h-[350px]">
                      <div className="flex flex-col items-center gap-2 text-muted-foreground">
                        <Loader2 className="h-6 w-6 animate-spin" />
                        <span className="text-sm">Loading screenshot...</span>
                      </div>
                    </div>
                  )}
                  {imageError ? (
                    <div className="flex flex-col items-center justify-center min-h-[350px] text-muted-foreground">
                      <ImageOff className="h-8 w-8 mb-2" />
                      <span className="text-sm">Screenshot unavailable</span>
                    </div>
                  ) : (
                    <img
                      src={currentStep.screenshot}
                      alt={`Step ${currentStep.step} screenshot`}
                      className={`w-full transition-opacity duration-200 ${
                        imageLoading ? "opacity-0" : "opacity-100"
                      }`}
                      onLoad={() => setImageLoading(false)}
                      onError={() => {
                        setImageLoading(false);
                        setImageError(true);
                      }}
                    />
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center min-h-[350px] text-muted-foreground">
                  <Monitor className="h-8 w-8 mb-2" />
                  <span className="text-sm">No screenshot for this step</span>
                </div>
              )}
            </div>

            {/* Right: Reasoning & Action */}
            <div className="flex flex-col">
              {/* Reasoning Section */}
              <div className="flex-1 p-4 border-t lg:border-t-0">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                    <Brain className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium">Reasoning</span>
                      {currentStep?.tool?.duration_ms && currentStep.tool.duration_ms > 0 && (
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {currentStep.tool.duration_ms}ms
                        </span>
                      )}
                    </div>
                    {currentStep?.reasoning ? (
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                        {currentStep.reasoning}
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground/50 italic">
                        No reasoning available for this step
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Section */}
              <div className="p-4 border-t bg-muted/30">
                <div className="flex items-start gap-3">
                  <div
                    className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                      isSuccess
                        ? "bg-success/20"
                        : isFailed
                        ? "bg-destructive/20"
                        : isRunning
                        ? "bg-primary/20"
                        : "bg-muted"
                    }`}
                  >
                    {isRunning ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : isSuccess ? (
                      <CheckCircle2 className="h-4 w-4 text-success" />
                    ) : isFailed ? (
                      <XCircle className="h-4 w-4 text-destructive" />
                    ) : (
                      <ToolIcon className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center flex-wrap gap-2 mb-2">
                      <span className="text-sm font-medium">Action</span>
                      {(currentStep?.tool || currentStep?.action) ? (
                        <>
                          <Badge
                            variant={isSuccess ? "default" : isFailed ? "destructive" : "secondary"}
                            className="font-mono text-xs"
                          >
                            {currentStep.tool?.tool || currentStep.action?.op || "unknown"}
                          </Badge>
                          {currentStep.tool && (
                            <span className="text-xs text-muted-foreground">
                              {new Date(currentStep.tool.timestamp).toLocaleTimeString()}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground/50 italic">
                          No action recorded
                        </span>
                      )}
                    </div>

                    {/* Parameters */}
                    {currentStep?.tool?.parameters && Object.keys(currentStep.tool.parameters).length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-2">
                        {Object.entries(currentStep.tool.parameters).map(([key, value]) => (
                          <div
                            key={key}
                            className="text-xs bg-background px-2 py-1 rounded border font-mono"
                          >
                            <span className="text-muted-foreground">{key}:</span>{" "}
                            <span>
                              {typeof value === "object"
                                ? JSON.stringify(value)
                                : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action parameters from message */}
                    {currentStep?.action && !currentStep?.tool && (
                      <div className="flex flex-wrap gap-2 mb-2">
                        {Object.entries(currentStep.action)
                          .filter(([key]) => key !== "op")
                          .map(([key, value]) => (
                            <div
                              key={key}
                              className="text-xs bg-background px-2 py-1 rounded border font-mono"
                            >
                              <span className="text-muted-foreground">{key}:</span>{" "}
                              <span>
                                {typeof value === "object"
                                  ? JSON.stringify(value)
                                  : String(value)}
                              </span>
                            </div>
                          ))}
                      </div>
                    )}

                    {/* Error message */}
                    {currentStep?.tool?.error && (
                      <div className="p-2 bg-destructive/10 rounded border border-destructive/20 mt-2">
                        <p className="text-xs text-destructive">{currentStep.tool.error}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </CardContent>

      {/* Keyboard hint */}
      <div className="px-4 py-2 border-t text-xs text-muted-foreground text-center">
        Use <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-mono">←</kbd>{" "}
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-mono">→</kbd> arrow keys to navigate
      </div>
    </Card>
  );
}
