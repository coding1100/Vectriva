"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { FileText, Settings, Calendar, Key, MessageSquare, LogOut, Hexagon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { clearTokens } from "@/lib/auth";
import { useRouter } from "next/navigation";

const navigation = [
  { name: "Documents", href: "/documents", icon: FileText },
  { name: "Conversations", href: "/conversations", icon: MessageSquare },
  { name: "Integrations", href: "/integrations", icon: Calendar },
  { name: "API Keys", href: "/api-keys", icon: Key },
  { name: "Config", href: "/config", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const params = useParams();
  const router = useRouter();
  const tenantId = params.tenantId as string | undefined;

  const handleLogout = () => {
    clearTokens();
    router.push("/login");
  };

  return (
    <div className="flex h-screen w-64 flex-col border-r border-white/5 bg-background/40 backdrop-blur-xl z-20 shadow-[4px_0_24px_-12px_rgba(0,0,0,0.1)]">
      <div className="p-6 flex items-center gap-3">
        <div className="bg-primary/20 p-2 rounded-xl text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]">
          <Hexagon className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-foreground to-foreground/70">
          Vectriva
        </h1>
      </div>
      <Separator className="bg-white/5" />
      <nav className="flex-1 space-y-2 p-4">
        {navigation.map((item) => {
          const href = tenantId ? `/dashboard/${tenantId}${item.href}` : "#";
          const isActive = pathname?.startsWith(href);
          return (
            <Link
              key={item.name}
              href={href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-300 ${
                isActive
                  ? "bg-primary/10 text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
              }`}
            >
              <item.icon className={`h-4 w-4 ${isActive ? "text-primary" : "text-muted-foreground/70"}`} />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <Separator className="bg-white/5" />
      <div className="p-4">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 rounded-xl text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all"
          onClick={handleLogout}
        >
          <LogOut className="h-4 w-4 text-muted-foreground/70" />
          Logout
        </Button>
      </div>
    </div>
  );
}
