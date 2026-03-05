"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useListTenantsApiTenantsGet } from "@/lib/api/generated/tenants/tenants";

export default function DashboardPage() {
  const router = useRouter();
  const [isMounted, setIsMounted] = useState(false);

  const { data: tenantsData } = useListTenantsApiTenantsGet();
  const tenants = tenantsData?.data;

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (isMounted) {
      if (tenants && tenants.length > 0) {
        router.push(`/dashboard/${tenants[0].id}/documents`);
      } else if (tenants && tenants.length === 0) {
        router.push("/dashboard/create-tenant");
      }
    }
  }, [tenants, router, isMounted]);

  if (!isMounted) return null;

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-muted-foreground">Loading...</p>
    </div>
  );
}
