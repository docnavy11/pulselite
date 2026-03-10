"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { useState } from "react";
import {
  IconOverview, IconChatbots, IconConversations,
  IconIntelligence, IconSettings, IconChevronDown,
} from "@/components/icons/NavIcons";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const SETTINGS_CHILDREN = [
  { href: "/settings",                label: "General" },
  { href: "/settings/team",           label: "Team" },
  { href: "/settings/billing",        label: "Billing" },
  { href: "/settings/integrations",   label: "Integrations" },
  { href: "/settings/llm",            label: "AI Models" },
  { href: "/settings/security",       label: "Security" },
  { href: "/settings/data-retention", label: "Data Retention" },
  { href: "/settings/webhooks",       label: "Webhooks" },
];

const MAIN_NAV = [
  { href: "/dashboard",     label: "Overview",      Icon: IconOverview },
  { href: "/chatbots",      label: "Chatbots",      Icon: IconChatbots },
  { href: "/conversations", label: "Conversations", Icon: IconConversations },
  { href: "/intelligence",  label: "Intelligence",  Icon: IconIntelligence },
];

const PLAN_LABELS: Record<string, string> = {
  free: "Free", starter: "Starter", growth: "Growth", enterprise: "Enterprise",
};

export function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const plan = workspace?.plan ?? "free";
  const isSettingsActive = pathname.startsWith("/settings");
  const [settingsOpen, setSettingsOpen] = useState(isSettingsActive);

  const wsInitial = workspace?.name?.[0]?.toUpperCase() ?? "W";
  const userName = user?.name ?? user?.email ?? "";
  const userInitial = userName[0]?.toUpperCase() ?? "?";

  return (
    <aside className="flex h-screen w-56 flex-col bg-white border-r border-[#f0ebe3] flex-shrink-0">
      {/* Logo + workspace switcher */}
      <div className="px-4 pt-5 pb-4 border-b border-[#f0ebe3]">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 7 L3 7 L5 3 L7 11 L9 5 L11 7 L13 7"
                stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-[17px] font-black tracking-tight text-gray-900">pulse</span>
        </div>

        {/* Workspace switcher */}
        <button className="flex items-center gap-2 w-full px-2 py-1.5 bg-[#faf8f5] rounded-lg hover:bg-[#f5f0ea] transition-colors">
          <div className="w-5 h-5 rounded-[5px] bg-gradient-to-br from-primary-500 to-amber-400 flex items-center justify-center text-white text-[9px] font-bold flex-shrink-0">
            {wsInitial}
          </div>
          <span className="text-[11px] font-semibold text-gray-600 flex-1 text-left truncate">
            {workspace?.name ?? "Loading…"}
          </span>
          <IconChevronDown className="stroke-gray-300" />
        </button>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {MAIN_NAV.map(({ href, label, Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-2.5 px-2.5 py-[7px] rounded-lg text-[12px] font-medium transition-all",
                active
                  ? "bg-primary-50 text-primary-500 font-semibold"
                  : "text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700"
              )}
            >
              <Icon
                size={16}
                className={active ? "stroke-primary-500" : "stroke-gray-400"}
              />
              {label}
            </Link>
          );
        })}

        {/* Divider */}
        <div className="h-px bg-[#f0ebe3] my-2 mx-1" />

        {/* Settings — collapsible */}
        <button
          onClick={() => setSettingsOpen((o) => !o)}
          className={clsx(
            "flex items-center gap-2.5 px-2.5 py-[7px] rounded-lg text-[12px] font-medium w-full transition-all",
            isSettingsActive
              ? "bg-primary-50 text-primary-500 font-semibold"
              : "text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700"
          )}
        >
          <IconSettings
            size={16}
            className={isSettingsActive ? "stroke-primary-500" : "stroke-gray-400"}
          />
          <span className="flex-1 text-left">Settings</span>
          <IconChevronDown
            className={clsx(
              "transition-transform",
              settingsOpen ? "rotate-0 stroke-gray-400" : "-rotate-90 stroke-gray-300"
            )}
          />
        </button>

        {settingsOpen && (
          <div className="ml-6 mt-0.5 space-y-0.5">
            {SETTINGS_CHILDREN.map(({ href, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={clsx(
                    "block px-2.5 py-[5px] rounded-md text-[11px] transition-colors",
                    active
                      ? "text-primary-500 font-semibold bg-primary-50"
                      : "text-gray-400 hover:text-gray-700 hover:bg-[#faf8f5]"
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* User footer */}
      <div className="px-3 py-3 border-t border-[#f0ebe3]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
            {userInitial}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-semibold text-gray-700 truncate">
              {userName || "User"}
            </div>
            <div className="text-[10px] text-gray-400 truncate">
              {PLAN_LABELS[plan] ?? "Free"} plan
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
