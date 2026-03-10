"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  Bot,
  MessageSquare,
  Brain,
  Settings,
  Users,
  Sparkles,
  Webhook,
  ShieldAlert,
  Database,
  Cpu,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chatbots", label: "Chatbots", icon: Bot },
  { href: "/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/intelligence", label: "Intelligence", icon: Brain },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/settings/team", label: "Team", icon: Users },
  { href: "/settings/webhooks", label: "Webhooks", icon: Webhook },
  { href: "/settings/security", label: "Security", icon: ShieldAlert },
  { href: "/settings/data-retention", label: "Data Retention", icon: Database },
  { href: "/settings/llm", label: "AI Models", icon: Cpu },
];

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  growth: "Growth",
  enterprise: "Enterprise",
};

export function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const plan = workspace?.plan ?? "free";

  return (
    <aside className="flex h-screen w-64 flex-col bg-sidebar-bg">
      <div className="flex h-16 items-center px-6">
        <Link
          href="/"
          className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-300 bg-clip-text text-transparent"
        >
          Pulse
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-sidebar-hover text-sidebar-active"
                  : "text-sidebar-text hover:bg-sidebar-hover hover:text-sidebar-active",
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-700 px-4 py-4">
        <Link href="/settings/billing" className="block mb-3">
          <div className="rounded-lg bg-slate-800 px-3 py-2 hover:bg-slate-700 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary-400" />
                <span className="text-xs text-slate-400">Plan</span>
              </div>
              <span className="text-xs font-semibold text-primary-400 capitalize">
                {PLAN_LABELS[plan] ?? plan}
              </span>
            </div>
            {plan === "free" && (
              <p className="text-[10px] text-slate-500 mt-0.5">Upgrade for more features</p>
            )}
          </div>
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-600 text-sm font-medium text-white">
            {user?.name?.charAt(0)?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-white">
              {user?.name || "User"}
            </p>
            <p className="truncate text-xs text-sidebar-text">
              {user?.email || ""}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
