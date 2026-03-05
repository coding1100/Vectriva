"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { Sidebar } from "@/components/dashboard/sidebar";
import { TenantSelector } from "@/components/dashboard/tenant-selector";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    if (!isAuthenticated()) {
      router.push("/login");
    }
  }, [router]);

  // Don't render anything until mounted to prevent hydration errors
  // Since we rely on isAuthenticated() which reads from localStorage
  if (!isMounted || !isAuthenticated()) {
    return null;
  }

  return (
    <div className="flex h-screen bg-transparent relative overflow-hidden">
      {/* Decorative gradient blob */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-indigo-500/10 rounded-full blur-[120px] -z-10 mix-blend-screen pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-5%] w-[40%] h-[40%] bg-blue-500/10 rounded-full blur-[120px] -z-10 mix-blend-screen pointer-events-none" />

      <Sidebar />
      <div className="flex flex-1 flex-col z-10">
        <header className="border-b border-white/5 bg-background/40 backdrop-blur-xl sticky top-0 z-20 shadow-sm">
          <div className="flex h-16 items-center px-6">
            <TenantSelector />
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6 md:p-8 space-y-8">
          {children}
        </main>
      </div>
    </div>
  );
}
