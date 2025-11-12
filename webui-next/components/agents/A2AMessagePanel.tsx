"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { motion } from "framer-motion";
import { MessageSquare, CheckCircle2, XCircle, Clock, ChevronRight } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Message {
  id: string;
  timestamp: string;
  direction: "green_to_white" | "white_to_green";
  type: "task" | "response" | "error";
  payload: any;
  validation: {
    valid: boolean;
    errors: string[];
  };
  latency_ms: number;
}

interface A2AMessagePanelProps {
  messages: Message[];
  isLoading?: boolean;
}

export function A2AMessagePanel({ messages, isLoading }: A2AMessagePanelProps) {
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(
    messages[0] || null
  );

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          Loading messages...
        </CardContent>
      </Card>
    );
  }

  if (messages.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          No messages available
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Message List */}
      <Card className="lg:col-span-1">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" />
            Messages ({messages.length})
          </CardTitle>
          <CardDescription className="text-xs">
            A2A message exchange
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[600px]">
            <div className="space-y-1 p-4 pt-0">
              {messages.map((message, index) => (
                <motion.button
                  key={message.id}
                  onClick={() => setSelectedMessage(message)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedMessage?.id === message.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50 hover:bg-accent/50"
                  }`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <Badge
                      variant={
                        message.direction === "green_to_white"
                          ? "default"
                          : "secondary"
                      }
                      className="text-xs"
                    >
                      {message.direction === "green_to_white" ? "G→W" : "W→G"}
                    </Badge>
                    {!message.validation.valid && (
                      <XCircle className="h-3 w-3 text-destructive" />
                    )}
                  </div>
                  <p className="text-xs font-medium mb-1">
                    {message.type}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {message.timestamp}
                  </p>
                  {selectedMessage?.id === message.id && (
                    <ChevronRight className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" />
                  )}
                </motion.button>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Message Detail */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Message Details</CardTitle>
            {selectedMessage && (
              <Badge
                variant={
                  selectedMessage.direction === "green_to_white"
                    ? "default"
                    : "secondary"
                }
              >
                {selectedMessage.direction === "green_to_white"
                  ? "Green → White"
                  : "White → Green"}
              </Badge>
            )}
          </div>
          <CardDescription className="text-xs">
            Full message content and metadata
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {selectedMessage ? (
            <motion.div
              key={selectedMessage.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="space-y-4"
            >
              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Type</p>
                  <Badge variant="outline">{selectedMessage.type}</Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Timestamp</p>
                  <p className="text-sm font-mono">
                    {new Date(selectedMessage.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>

              {/* Latency */}
              {selectedMessage.latency_ms > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Latency</p>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-mono">
                      {selectedMessage.latency_ms}ms
                    </span>
                  </div>
                </div>
              )}

              <Separator />

              {/* Validation */}
              <div>
                <p className="text-xs text-muted-foreground mb-2">Validation</p>
                <div className="flex items-center gap-2">
                  {selectedMessage.validation.valid ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-success" />
                      <span className="text-sm">Valid</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-destructive" />
                      <span className="text-sm text-destructive">Invalid</span>
                    </>
                  )}
                </div>
                {!selectedMessage.validation.valid &&
                  selectedMessage.validation.errors.length > 0 && (
                    <div className="mt-2 p-2 bg-destructive/10 rounded border border-destructive/20">
                      <p className="text-xs font-medium text-destructive mb-1">
                        Errors:
                      </p>
                      <ul className="text-xs space-y-1">
                        {selectedMessage.validation.errors.map((error, i) => (
                          <li key={i} className="text-destructive">
                            • {error}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>

              <Separator />

              {/* Payload */}
              <div>
                <p className="text-xs text-muted-foreground mb-2">Payload</p>
                <ScrollArea className="h-[300px] w-full rounded-md border">
                  <pre className="p-4 text-xs font-mono bg-muted">
                    {JSON.stringify(selectedMessage.payload, null, 2)}
                  </pre>
                </ScrollArea>
              </div>
            </motion.div>
          ) : (
            <div className="text-sm text-muted-foreground text-center py-12">
              Select a message to view details
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

