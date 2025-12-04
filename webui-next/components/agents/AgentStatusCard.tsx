"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Activity } from "lucide-react";

interface AgentStatusCardProps {
  agent: "green" | "white";
  status?: {
    status: string;
    current_step?: number;
    max_steps?: number;
    current_action?: string;
    vm_status?: string;
    tools_available?: number;
    thinking_time_ms?: number;
    last_action?: any;
    tools_used?: string[];
    message_count?: number;
    latest_message?: string;
    white_agent_url?: string;
  };
  isLive?: boolean;
}

export function AgentStatusCard({ agent, status, isLive = false }: AgentStatusCardProps) {
  const agentColor = agent === "green" ? "var(--green-agent)" : "var(--white-agent)";
  const agentName = agent === "green" ? "Green Agent" : "White Agent";
  const agentRole = agent === "green" ? "Assessment Orchestrator" : "Task Execution Agent";
  
  const isActive = status?.status !== "idle";

  return (
    <Card className="relative overflow-hidden">
      {/* Active Pulse Animation */}
      {isActive && isLive && (
        <motion.div
          className="absolute inset-0 border-2 rounded-lg pointer-events-none"
          style={{ borderColor: agentColor }}
          animate={{
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      )}

      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <motion.div
              className="h-3 w-3 rounded-full"
              style={{ backgroundColor: agentColor }}
              animate={isActive && isLive ? {
                scale: [1, 1.2, 1],
                opacity: [1, 0.8, 1],
              } : {}}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
            <CardTitle className="text-lg">{agentName}</CardTitle>
          </div>
          {isLive && (
            <Badge variant={isActive ? "default" : "secondary"} className="text-xs">
              {isActive ? (
                <>
                  <Activity className="mr-1 h-3 w-3" />
                  Active
                </>
              ) : (
                "Idle"
              )}
            </Badge>
          )}
        </div>
        <CardDescription>{agentRole}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        {status ? (
          <>
            {/* Status */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Status:</span>
              <Badge variant={isActive ? "default" : "secondary"}>
                {status.status}
              </Badge>
            </div>

            {/* Green Agent Specific */}
            {agent === "green" && (
              <>
                {status.current_step !== undefined && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Step:</span>
                    <span className="font-mono">
                      {status.current_step}
                      {status.max_steps && ` / ${status.max_steps}`}
                    </span>
                  </div>
                )}
                {status.latest_message && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Status:</span>
                    <p className="text-xs mt-1 bg-primary/10 px-2 py-1.5 rounded border border-primary/20">
                      {status.latest_message}
                    </p>
                  </div>
                )}
                {status.current_action && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Action:</span>
                    <p className="text-xs mt-1 font-mono bg-muted px-2 py-1 rounded">
                      {status.current_action}
                    </p>
                  </div>
                )}
                {status.vm_status && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">VM Status:</span>
                    <Badge variant="outline">{status.vm_status}</Badge>
                  </div>
                )}
                {status.tools_available !== undefined && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Tools Available:</span>
                    <span className="font-mono">{status.tools_available}</span>
                  </div>
                )}
              </>
            )}

            {/* White Agent Specific */}
            {agent === "white" && (
              <>
                {status.message_count !== undefined && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Messages:</span>
                    <span className="font-mono">{status.message_count}</span>
                  </div>
                )}
                {status.thinking_time_ms !== undefined && status.thinking_time_ms > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Thinking Time:</span>
                    <span className="font-mono">{status.thinking_time_ms}ms</span>
                  </div>
                )}
                {status.tools_used && status.tools_used.length > 0 && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Tools Used:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {status.tools_used.map((tool) => (
                        <Badge key={tool} variant="outline" className="text-xs">
                          {tool}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <div className="text-sm text-muted-foreground text-center py-4">
            No status data available
          </div>
        )}
      </CardContent>
    </Card>
  );
}

