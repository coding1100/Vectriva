"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import { Plus } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useListTenantsApiTenantsGet } from "@/lib/api/generated/tenants/tenants";

export function TenantSelector() {
  const router = useRouter();
  const params = useParams();
  const tenantId = params.tenantId as string | undefined;
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { data: tenants, isLoading } = useListTenantsApiTenantsGet({
    query: {
      enabled: isMounted
    }
  });

  const handleTenantChange = (newTenantId: string) => {
    if (newTenantId === "create") {
      router.push("/dashboard/create-tenant");
    } else {
      router.push(`/dashboard/${newTenantId}/documents`);
    }
  };

  if (!isMounted) return null;

  if (isLoading) {
    return <div className="h-10 w-64 animate-pulse rounded-md bg-muted" />;
  }

  return (
    <div className="flex items-center gap-2">
      <Select value={tenantId} onValueChange={handleTenantChange}>
        <SelectTrigger className="w-64 bg-background/50 backdrop-blur-md border-white/10">
          <SelectValue placeholder="Select tenant" />
        </SelectTrigger>
        <SelectContent>
          {tenants?.map((tenant) => (
            <SelectItem key={tenant.id} value={tenant.id}>
              {tenant.name}
            </SelectItem>
          ))}
          <SelectItem value="create">
            <div className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              Create new tenant
            </div>
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
