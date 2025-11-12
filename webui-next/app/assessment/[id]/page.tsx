"use client";

import { useParams } from "next/navigation";
import {
  useAssessment,
  useAssessmentMessages,
  useToolExecutions,
  useAgentState,
  useEvaluationDetails,
} from "@/lib/api/queries";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CheckCircle2,
  XCircle,
  Clock,
  ArrowLeft,
  Loader2,
  MessageSquare,
  Wrench,
  Activity,
  Target,
} from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

export default function AssessmentDetailPage() {
  const params = useParams();
  const assessmentId = params.id as string;
  
  // Fetch assessment data
  const { data: assessment, isLoading } = useAssessment(assessmentId);
  const { data: messages } = useAssessmentMessages(assessmentId);
  const { data: tools } = useToolExecutions(assessmentId);
  const { data: agentState } = useAgentState(assessmentId);
  const { data: evaluation } = useEvaluationDetails(assessmentId);

  if (isLoading) {
    return (
      <div className="container py-8">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-center py-12"
        >
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </motion.div>
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

  return (
    <div className="container py-8">
      <div className="flex flex-col gap-8">
        {/* Header */}
        <div>
          <Link href="/results">
            <Button variant="ghost" size="sm" className="mb-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Results
            </Button>
          </Link>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">{assessment.task_id}</h1>
              <p className="text-muted-foreground">Assessment ID: {assessment.id}</p>
            </div>
            <div className="flex items-center gap-3">
              <Link href={`/assessment/${assessmentId}/live`}>
                <Button variant="outline">
                  <Activity className="mr-2 h-4 w-4" />
                  Live View
                </Button>
              </Link>
              <Badge
                variant={
                  assessment.status === "completed"
                    ? "default"
                    : assessment.status === "failed"
                    ? "destructive"
                    : "secondary"
                }
                className="h-8 px-4"
              >
                {assessment.status === "completed" && assessment.success && (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                )}
                {assessment.status === "failed" && <XCircle className="mr-2 h-4 w-4" />}
                {assessment.status === "running" && <Clock className="mr-2 h-4 w-4 animate-pulse" />}
                {assessment.status}
              </Badge>
            </div>
          </div>
        </div>

        {/* Overview */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Domain</CardTitle>
              </CardHeader>
              <CardContent>
                <Badge variant="outline">{assessment.domain || "N/A"}</Badge>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Steps Taken</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{assessment.steps}</div>
                <p className="text-xs text-muted-foreground">
                  Max: {assessment.config.max_steps}
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Execution Time</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {assessment.time_sec ? `${Math.round(assessment.time_sec)}s` : "—"}
                </div>
                <p className="text-xs text-muted-foreground">Total duration</p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Evaluation Score</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {assessment.evaluation_score !== null
                    ? assessment.evaluation_score.toFixed(2)
                    : "—"}
                </div>
                <p className="text-xs text-muted-foreground">
                  {assessment.evaluation_method || "N/A"}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Enhanced Data Tabs */}
        <Tabs defaultValue="trajectory" className="space-y-4">
          <TabsList>
            <TabsTrigger value="trajectory">
              <Target className="mr-2 h-4 w-4" />
              Trajectory
            </TabsTrigger>
            <TabsTrigger value="messages">
              <MessageSquare className="mr-2 h-4 w-4" />
              Messages ({messages?.messages?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="tools">
              <Wrench className="mr-2 h-4 w-4" />
              Tools ({tools?.executions?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="agent-state">
              <Activity className="mr-2 h-4 w-4" />
              Agent State
            </TabsTrigger>
          </TabsList>

          {/* Trajectory Tab */}
          <TabsContent value="trajectory">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              {assessment?.trajectory && assessment.trajectory.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Trajectory</CardTitle>
                    <CardDescription>
                      Action sequence taken by the agent
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {assessment.trajectory.map((step, index) => (
                        <motion.div
                          key={index}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.2 }}
                          className="flex gap-4 border-l-2 border-primary/30 pl-4 pb-4 last:pb-0"
                        >
                          <div className="flex-shrink-0">
                            <Badge variant="outline" className="font-mono">
                              Step {step.step}
                            </Badge>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm mb-1">
                              Action: <code className="text-primary">{step.action.op}</code>
                            </p>
                            <p className="text-sm text-muted-foreground line-clamp-3">
                              {step.content}
                            </p>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardContent className="py-12 text-center text-muted-foreground">
                    No trajectory data available
                  </CardContent>
                </Card>
              )}
            </motion.div>
          </TabsContent>

          {/* Messages Tab */}
          <TabsContent value="messages">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle>A2A Message History</CardTitle>
                  <CardDescription>
                    Full message exchange between green and white agents
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {messages?.messages && messages.messages.length > 0 ? (
                    <div className="space-y-4">
                      {messages.messages.map((msg: any, index) => (
                        <motion.div
                          key={msg.id || index}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.2 }}
                          className="border rounded-lg p-4 space-y-2"
                        >
                        <div className="flex items-center justify-between">
                          <Badge
                            variant={
                              msg.direction === "green_to_white"
                                ? "default"
                                : "secondary"
                            }
                          >
                            {msg.direction === "green_to_white"
                              ? "Green → White"
                              : "White → Green"}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {msg.latency_ms > 0 && `${msg.latency_ms}ms`}
                          </span>
                        </div>
                        <div className="text-sm">
                          <strong>Type:</strong> {msg.type}
                        </div>
                        {msg.validation && !msg.validation.valid && (
                          <div className="text-sm text-destructive">
                            <strong>Validation Errors:</strong>{" "}
                            {msg.validation.errors.join(", ")}
                          </div>
                        )}
                        <details className="text-sm">
                          <summary className="cursor-pointer text-muted-foreground">
                            View Payload
                          </summary>
                          <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-auto">
                            {JSON.stringify(msg.payload, null, 2)}
                          </pre>
                        </details>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No message data available
                    </p>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* Tools Tab */}
          <TabsContent value="tools">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card>
                <CardHeader>
                  <CardTitle>Tool Executions</CardTitle>
                  <CardDescription>
                    Detailed log of tool calls and results
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {tools?.executions && tools.executions.length > 0 ? (
                    <div className="space-y-4">
                      {tools.executions.map((exec: any, index) => (
                        <motion.div
                          key={index}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.2 }}
                          className="border rounded-lg p-4 space-y-2"
                        >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">Step {exec.step}</Badge>
                            <span className="font-medium">{exec.tool}</span>
                          </div>
                          <Badge
                            variant={
                              exec.status === "success"
                                ? "default"
                                : exec.status === "failed"
                                ? "destructive"
                                : "secondary"
                            }
                          >
                            {exec.status}
                          </Badge>
                        </div>
                        {exec.duration_ms > 0 && (
                          <div className="text-sm text-muted-foreground">
                            Duration: {exec.duration_ms}ms
                          </div>
                        )}
                        <details className="text-sm">
                          <summary className="cursor-pointer text-muted-foreground">
                            View Parameters
                          </summary>
                          <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-auto">
                            {JSON.stringify(exec.parameters, null, 2)}
                          </pre>
                        </details>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No tool execution data available
                    </p>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </TabsContent>

          {/* Agent State Tab */}
          <TabsContent value="agent-state">
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: "var(--green-agent)" }}
                    />
                    Green Agent
                  </CardTitle>
                  <CardDescription>Assessment orchestrator</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {agentState?.green_agent ? (
                    <>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Status:</span>
                        <Badge>{agentState.green_agent.status}</Badge>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Current Step:</span>
                        <span>{agentState.green_agent.current_step}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Current Action:</span>
                        <span className="text-xs">
                          {agentState.green_agent.current_action}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">VM Status:</span>
                        <Badge variant="outline">
                          {agentState.green_agent.vm_status}
                        </Badge>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">No data available</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: "var(--white-agent)" }}
                    />
                    White Agent
                  </CardTitle>
                  <CardDescription>Task execution agent</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {agentState?.white_agent ? (
                    <>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Status:</span>
                        <Badge>{agentState.white_agent.status}</Badge>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Messages:</span>
                        <span>{agentState.white_agent.message_count}</span>
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground">Tools Used:</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {agentState.white_agent.tools_used.map((tool: string) => (
                            <Badge key={tool} variant="outline" className="text-xs">
                              {tool}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">No data available</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        {/* Failure Reason */}
        {assessment.failure_reason && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Failure Reason</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{assessment.failure_reason}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

