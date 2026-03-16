import { Link, useLocation, useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import { useEffect, useRef, useState } from "react";
import {
  IconOverview, IconChatbots, IconConversations,
  IconIntelligence, IconLogs, IconSettings, IconChevronDown,
  IconAdmin,
} from "@/components/icons/NavIcons";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { useDeploymentStore } from "@/stores/deployment-store";
import { createWorkspace } from "@/lib/api-functions";
import type { Workspace } from "@/lib/types";

const SETTINGS_CHILDREN = [
  { href: "/settings",                label: "General" },
  { href: "/settings/team",           label: "Team" },
  { href: "/settings/billing",        label: "Billing" },
  { href: "/settings/integrations",   label: "Integrations" },
  { href: "/settings/llm",            label: "AI Models" },
  { href: "/settings/security",       label: "Security" },
  { href: "/settings/data-retention", label: "Data Retention" },
  { href: "/settings/webhooks",       label: "Webhooks" },
  { href: "/settings/intelligence",  label: "Intelligence" },
];

const MAIN_NAV = [
  { href: "/dashboard",     label: "Overview",      Icon: IconOverview },
  { href: "/chatbots",      label: "Chatbots",      Icon: IconChatbots },
  { href: "/conversations", label: "Conversations", Icon: IconConversations },
  { href: "/logs",          label: "Logs",          Icon: IconLogs },
  { href: "/intelligence",  label: "Intelligence",  Icon: IconIntelligence },
  { href: "/admin",         label: "Admin",          Icon: IconAdmin },
];

const PLAN_LABELS: Record<string, string> = {
  free: "Free", starter: "Starter", growth: "Growth", enterprise: "Enterprise",
};

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  pinned: boolean;
  onPinToggle: () => void;
}

