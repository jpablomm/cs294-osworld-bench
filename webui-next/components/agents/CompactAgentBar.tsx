"use client";

import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Loader2, CheckCircle2, XCircle, Clock, Zap } from "lucide-react";

interface AgentState {
  status?: string;
  current_step?: number;
  max_steps?: number;
  latest_message?: string;
  current_action?: string;
  vm_status?: string;
  tools_used?: string[];
  message_count?: number;
  thinking_time_ms?: number;
}

interface CompactAgentBarProps {
  greenAgent?: AgentState;
  whiteAgent?: AgentState;
  isActive?: boolean;
}

function getStatusColor(status?: string): string {
  if (!status) return "bg-muted text-muted-foreground";

  const activeStatuses = [
    "initializing", "creating", "booting", "setting_up", "orchestrating",
    "waiting_for_response", "processing_response", "evaluating"
  ];
  const successStatuses = ["completed", "ready", "setup_complete", "tool_success"];
  const errorStatuses = ["failed", "error", "tool_failed"];

  if (activeStatuses.includes(status)) return "bg-primary/20 text-primary border-primary/30";
  if (successStatuses.includes(status)) return "bg-success/20 text-success border-success/30";
  if (errorStatuses.includes(status)) return "bg-destructive/20 text-destructive border-destructive/30";
  return "bg-muted text-muted-foreground";
}

function getStatusIcon(status?: string) {
  if (!status || status === "idle") return null;

  const activeStatuses = [
    "initializing", "creating", "booting", "setting_up", "orchestrating",
    "waiting_for_response", "processing_response", "evaluating", "executing_tool"
  ];
  const successStatuses = ["completed", "ready", "setup_complete", "tool_success"];
  const errorStatuses = ["failed", "error", "tool_failed"];

  if (activeStatuses.includes(status)) {
    return <Loader2 className="h-3 w-3 animate-spin" />;
  }
  if (successStatuses.includes(status)) {
    return <CheckCircle2 className="h-3 w-3" />;
  }
  if (errorStatuses.includes(status)) {
    return <XCircle className="h-3 w-3" />;
  }
  return null;
}

function formatStatus(status?: string): string {
  if (!status) return "idle";
  return status.replace(/_/g, " ");
}

export function CompactAgentBar({ greenAgent, whiteAgent, isActive }: CompactAgentBarProps) {
  return (
    <div className="flex items-center justify-between p-3 bg-card rounded-lg border">
      <div className="flex items-center gap-4">
        {/* Green Agent */}
        <div className="flex items-center gap-2">
          <motion.div
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: "var(--green-agent)" }}
            animate={isActive && greenAgent?.status !== "idle" ? {
              scale: [1, 1.3, 1],
              opacity: [1, 0.7, 1],
            } : {}}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="text-sm font-medium">Green</span>
          <Badge
            variant="outline"
            className={`text-xs ${getStatusColor(greenAgent?.status)}`}
          >
            {getStatusIcon(greenAgent?.status)}
            <span className="ml-1">{formatStatus(greenAgent?.status)}</span>
          </Badge>
          {greenAgent?.vm_status && greenAgent.vm_status !== "done" && (
            <Badge variant="secondary" className="text-xs">
              VM: {greenAgent.vm_status}
            </Badge>
          )}
        </div>

        <div className="h-4 w-px bg-border" />

        {/* White Agent */}
        <div className="flex items-center gap-2">
          <motion.div
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: "var(--white-agent)" }}
            animate={isActive && whiteAgent?.status !== "idle" ? {
              scale: [1, 1.3, 1],
              opacity: [1, 0.7, 1],
            } : {}}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="text-sm font-medium">White</span>
          <Badge
            variant="outline"
            className={`text-xs ${getStatusColor(whiteAgent?.status)}`}
          >
            {getStatusIcon(whiteAgent?.status)}
            <span className="ml-1">{formatStatus(whiteAgent?.status)}</span>
          </Badge>
          {whiteAgent?.current_action && (
            <Badge variant="secondary" className="text-xs font-mono">
              {whiteAgent.current_action}
            </Badge>
          )}
        </div>
      </div>

      {/* Right side: Step counter and metrics */}
      <div className="flex items-center gap-3">
        {greenAgent?.current_step !== undefined && greenAgent.current_step > 0 && (
          <div className="flex items-center gap-1.5 text-sm">
            <Zap className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono">
              {greenAgent.current_step}
              {greenAgent.max_steps ? ` / ${greenAgent.max_steps}` : ""}
            </span>
          </div>
        )}
        {whiteAgent?.thinking_time_ms !== undefined && whiteAgent.thinking_time_ms > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span className="font-mono">{whiteAgent.thinking_time_ms}ms</span>
          </div>
        )}
        {whiteAgent?.tools_used && whiteAgent.tools_used.length > 0 && (
          <Badge variant="outline" className="text-xs">
            {whiteAgent.tools_used.length} tools
          </Badge>
        )}
      </div>
    </div>
  );
}
