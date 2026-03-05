"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useGetTenantConfigApiTenantsTenantIdConfigGet,
  useUpdateTenantConfigApiTenantsTenantIdConfigPatch,
  getGetTenantConfigApiTenantsTenantIdConfigGetQueryKey,
  useListApiKeysApiTenantsTenantIdApiKeysGet
} from "@/lib/api/generated/tenants/tenants";
import {
  useListModelProvidersApiModelsProvidersGet,
  useListEmbeddingModelsApiModelsEmbeddingsGet
} from "@/lib/api/generated/models/models";

const configSchema = z.object({
  persona_name: z.string().optional(),
  tone: z.string().optional(),
  custom_instructions: z.string().optional().default(""),
  llm_provider: z.string().optional(),
  llm_model: z.string().optional(),
  embedding_provider: z.string().optional(),
  embedding_model: z.string().optional(),
  auto_escalate_on_failure_count: z.any().optional(),
  auto_escalate_on_negative_sentiment: z.boolean().optional().default(true),
  escalation_email: z.any(),
  primary_color: z.string().optional(),
  widget_position: z.string().optional(),
  welcome_message: z.string().optional(),
});

type ConfigFormValues = z.infer<typeof configSchema>;

export default function ConfigPage() {
  const params = useParams();
  const tenantId = params.tenantId as string;
  const queryClient = useQueryClient();
  const [copiedEmbed, setCopiedEmbed] = useState(false);

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { data: config, isLoading: configLoading } = useGetTenantConfigApiTenantsTenantIdConfigGet(tenantId, {
    query: {
      enabled: isMounted
    }
  });

  const { data: llmProviders } = useListModelProvidersApiModelsProvidersGet({
    query: {
      enabled: isMounted
    }
  });

  const { data: embeddingModels } = useListEmbeddingModelsApiModelsEmbeddingsGet({
    query: {
      enabled: isMounted
    }
  });

  const { data: apiKeys } = useListApiKeysApiTenantsTenantIdApiKeysGet(tenantId, {
    query: {
      enabled: isMounted
    }
  });

  const form = useForm<ConfigFormValues>({
    resolver: zodResolver(configSchema),
    defaultValues: {
      persona_name: "",
      tone: "professional",
      custom_instructions: "",
      llm_provider: "gemini",
      llm_model: "gemini-1.5-pro",
      embedding_provider: "gemini",
      embedding_model: "models/text-embedding-004",
      auto_escalate_on_failure_count: 3,
      auto_escalate_on_negative_sentiment: true,
      escalation_email: "",
      primary_color: "#0066CC",
      widget_position: "bottom-right",
      welcome_message: "Hi! How can I help you today?",
    },
  });

  useEffect(() => {
    if (config) {
      form.reset({
        ...config,
        custom_instructions: config.custom_instructions || "",
        escalation_email: config.escalation_email || "",
        primary_color: config.primary_color || "#0066CC",
      });
    }
  }, [config, form]);

  const updateMutation = useUpdateTenantConfigApiTenantsTenantIdConfigPatch({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetTenantConfigApiTenantsTenantIdConfigGetQueryKey(tenantId) });
        alert("Configuration saved successfully!");
      },
      onError: (error) => {
        console.error("Mutation failed:", error);
        alert("Failed to save configuration. See console for details.");
      }
    }
  });

  const onSubmit = (values: ConfigFormValues) => {
    // Clean up empty string values before sending
    const dataToSend = {
      ...values,
      escalation_email: values.escalation_email === "" ? null : values.escalation_email,
    };
    
    // Ensure numbers are correct types
    if (typeof dataToSend.auto_escalate_on_failure_count === "string") {
      dataToSend.auto_escalate_on_failure_count = parseInt(dataToSend.auto_escalate_on_failure_count, 10);
    }
    
    updateMutation.mutate({
      tenantId,
      data: dataToSend as any // Casting to any to bypass TS error with the loose schema
    });
  };

  const onError = (errors: any) => {
    console.error("Form validation errors:", errors);
  };

  const selectedLlmProvider = form.watch("llm_provider");
  const selectedEmbeddingProvider = form.watch("embedding_provider");

  const llmModels = selectedLlmProvider
    ? llmProviders?.find((p) => p.id === selectedLlmProvider)?.available_models || []
    : [];
  
  const embeddingOptions = selectedEmbeddingProvider
    ? embeddingModels?.filter((m) => m.provider === selectedEmbeddingProvider) || []
    : [];

  if (!isMounted) return null;

  if (configLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">Loading configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Chatbot Configuration</h1>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit, onError)} className="space-y-6">
          <Tabs defaultValue="persona" className="w-full">
            {Object.keys(form.formState.errors).length > 0 && (
              <div className="mb-4 p-4 border border-red-500 bg-red-50 text-red-700 rounded-md">
                <p className="font-bold">Please fix the following errors:</p>
                <ul className="list-disc pl-5 mt-2">
                  {Object.entries(form.formState.errors).map(([key, error]) => (
                    <li key={key}>
                      {key}: {error?.message as string}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <TabsList>
              <TabsTrigger value="persona">Persona</TabsTrigger>
              <TabsTrigger value="models">Models</TabsTrigger>
              <TabsTrigger value="escalation">Escalation</TabsTrigger>
              <TabsTrigger value="widget">Widget</TabsTrigger>
              <TabsTrigger value="embed">Embed Code</TabsTrigger>
            </TabsList>

            <TabsContent value="persona" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Persona Settings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="persona_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Persona Name</FormLabel>
                        <FormControl>
                          <Input placeholder="AI Assistant" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="tone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Tone</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="professional">Professional</SelectItem>
                            <SelectItem value="friendly">Friendly</SelectItem>
                            <SelectItem value="casual">Casual</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="custom_instructions"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Custom Instructions</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="You are a helpful assistant that..."
                            className="min-h-32"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Additional context and behavior instructions for the agent
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="models" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>LLM Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="llm_provider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LLM Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {llmProviders && llmProviders.length > 0 ? (
                              llmProviders.map((provider) => (
                                <SelectItem key={provider.id} value={provider.id}>
                                  {provider.name}
                                </SelectItem>
                              ))
                            ) : (
                              <SelectItem value={field.value || "openai"} disabled>
                                Loading providers...
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="llm_model"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LLM Model</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {llmModels && llmModels.length > 0 ? (
                              llmModels.map((model) => (
                                <SelectItem key={model.id} value={model.id}>
                                  {model.name}
                                </SelectItem>
                              ))
                            ) : (
                              <SelectItem value={field.value || "default"} disabled>
                                {field.value || "Loading models..."}
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Embedding Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="embedding_provider"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Embedding Provider</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="openai">OpenAI</SelectItem>
                            <SelectItem value="gemini">Gemini</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="embedding_model"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Embedding Model</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {embeddingOptions && embeddingOptions.length > 0 ? (
                              embeddingOptions.map((model) => (
                                <SelectItem key={model.model_id} value={model.model_id}>
                                  {model.name}
                                </SelectItem>
                              ))
                            ) : (
                              <SelectItem value={field.value || "default"} disabled>
                                {field.value || "Loading models..."}
                              </SelectItem>
                            )}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="escalation" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Escalation Settings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="auto_escalate_on_failure_count"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Failure Count Threshold</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={1}
                            max={10}
                            {...field}
                            onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
                          />
                        </FormControl>
                        <FormDescription>
                          Escalate after this many consecutive failures
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="escalation_email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Escalation Email</FormLabel>
                        <FormControl>
                          <Input
                            type="email"
                            placeholder="support@example.com"
                            {...field}
                            value={field.value || ""}
                          />
                        </FormControl>
                        <FormDescription>
                          Email to notify when escalations occur
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="widget" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Widget Appearance</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="primary_color"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Primary Color</FormLabel>
                        <FormControl>
                          <div className="flex gap-2">
                            <Input type="color" {...field} className="w-20 h-10" />
                            <Input {...field} placeholder="#3B82F6" />
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="widget_position"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Widget Position</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="bottom-right">Bottom Right</SelectItem>
                            <SelectItem value="bottom-left">Bottom Left</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="welcome_message"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Welcome Message</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Hi! How can I help you today?"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="embed" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Embed Widget on Your Website</CardTitle>
                  <CardDescription>
                    Copy and paste this code into your website&apos;s HTML, just before the closing
                    &lt;/body&gt; tag
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {apiKeys && apiKeys.length > 0 ? (
                    <>
                      {apiKeys.filter((k) => k.is_active).map((key) => {
                        const embedCode = `<script src="${process.env.NEXT_PUBLIC_API_URL?.replace("/api", "") || "https://your-domain.com"}/embed.js" data-api-key="${key.key_preview}"></script>`;
                        return (
                          <div key={key.id} className="space-y-2">
                            <div className="flex items-center justify-between">
                              <label className="text-sm font-medium">
                                {key.name || "Unnamed Key"}
                              </label>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  navigator.clipboard.writeText(embedCode);
                                  setCopiedEmbed(true);
                                  setTimeout(() => setCopiedEmbed(false), 2000);
                                }}
                              >
                                {copiedEmbed ? (
                                  <>
                                    <Check className="mr-2 h-4 w-4" />
                                    Copied!
                                  </>
                                ) : (
                                  <>
                                    <Copy className="mr-2 h-4 w-4" />
                                    Copy
                                  </>
                                )}
                              </Button>
                            </div>
                            <pre className="rounded-md bg-muted p-4 text-sm overflow-x-auto">
                              <code>{embedCode}</code>
                            </pre>
                          </div>
                        );
                      })}
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No active API keys found. Please create an API key first in the API Keys
                      section.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end">
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
