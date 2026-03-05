"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Button } from "@/components/ui/button";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCreateTenantApiTenantsPost } from "@/lib/api/generated/tenants/tenants";

const tenantSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  timezone: z.string().min(1, "Please select a timezone"),
});

type TenantFormValues = z.infer<typeof tenantSchema>;

const timezones = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Toronto",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
];

export default function CreateTenantPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const form = useForm<TenantFormValues>({
    resolver: zodResolver(tenantSchema),
    defaultValues: {
      name: "",
      timezone: "UTC",
    },
  });

  useEffect(() => {
    if (isMounted) {
      form.setValue("timezone", Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
    }
  }, [isMounted, form]);

  const createMutation = useCreateTenantApiTenantsPost({
    mutation: {
      onSuccess: (response) => {
        if (response && response.data && response.data.id) {
            router.push(`/dashboard/${response.data.id}/documents`);
        } else {
            // It seems response isn't formatted as expected, probably due to axios unwrapping
            // Try to extract from the root or navigate to the dashboard root
            const tenantId = (response as any)?.id;
            if (tenantId) {
                router.push(`/dashboard/${tenantId}/documents`);
            } else {
                router.push("/dashboard");
            }
        }
      },
      onError: (err: any) => {
        console.error("Creation error:", err);
        const errorMsg = err.response?.data?.detail 
          ? (typeof err.response.data.detail === 'string' 
              ? err.response.data.detail 
              : JSON.stringify(err.response.data.detail))
          : "Failed to create tenant. Please try again.";
        setError(errorMsg);
      }
    }
  });

  function onSubmit(values: TenantFormValues) {
    setError(null);
    createMutation.mutate({ data: values });
  }

  if (!isMounted) return null;

  return (
    <div className="flex h-full items-center justify-center relative">
      {/* Decorative gradient blob */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary/20 rounded-full blur-[100px] -z-10 animate-pulse" />
      
      <Card className="w-full max-w-lg backdrop-blur-xl bg-background/60 border-white/10 shadow-2xl">
        <CardHeader>
          <CardTitle>Create New Tenant</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tenant Name</FormLabel>
                    <FormControl>
                      <Input placeholder="My Organization" className="bg-background/50 backdrop-blur-md" {...field} />
                    </FormControl>
                    <FormDescription>
                      This is the name that will identify your organization
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="timezone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Timezone</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger className="bg-background/50 backdrop-blur-md">
                          <SelectValue placeholder="Select a timezone" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {timezones.map((tz) => (
                          <SelectItem key={tz} value={tz}>
                            {tz}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Used for scheduling and business hours
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {error && (
                <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => router.back()}
                  disabled={createMutation.isPending}
                  className="bg-transparent border-white/10 hover:bg-white/5"
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending} className="bg-primary hover:bg-primary/90 shadow-[0_0_20px_rgba(59,130,246,0.5)]">
                  {createMutation.isPending ? "Creating..." : "Create Tenant"}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