export function Sidebar({ isOpen, onClose, pinned, onPinToggle }: SidebarProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const isCloud = useDeploymentStore((s) => s.isCloud);
  const plan = workspace?.plan ?? "free";
  const isSettingsActive = pathname.startsWith("/settings");
  const [settingsOpen, setSettingsOpen] = useState(isSettingsActive);
  const [wsSwitcherOpen, setWsSwitcherOpen] = useState(false);
  const [creatingWs, setCreatingWs] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [savingWs, setSavingWs] = useState(false);
  const newWsInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (creatingWs) setTimeout(() => newWsInputRef.current?.focus(), 50);
  }, [creatingWs]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setWsSwitcherOpen(false);
        setCreatingWs(false);
        setNewWsName("");
      }
    }
    if (wsSwitcherOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [wsSwitcherOpen]);

  // Collapse settings sub-nav when switching to rail mode
  useEffect(() => {
    if (!pinned) setSettingsOpen(false);
  }, [pinned, setSettingsOpen]);

  // Close drawer on route change only when not pinned (mobile behaviour)
  useEffect(() => {
    if (!pinned) onClose();
  }, [pathname, pinned, onClose]);

  async function handleCreateWorkspace() {
    const name = newWsName.trim();
    if (!name) return;
    setSavingWs(true);
    try {
      const ws = await createWorkspace(name);
      useWorkspaceStore.getState().setWorkspaces([...workspaces, ws]);
      useWorkspaceStore.getState().setCurrentWorkspace(ws);
      setWsSwitcherOpen(false);
      setCreatingWs(false);
      setNewWsName("");
    } catch (err) {
      console.error("Failed to create workspace:", err);
    } finally {
      setSavingWs(false);
    }
  }

  const logout = useAuthStore((s) => s.logout);
  const { isOpen: copilotOpen, toggle: toggleCopilot } = useCopilot();
  const wsInitial = workspace?.name?.[0]?.toUpperCase() ?? "W";
  const userName = user?.name ?? user?.email ?? "";
  const userInitial = userName[0]?.toUpperCase() ?? "?";

  return (
    <aside className={clsx(
      "flex h-screen flex-col bg-white border-r border-[#f0ebe3]",
      // Mobile always w-56; desktop: w-56 when pinned, w-10 when not
      pinned ? "w-56" : "w-56 xl:w-10",
      // Below xl: fixed overlay, slides in/out
      "fixed inset-y-0 left-0 z-50 transition-[width,transform] duration-200 ease-in-out",
      // At xl+: back to normal document flow
      "xl:static xl:z-auto xl:flex-shrink-0 xl:translate-x-0",
      // Open/closed (only meaningful below xl)
      isOpen ? "translate-x-0" : "-translate-x-full",
    )}>
      {/* ── Expanded header (logo + workspace switcher) ──────────────────────
          Hidden in desktop rail mode; always visible on mobile (drawer). */}
      <div className={clsx(
        "px-4 pt-5 pb-4 border-b border-[#f0ebe3]",
        !pinned && "xl:hidden",
      )}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 bg-primary-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 7 L3 7 L5 3 L7 11 L9 5 L11 7 L13 7"
                stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-[17px] font-black tracking-tight text-gray-900">pulse</span>
          {/* Pin button — desktop only, right-aligned in expanded header */}
          <button
            onClick={onPinToggle}
            className="hidden xl:flex ml-auto items-center justify-center w-6 h-6 rounded-md hover:bg-[#faf8f5] transition-colors flex-shrink-0 text-primary-500"
            aria-label={pinned ? "Unpin sidebar" : "Pin sidebar"}
          >
            {/* Filled pin icon = pinned state */}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
              <path d="M8 1L11 4L9 6L9.5 9L6 7.5L2.5 9L3 6L1 4L4 1H8Z" />
              <line x1="6" y1="7.5" x2="6" y2="11.5" stroke="white" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Workspace switcher */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => { setWsSwitcherOpen((o) => !o); setCreatingWs(false); setNewWsName(""); }}
            className="flex items-center gap-2 w-full px-2 py-1.5 bg-[#faf8f5] rounded-lg hover:bg-[#f5f0ea] transition-colors"
          >
            <div className="w-5 h-5 rounded-[5px] bg-gradient-to-br from-primary-500 to-amber-400 flex items-center justify-center text-white text-[9px] font-bold flex-shrink-0">
              {wsInitial}
            </div>
            <span className="text-[11px] font-semibold text-gray-600 flex-1 text-left truncate">
              {workspace?.name ?? "Loading…"}
            </span>
            <IconChevronDown className={clsx("transition-transform", wsSwitcherOpen ? "rotate-180" : "", "stroke-gray-300")} />
          </button>

          {wsSwitcherOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-[#f0ebe3] rounded-xl shadow-lg z-50 overflow-hidden">
              {/* Workspace list */}
              {workspaces.map((ws: Workspace) => (
                <button
                  key={ws.id}
                  onClick={() => { setCurrentWorkspace(ws); setWsSwitcherOpen(false); }}
                  className={clsx(
                    "flex items-center gap-2 w-full px-3 py-2 text-left text-[11px] transition-colors",
                    ws.id === workspace?.id
                      ? "bg-primary-50 text-primary-600 font-semibold"
                      : "text-gray-600 hover:bg-[#faf8f5]"
                  )}
                >
                  <div className="w-4 h-4 rounded-[4px] bg-gradient-to-br from-primary-500 to-amber-400 flex items-center justify-center text-white text-[8px] font-bold flex-shrink-0">
                    {ws.name[0]?.toUpperCase()}
                  </div>
                  <span className="flex-1 truncate">{ws.name}</span>
                  {ws.id === workspace?.id && (
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path d="M2 5l2 2 4-4" stroke="#ff6b35" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                </button>
              ))}

              {/* Divider */}
              <div className="h-px bg-[#f0ebe3] mx-2" />

              {/* New workspace */}
              {creatingWs ? (
                <div className="px-3 py-2 space-y-1.5">
                  <input
                    ref={newWsInputRef}
                    value={newWsName}
                    onChange={(e) => setNewWsName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateWorkspace();
                      if (e.key === "Escape") { setCreatingWs(false); setNewWsName(""); }
                    }}
                    placeholder="Workspace name"
                    className="w-full rounded-md border border-gray-300 px-2 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <div className="flex gap-1.5">
                    <button
                      onClick={handleCreateWorkspace}
                      disabled={savingWs || !newWsName.trim()}
                      className="flex-1 py-1 text-[10px] font-semibold bg-primary-500 hover:bg-primary-600 text-white rounded-md disabled:opacity-50 transition-colors"
                    >
                      {savingWs ? "Creating…" : "Create"}
                    </button>
                    <button
                      onClick={() => { setCreatingWs(false); setNewWsName(""); }}
                      className="flex-1 py-1 text-[10px] font-medium text-gray-500 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setCreatingWs(true)}
                  className="flex items-center gap-2 w-full px-3 py-2 text-[11px] text-gray-400 hover:text-gray-600 hover:bg-[#faf8f5] transition-colors"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M6 2v8M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                  New workspace
                </button>
              )}

              {/* Settings link */}
              <Link
                to="/settings"
                onClick={() => setWsSwitcherOpen(false)}
                className="flex items-center gap-2 w-full px-3 py-2 text-[11px] text-gray-400 hover:text-gray-600 hover:bg-[#faf8f5] transition-colors border-t border-[#f0ebe3]"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <circle cx="6" cy="6" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M6 1v1.5M6 9.5V11M1 6h1.5M9.5 6H11M2.4 2.4l1.1 1.1M8.5 8.5l1.1 1.1M9.6 2.4L8.5 3.5M3.5 8.5L2.4 9.6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
                Workspace settings
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* ── Rail header (pin button only) ────────────────────────────────────
          Only shown on desktop when sidebar is in icon-rail (unpinned) mode. */}
      <div className={clsx(
        "hidden border-b border-[#f0ebe3] py-4 justify-center",
        !pinned && "xl:flex",
      )}>
        <button
          onClick={onPinToggle}
          className="flex items-center justify-center w-6 h-6 rounded-md hover:bg-[#faf8f5] transition-colors text-gray-300"
          aria-label="Pin sidebar"
        >
          {/* Outline pin icon = unpinned state */}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M8 1L11 4L9 6L9.5 9L6 7.5L2.5 9L3 6L1 4L4 1H8Z"
              stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
            <line x1="6" y1="7.5" x2="6" y2="11.5"
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {MAIN_NAV.map(({ href, label, Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              to={href}
              className={clsx(
                "flex items-center py-[7px] rounded-lg text-[12px] font-medium transition-all",
                pinned ? "gap-2.5 px-2.5" : "gap-2.5 px-2.5 xl:justify-center xl:gap-0 xl:px-0",
                active
                  ? "bg-primary-50 text-primary-500 font-semibold"
                  : "text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700"
              )}
            >
              <Icon
                size={16}
                className={active ? "stroke-primary-500" : "stroke-gray-400"}
              />
              <span className={clsx(!pinned && "xl:hidden")}>{label}</span>
            </Link>
          );
        })}

        {/* Divider */}
        <div className="h-px bg-[#f0ebe3] my-2 mx-1" />

        {/* Settings — collapsible */}
        <button
          onClick={() => pinned ? setSettingsOpen((o) => !o) : navigate("/settings")}
          className={clsx(
            "flex items-center py-[7px] rounded-lg text-[12px] font-medium w-full transition-all",
            pinned ? "gap-2.5 px-2.5" : "gap-2.5 px-2.5 xl:justify-center xl:gap-0 xl:px-0",
            isSettingsActive
              ? "bg-primary-50 text-primary-500 font-semibold"
              : "text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700"
          )}
        >
          <IconSettings
            size={16}
            className={isSettingsActive ? "stroke-primary-500" : "stroke-gray-400"}
          />
          <span className={clsx("flex-1 text-left", !pinned && "xl:hidden")}>Settings</span>
          <IconChevronDown
            className={clsx(
              "transition-transform",
              !pinned && "xl:hidden",
              settingsOpen ? "rotate-0 stroke-gray-400" : "-rotate-90 stroke-gray-300"
            )}
          />
        </button>

        {settingsOpen && (
          <div className="ml-6 mt-0.5 space-y-0.5">
            {SETTINGS_CHILDREN
              .filter(({ href }) => isCloud || href !== "/settings/billing")
              .map(({ href, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  to={href}
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

      {/* Activity console toggle */}
      <div className={clsx("px-3 pb-0.5", !pinned && "xl:hidden")}>
        <button
          onClick={() => window.dispatchEvent(new CustomEvent("toggle-activity-console"))}
          className="flex items-center gap-2.5 w-full px-2.5 py-[7px] rounded-lg text-[12px] font-medium text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700 transition-all"
        >
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" className="text-gray-400">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          <span className="flex-1 text-left">Activity</span>
        </button>
      </div>

      {/* Copilot toggle */}
      <div className={clsx("px-3 pb-2", !pinned && "xl:hidden")}>
        <button
          onClick={toggleCopilot}
          className={clsx(
            "flex items-center gap-2.5 w-full px-2.5 py-[7px] rounded-lg text-[12px] font-medium transition-all",
            copilotOpen
              ? "bg-primary-50 text-primary-500 font-semibold"
              : "text-gray-500 hover:bg-[#faf8f5] hover:text-gray-700"
          )}
        >
          <span className={clsx("text-[14px] leading-none", copilotOpen ? "text-primary-500" : "text-gray-400")}>✦</span>
          <span className="flex-1 text-left">Copilot</span>
          <span className="text-[10px] text-gray-300">⌘J</span>
        </button>
      </div>

      {/* User footer */}
      <div className={clsx("px-3 py-3 border-t border-[#f0ebe3]", !pinned && "xl:hidden")}>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
            {userInitial}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-semibold text-gray-700 truncate">
              {userName || "User"}
            </div>
            <div className="text-[10px] text-gray-400 truncate">
              {isCloud ? (PLAN_LABELS[plan] ?? "Free") + " plan" : "Self-Hosted"}
            </div>
          </div>
          <button
            onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center justify-center w-6 h-6 rounded-md hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600 flex-shrink-0"
            aria-label="Sign out"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
