"use client";

import { useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Wrench,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
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
}

interface ActivityFeedProps {
  messages: Message[];
  tools: ToolExecution[];
  isLoading?: boolean;
  autoScroll?: boolean;
}

type ActivityItem = {
  type: "message" | "tool";
  timestamp: string;
  data: Message | ToolExecution;
};

function mergeAndSortActivities(messages: Message[], tools: ToolExecution[]): ActivityItem[] {
  const items: ActivityItem[] = [];

  messages.forEach((msg) => {
    items.push({ type: "message", timestamp: msg.timestamp, data: msg });
  });

  tools.forEach((tool) => {
    items.push({ type: "tool", timestamp: tool.timestamp, data: tool });
  });

  // Sort by timestamp, newest last (for bottom-to-top display, we'll reverse)
  return items.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

function MessageItem({ message }: { message: Message }) {
  const isFromGreen = message.direction === "green_to_white";
  const isValid = message.validation?.valid !== false;

  return (
    <motion.div
      initial={{ opacity: 0, x: isFromGreen ? -10 : 10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-start gap-2 ${isFromGreen ? "" : "flex-row-reverse"}`}
    >
      <div
        className={`flex-shrink-0 h-6 w-6 rounded-full flex items-center justify-center ${
          isFromGreen ? "bg-green-500/20" : "bg-blue-500/20"
        }`}
      >
        {isFromGreen ? (
          <ArrowRight className="h-3 w-3 text-green-600" />
        ) : (
          <ArrowLeft className="h-3 w-3 text-blue-600" />
        )}
      </div>
      <div
        className={`flex-1 max-w-[85%] p-2 rounded-lg text-xs ${
          isFromGreen
            ? "bg-green-500/10 border border-green-500/20"
            : "bg-blue-500/10 border border-blue-500/20"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <Badge variant="outline" className="text-[10px] h-4">
            Step {message.step}
          </Badge>
          <span className="text-muted-foreground text-[10px]">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
          {/* Only show latency for responses (white_to_green) with positive values */}
          {!isFromGreen && message.latency_ms && message.latency_ms > 0 && (
            <span className="text-muted-foreground text-[10px]">
              {message.latency_ms}ms
            </span>
          )}
          {!isValid && (
            <XCircle className="h-3 w-3 text-destructive" />
          )}
        </div>
        {message.payload?.content && (
          <p className="text-muted-foreground line-clamp-2">
            {typeof message.payload.content === "string"
              ? message.payload.content.slice(0, 100)
              : JSON.stringify(message.payload.content).slice(0, 100)}
            {(message.payload.content?.length || 0) > 100 ? "..." : ""}
          </p>
        )}
        {message.payload?.action?.op && (
          <Badge variant="secondary" className="text-[10px] mt-1">
            {message.payload.action.op}
          </Badge>
        )}
      </div>
    </motion.div>
  );
}

function ToolItem({ tool }: { tool: ToolExecution }) {
  const isRunning = tool.status === "executing" || tool.status === "running";
  const isSuccess = tool.status === "success";
  const isFailed = tool.status === "failed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2 py-1"
    >
      <div
        className={`flex-shrink-0 h-6 w-6 rounded-full flex items-center justify-center ${
          isSuccess
            ? "bg-success/20"
            : isFailed
            ? "bg-destructive/20"
            : "bg-primary/20"
        }`}
      >
        {isRunning ? (
          <Loader2 className="h-3 w-3 animate-spin text-primary" />
        ) : isSuccess ? (
          <CheckCircle2 className="h-3 w-3 text-success" />
        ) : isFailed ? (
          <XCircle className="h-3 w-3 text-destructive" />
        ) : (
          <Wrench className="h-3 w-3 text-primary" />
        )}
      </div>
      <div className="flex-1 flex items-center gap-2 text-xs">
        <Badge variant="outline" className="text-[10px] h-4">
          Step {tool.step}
        </Badge>
        <span className="font-mono font-medium">{tool.tool}</span>
        {tool.duration_ms > 0 && (
          <span className="text-muted-foreground flex items-center gap-1">
            <Clock className="h-2.5 w-2.5" />
            {tool.duration_ms}ms
          </span>
        )}
        <span className="text-muted-foreground text-[10px] ml-auto">
          {new Date(tool.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </motion.div>
  );
}

export function ActivityFeed({ messages, tools, isLoading, autoScroll = true }: ActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activities = mergeAndSortActivities(messages, tools);

  // Auto-scroll to bottom when new items arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activities.length, autoScroll]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Activity
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2" />
          Loading activity...
        </CardContent>
      </Card>
    );
  }

  if (activities.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Activity
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          No activity yet. Waiting for agent interactions...
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Activity
          </span>
          <div className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
            <Badge variant="secondary" className="text-[10px]">
              {messages.length} messages
            </Badge>
            <Badge variant="secondary" className="text-[10px]">
              {tools.length} tools
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[300px]" ref={scrollRef}>
          <div className="p-4 space-y-3">
            <AnimatePresence mode="popLayout">
              {activities.map((item, index) => (
                <div key={`${item.type}-${item.timestamp}-${index}`}>
                  {item.type === "message" ? (
                    <MessageItem message={item.data as Message} />
                  ) : (
                    <ToolItem tool={item.data as ToolExecution} />
                  )}
                </div>
              ))}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
