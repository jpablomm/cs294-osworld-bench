"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import {
  Monitor,
  Loader2,
  MousePointer,
  Keyboard,
  Eye,
  Clock,
  CheckCircle2,
  XCircle,
  Maximize2,
  Minimize2,
  Image,
} from "lucide-react";

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

interface CurrentActionPanelProps {
  latestTool?: ToolExecution;
  greenAgentMessage?: string;
  isInitializing?: boolean;
  vmStage?: string;
  vmMessage?: string;
}

function getToolIcon(tool: string) {
  const t = tool.toLowerCase();
  if (t.includes("click") || t.includes("mouse")) return MousePointer;
  if (t.includes("type") || t.includes("key")) return Keyboard;
  if (t.includes("screenshot") || t.includes("capture")) return Eye;
  return Monitor;
}

export function CurrentActionPanel({
  latestTool,
  greenAgentMessage,
  isInitializing,
  vmStage,
  vmMessage,
}: CurrentActionPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);

  // During initialization, show VM progress
  if (isInitializing || !latestTool) {
    return (
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            >
              <Loader2 className="h-4 w-4 text-primary" />
            </motion.div>
            {vmStage === "creating" && "Creating Virtual Machine..."}
            {vmStage === "booting" && "Booting VM..."}
            {vmStage === "ready" && "VM Ready, Setting Up..."}
            {!vmStage || vmStage === "pending" ? "Initializing..." : ""}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="text-center space-y-3">
              <motion.div
                className="w-16 h-16 mx-auto rounded-full bg-primary/20 flex items-center justify-center"
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <Monitor className="h-8 w-8 text-primary" />
              </motion.div>
              <p className="text-sm text-muted-foreground max-w-xs">
                {vmMessage || greenAgentMessage || "Setting up the environment..."}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const ToolIcon = getToolIcon(latestTool.tool);
  const isRunning = latestTool.status === "executing" || latestTool.status === "running";
  const isSuccess = latestTool.status === "success";
  const isFailed = latestTool.status === "failed";
  const screenshotUrl = latestTool.screenshot_after || latestTool.screenshot_before;

  return (
    <Card className={isFailed ? "border-destructive/50" : isRunning ? "border-primary/50" : ""}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
            ) : isSuccess ? (
              <CheckCircle2 className="h-4 w-4 text-success" />
            ) : isFailed ? (
              <XCircle className="h-4 w-4 text-destructive" />
            ) : (
              <ToolIcon className="h-4 w-4" />
            )}
            Current Action
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-xs">
              Step {latestTool.step}
            </Badge>
            <Badge
              variant={isSuccess ? "default" : isFailed ? "destructive" : "secondary"}
            >
              {latestTool.tool}
            </Badge>
            {screenshotUrl && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Parameters */}
        {latestTool.parameters && Object.keys(latestTool.parameters).length > 0 && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(latestTool.parameters).map(([key, value]) => (
              <div
                key={key}
                className="text-xs bg-muted px-2 py-1 rounded font-mono"
              >
                <span className="text-muted-foreground">{key}:</span>{" "}
                <span className="break-all">
                  {typeof value === "object"
                    ? JSON.stringify(value).slice(0, 30)
                    : String(value).slice(0, 30)}
                  {String(value).length > 30 ? "..." : ""}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Duration and timing */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {latestTool.duration_ms > 0 && (
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span className="font-mono">{latestTool.duration_ms}ms</span>
            </div>
          )}
          <span>{new Date(latestTool.timestamp).toLocaleTimeString()}</span>
        </div>

        {/* Error message */}
        {latestTool.error && (
          <div className="p-2 bg-destructive/10 rounded border border-destructive/20">
            <p className="text-xs text-destructive">{latestTool.error}</p>
          </div>
        )}

        {/* Screenshot */}
        <AnimatePresence>
          {screenshotUrl && (
            <motion.div
              initial={{ opacity: 0, height: isExpanded ? "auto" : 200 }}
              animate={{ opacity: 1, height: isExpanded ? "auto" : 200 }}
              className="relative rounded-lg border overflow-hidden bg-muted/50"
            >
              {imageLoading && !imageError && (
                <div className="absolute inset-0 flex items-center justify-center bg-muted">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Image className="h-4 w-4 animate-pulse" />
                    Loading screenshot...
                  </div>
                </div>
              )}
              {imageError ? (
                <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
                  <XCircle className="h-4 w-4 mr-1" />
                  Screenshot unavailable
                </div>
              ) : (
                <img
                  src={screenshotUrl}
                  alt="Current action screenshot"
                  className={`w-full transition-opacity duration-200 ${
                    imageLoading ? "opacity-0" : "opacity-100"
                  } ${isExpanded ? "" : "object-cover h-[200px]"}`}
                  onLoad={() => setImageLoading(false)}
                  onError={() => {
                    setImageLoading(false);
                    setImageError(true);
                  }}
                />
              )}
              {!isExpanded && !imageError && !imageLoading && (
                <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-background/80 to-transparent" />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
