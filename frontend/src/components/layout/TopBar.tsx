"use client";

import { usePathname } from "next/navigation";
import { IconBell, IconPlus, IconSearch } from "@/components/icons/NavIcons";
import { Breadcrumb } from "@/components/ui/Breadcrumb";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/chatbots": "Chatbots",
  "/conversations": "Conversations",
  "/intelligence": "Intelligence",
  "/settings": "Settings",
  "/settings/team": "Settings",
  "/settings/billing": "Settings",
  "/settings/integrations": "Settings",
  "/settings/llm": "Settings",
  "/settings/security": "Settings",
  "/settings/data-retention": "Settings",
  "/settings/webhooks": "Settings",
};

const NEW_BUTTON_LABELS: Record<string, string> = {
  "/chatbots": "New chatbot",
  "/conversations": "Export",
  "/intelligence": "Add source",
};

function getPageTitle(pathname: string): string {
  // Exact match first
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  // Chatbot sub-pages
  if (pathname.startsWith("/chatbots/")) return "Chatbots";
  return "";
}

export function TopBar() {
  const pathname = usePathname();
  const pageTitle = getPageTitle(pathname);
  const newLabel = NEW_BUTTON_LABELS[pathname] ?? "New";

  const openCommandPalette = () => {
    window.dispatchEvent(new CustomEvent("open-command-palette"));
  };

  return (
    <header className="h-12 flex items-center gap-3 px-5 bg-white border-b border-[#f0ebe3] flex-shrink-0">
      {/* Left: breadcrumb */}
      <div className="flex-1 min-w-0">
        <Breadcrumb />
      </div>

      {/* Centre-right: ⌘K trigger */}
      <button
        onClick={openCommandPalette}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#faf8f5] border border-[#f0ebe3] text-gray-400 hover:border-[#e0dbd2] hover:text-gray-600 transition-colors text-[11px]"
      >
        <IconSearch size={11} className="stroke-gray-400" />
        <span>Search…</span>
        <kbd className="ml-1 text-[9px] font-medium bg-white border border-[#e8e2d8] rounded px-1 py-0.5 text-gray-400">⌘K</kbd>
      </button>

      {/* Bell */}
      <button className="p-1.5 rounded-lg hover:bg-[#faf8f5] transition-colors">
        <IconBell size={14} className="stroke-gray-400" />
      </button>

      {/* + New */}
      <button className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-[11px] font-semibold transition-colors">
        <IconPlus size={11} className="stroke-white" />
        {newLabel}
      </button>
    </header>
  );
}
