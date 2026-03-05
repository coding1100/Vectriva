"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Upload, Trash2, FileText, ChevronDown, ChevronRight } from "lucide-react";
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
import {
  useListDocumentsApiTenantsTenantIdDocumentsGet,
  useGetDocumentChunksApiTenantsTenantIdDocumentsDocumentIdChunksGet,
  useUploadDocumentApiTenantsTenantIdDocumentsPost,
  useDeleteDocumentApiTenantsTenantIdDocumentsDocumentIdDelete,
  getListDocumentsApiTenantsTenantIdDocumentsGetQueryKey
} from "@/lib/api/generated/documents/documents";
import type { DocumentResponse } from "@/lib/api/generated/models";

export default function DocumentsPage() {
  const params = useParams();
  const tenantId = params.tenantId as string;
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { data: documentsData, isLoading } = useListDocumentsApiTenantsTenantIdDocumentsGet(
    tenantId,
    {
      query: {
        enabled: isMounted,
        refetchInterval: (query) => {
          const docs = query.state.data?.data;
          if (docs?.some((d) => d.status === "queued" || d.status === "processing")) {
            return 3000;
          }
          return false;
        },
      }
    }
  );
  const documents = documentsData?.data;

  const { data: chunksData, isLoading: chunksLoading } = useGetDocumentChunksApiTenantsTenantIdDocumentsDocumentIdChunksGet(
    tenantId,
    expandedDoc || "",
    {
      query: { enabled: isMounted && !!expandedDoc }
    }
  );
  const chunks = chunksData?.data;

  const deleteMutation = useDeleteDocumentApiTenantsTenantIdDocumentsDocumentIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListDocumentsApiTenantsTenantIdDocumentsGetQueryKey(tenantId),
        });
      },
    }
  });

  const uploadMutation = useUploadDocumentApiTenantsTenantIdDocumentsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListDocumentsApiTenantsTenantIdDocumentsGetQueryKey(tenantId),
        });
      },
      onError: (err: any) => {
        console.error("Upload failed:", err);
      },
      onSettled: () => {
        setUploading(false);
      }
    }
  });

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    // Let Orval handle FormData creation under the hood
    // Just pass it as the raw object structure it expects
    
    // We need to use the native fetch API directly because orval/axios
    // configuration is still stripping headers or mangling the boundary
    try {
      const token = localStorage.getItem("vectriva_access_token");
      const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/tenants/${tenantId}/documents`;
      
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
          // CRITICAL: Do NOT set Content-Type header here.
          // Fetch automatically sets it to multipart/form-data WITH the correct boundary when body is FormData
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      // Success
      queryClient.invalidateQueries({
        queryKey: getListDocumentsApiTenantsTenantIdDocumentsGetQueryKey(tenantId),
      });
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const getStatusBadge = (status: DocumentResponse["status"]) => {
    const variants: Record<DocumentResponse["status"], "default" | "secondary" | "destructive" | "outline"> = {
      queued: "secondary",
      processing: "default",
      indexed: "default",
      failed: "destructive",
    };
    return (
      <Badge variant={variants[status] || "default"}>
        {status}
      </Badge>
    );
  };

  if (!isMounted) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Documents</h1>
        <div>
          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".pdf,.txt,.md,.docx,.xlsx"
            onChange={handleFileUpload}
            disabled={uploading}
          />
          <Button asChild disabled={uploading}>
            <label htmlFor="file-upload" className="cursor-pointer">
              <Upload className="mr-2 h-4 w-4" />
              {uploading ? "Uploading..." : "Upload Document"}
            </label>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Document Library</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <p className="text-muted-foreground">Loading documents...</p>
            </div>
          ) : documents && documents.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12"></TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Chunks</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-24"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <React.Fragment key={doc.id}>
                    <TableRow>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setExpandedDoc(expandedDoc === doc.id ? null : doc.id)
                          }
                        >
                          {expandedDoc === doc.id ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </Button>
                      </TableCell>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          {doc.name}
                        </div>
                      </TableCell>
                      <TableCell>{doc.file_type}</TableCell>
                      <TableCell>{getStatusBadge(doc.status)}</TableCell>
                      <TableCell>{doc.chunk_count}</TableCell>
                      <TableCell>
                        {new Date(doc.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteMutation.mutate({ tenantId, documentId: doc.id })}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                    {expandedDoc === doc.id && (
                      <TableRow>
                        <TableCell colSpan={7} className="bg-muted/50">
                          <div className="p-4 space-y-2">
                            <h4 className="font-semibold text-sm">Document Chunks</h4>
                            {chunksLoading ? (
                              <p className="text-sm text-muted-foreground">Loading chunks...</p>
                            ) : chunks && chunks.length > 0 ? (
                              <div className="space-y-2">
                                {chunks.slice(0, 5).map((chunk, idx) => (
                                  <div
                                    key={chunk.id}
                                    className="rounded-md border bg-background p-3 text-sm"
                                  >
                                    <div className="font-medium text-xs text-muted-foreground mb-1">
                                      Chunk {idx + 1} ({chunk.chunk_type})
                                    </div>
                                    <p className="line-clamp-3">{chunk.content}</p>
                                  </div>
                                ))}
                                {chunks.length > 5 && (
                                  <p className="text-xs text-muted-foreground">
                                    ... and {chunks.length - 5} more chunks
                                  </p>
                                )}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground">No chunks available</p>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center justify-center p-12 text-center">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No documents yet</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Upload your first document to get started with RAG
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
