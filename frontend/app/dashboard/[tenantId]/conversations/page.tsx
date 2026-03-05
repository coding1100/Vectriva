"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { MessageSquare, ChevronDown, ChevronRight, AlertCircle, Search, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useListConversationsApiTenantsTenantIdConversationsGet,
  useGetConversationApiTenantsTenantIdConversationsConversationIdGet,
  useGetToolCallsApiTenantsTenantIdConversationsConversationIdToolCallsGet,
  useGetRetrievalsApiTenantsTenantIdConversationsConversationIdRetrievalsGet
} from "@/lib/api/generated/conversations/conversations";

export default function ConversationsPage() {
  const params = useParams();
  const tenantId = params.tenantId as string;
  const [selectedConv, setSelectedConv] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { data: conversations, isLoading } = useListConversationsApiTenantsTenantIdConversationsGet(
    tenantId,
    { page, page_size: pageSize },
    {
      query: {
        enabled: isMounted
      }
    }
  );

  const { data: detail } = useGetConversationApiTenantsTenantIdConversationsConversationIdGet(
    tenantId,
    selectedConv || "",
    { query: { enabled: isMounted && !!selectedConv } }
  );

  const { data: toolCalls } = useGetToolCallsApiTenantsTenantIdConversationsConversationIdToolCallsGet(
    tenantId,
    selectedConv || "",
    { query: { enabled: isMounted && !!selectedConv } }
  );

  const { data: retrievals } = useGetRetrievalsApiTenantsTenantIdConversationsConversationIdRetrievalsGet(
    tenantId,
    selectedConv || "",
    { query: { enabled: isMounted && !!selectedConv } }
  );

  if (!isMounted) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Conversations</h1>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent Conversations</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center p-8">
                <p className="text-muted-foreground">Loading conversations...</p>
              </div>
            ) : conversations && conversations.conversations.length > 0 ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Customer</TableHead>
                      <TableHead>Messages</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Started</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {conversations.conversations.map((conv) => (
                      <TableRow
                        key={conv.id}
                        className={`cursor-pointer ${
                          selectedConv === conv.id ? "bg-muted" : ""
                        }`}
                        onClick={() => setSelectedConv(conv.id)}
                      >
                        <TableCell>
                          {conv.customer_email || (
                            <span className="text-muted-foreground">Anonymous</span>
                          )}
                        </TableCell>
                        <TableCell>{conv.message_count}</TableCell>
                        <TableCell>
                          {conv.is_escalated ? (
                            <Badge variant="destructive">Escalated</Badge>
                          ) : (
                            <Badge variant="default">Active</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {new Date(conv.started_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <div className="flex items-center justify-between mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page} of {Math.ceil(conversations.total / pageSize)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= Math.ceil(conversations.total / pageSize)}
                  >
                    Next
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center p-12 text-center">
                <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No conversations yet</h3>
                <p className="text-sm text-muted-foreground">
                  Conversations will appear here once customers start chatting
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Conversation Details</CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedConv ? (
              <div className="flex items-center justify-center p-12 text-center">
                <p className="text-muted-foreground">
                  Select a conversation to view details
                </p>
              </div>
            ) : detail ? (
              <Tabs defaultValue="messages">
                <TabsList className="w-full">
                  <TabsTrigger value="messages" className="flex-1">Messages</TabsTrigger>
                  <TabsTrigger value="tools" className="flex-1">Tool Calls</TabsTrigger>
                  <TabsTrigger value="retrievals" className="flex-1">Retrievals</TabsTrigger>
                </TabsList>

                <TabsContent value="messages" className="space-y-3 mt-4">
                  <div className="space-y-2">
                    {detail.is_escalated && (
                      <Badge variant="destructive" className="mb-2">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        Escalated: {detail.escalation_reason}
                      </Badge>
                    )}
                    {detail.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`rounded-lg p-3 ${
                          msg.role === "user"
                            ? "bg-primary/10 ml-8"
                            : "bg-muted mr-8"
                        }`}
                      >
                        <div className="text-xs font-semibold mb-1">
                          {msg.role === "user" ? "Customer" : "Agent"}
                        </div>
                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        <div className="text-xs text-muted-foreground mt-1">
                          {new Date(msg.created_at).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="tools" className="space-y-2 mt-4">
                  {toolCalls && toolCalls.length > 0 ? (
                    toolCalls.map((call) => (
                      <div
                        key={call.id}
                        className="rounded-lg border p-3 space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Wrench className="h-4 w-4" />
                            <span className="font-semibold text-sm">{call.tool_name}</span>
                          </div>
                          {call.latency_ms && (
                            <span className="text-xs text-muted-foreground">
                              {call.latency_ms}ms
                            </span>
                          )}
                        </div>
                        <div className="text-xs">
                          <div className="font-medium mb-1">Inputs:</div>
                          <pre className="bg-muted p-2 rounded overflow-x-auto">
                            {JSON.stringify(call.inputs, null, 2)}
                          </pre>
                        </div>
                        {call.outputs && (
                          <div className="text-xs">
                            <div className="font-medium mb-1">Outputs:</div>
                            <pre className="bg-muted p-2 rounded overflow-x-auto">
                              {JSON.stringify(call.outputs, null, 2)}
                            </pre>
                          </div>
                        )}
                        {call.error && (
                          <div className="text-xs text-destructive">
                            Error: {call.error}
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground text-center p-8">
                      No tool calls in this conversation
                    </p>
                  )}
                </TabsContent>

                <TabsContent value="retrievals" className="space-y-2 mt-4">
                  {retrievals && retrievals.length > 0 ? (
                    retrievals.map((retrieval) => (
                      <div
                        key={retrieval.id}
                        className="rounded-lg border p-3 space-y-2"
                      >
                        <div className="flex items-center gap-2">
                          <Search className="h-4 w-4" />
                          <span className="font-semibold text-sm">RAG Query</span>
                        </div>
                        <p className="text-sm">{retrieval.query}</p>
                        <div className="text-xs text-muted-foreground">
                          Retrieved {retrieval.chunk_ids.length} chunks
                          {retrieval.similarity_scores.length > 0 && (
                            <span>
                              {" "}
                              (top score: {retrieval.similarity_scores[0].toFixed(3)})
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground text-center p-8">
                      No retrievals in this conversation
                    </p>
                  )}
                </TabsContent>
              </Tabs>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
