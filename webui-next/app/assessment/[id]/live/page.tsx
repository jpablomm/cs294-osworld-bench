"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  useAssessment,
  useAssessmentMessages,
  useToolExecutions,
  useAgentState,
} from "@/lib/api/queries";
import { useSSE } from "@/lib/hooks/useSSE";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { A2AMessagePanel } from "@/components/agents/A2AMessagePanel";
import { ToolExecutionTimeline } from "@/components/agents/ToolExecutionTimeline";
import {
  ArrowLeft,
  Loader2,
  Radio,
  MessageSquare,
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";
import { motion } from "framer-motion";

export default function LiveAssessmentPage() {
  const params = useParams();
  const assessmentId = params.id as string;

  // Fetch all data
  const { data: assessment, isLoading } = useAssessment(assessmentId);
  const { data: messages } = useAssessmentMessages(assessmentId);
  const { data: tools } = useToolExecutions(assessmentId);
  const { data: agentState } = useAgentState(assessmentId);

  // Real-time updates via SSE
  const { connected: sseConnected } = useSSE(assessmentId, {
    enabled: true,
    onEvent: (event) => {
      console.log("[Live View] SSE Event:", event);
    },
  });

  if (isLoading) {
    return (
      <div className="container py-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="container py-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Assessment Not Found</CardTitle>
            <CardDescription>
              The assessment with ID "{assessmentId}" could not be found.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/results">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Results
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isRunning = assessment.status === "running";
  const isCompleted = assessment.status === "completed";
  const isFailed = assessment.status === "failed";

  // Detect if assessment is initializing (running but no data yet)
  const isInitializing =
    isRunning &&
    assessment.steps === 0 &&
    (!messages?.messages?.length) &&
    (!agentState?.green_agent && !agentState?.white_agent);

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div>
          <Link href={`/assessment/${assessmentId}`}>
            <Button variant="ghost" size="sm" className="mb-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Details
            </Button>
          </Link>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                Live Agent Interaction
                {sseConnected && isRunning && (
                  <motion.div
                    className="flex items-center gap-2"
                    animate={{ opacity: [1, 0.5, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Radio className="h-5 w-5 text-success" />
                    <span className="text-sm font-normal text-success">Live</span>
                  </motion.div>
                )}
              </h1>
              <p className="text-muted-foreground mt-1">
                {assessment.task_id} • {assessment.id}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {isRunning && (
                <Badge variant="secondary" className="h-8 px-4">
                  <Clock className="mr-2 h-4 w-4 animate-pulse" />
                  Running
                </Badge>
              )}
              {isCompleted && (
                <Badge className="h-8 px-4">
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Completed
                </Badge>
              )}
              {isFailed && (
                <Badge variant="destructive" className="h-8 px-4">
                  <XCircle className="mr-2 h-4 w-4" />
                  Failed
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Initializing State */}
        {isInitializing && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <Card className="border-primary/50 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  >
                    <Loader2 className="h-6 w-6 text-primary" />
                  </motion.div>
                  Launching Assessment...
                </CardTitle>
                <CardDescription>
                  Setting up agents and environment. This typically takes 10-30 seconds.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-success" />
                    <span>Assessment created</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <motion.div
                      animate={{ opacity: [0.5, 1, 0.5] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    >
                      <Loader2 className="h-4 w-4 text-primary" />
                    </motion.div>
                    <span>Starting agents and environment...</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>Waiting for first action</span>
                  </div>
                </div>
                <div className="pt-2 text-xs text-muted-foreground">
                  The page will automatically update when the assessment begins.
                  {sseConnected && (
                    <span className="text-success ml-2">• Live connection active</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Skeleton loaders for agent cards */}
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-4 rounded-full bg-muted animate-pulse" />
                    <div className="h-4 w-24 bg-muted rounded animate-pulse" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="h-3 bg-muted rounded animate-pulse" />
                    <div className="h-3 bg-muted rounded animate-pulse w-3/4" />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="h-4 w-4 rounded-full bg-muted animate-pulse" />
                    <div className="h-4 w-24 bg-muted rounded animate-pulse" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="h-3 bg-muted rounded animate-pulse" />
                    <div className="h-3 bg-muted rounded animate-pulse w-3/4" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}

        {/* Agent Status Cards - Only show when not initializing */}
        {!isInitializing && (
        <div className="grid gap-4 md:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <AgentStatusCard
              agent="green"
              status={agentState?.green_agent}
              isLive={sseConnected && isRunning}
            />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <AgentStatusCard
              agent="white"
              status={agentState?.white_agent}
              isLive={sseConnected && isRunning}
            />
          </motion.div>
        </div>
        )}

        {/* Main Content Tabs - Only show when not initializing */}
        {!isInitializing && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Tabs defaultValue="messages" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2 lg:w-[400px]">
              <TabsTrigger value="messages">
                <MessageSquare className="mr-2 h-4 w-4" />
                Messages ({messages?.messages?.length || 0})
              </TabsTrigger>
              <TabsTrigger value="tools">
                <Wrench className="mr-2 h-4 w-4" />
                Tools ({tools?.executions?.length || 0})
              </TabsTrigger>
            </TabsList>

            {/* Messages Tab */}
            <TabsContent value="messages">
              <A2AMessagePanel
                messages={messages?.messages || []}
                isLoading={!messages}
              />
            </TabsContent>

            {/* Tools Tab */}
            <TabsContent value="tools">
              <ToolExecutionTimeline
                executions={tools?.executions || []}
                isLoading={!tools}
              />
            </TabsContent>
          </Tabs>
        </motion.div>
        )}
      </div>
    </div>
  );
}

