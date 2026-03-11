import { useEffect, useState, useCallback } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { IconSearch } from "@/components/icons/NavIcons";

const COMMANDS = [
  { id: "overview",       label: "Go to Overview",       href: "/dashboard",        section: "Navigate" },
  { id: "chatbots",       label: "Go to Chatbots",        href: "/chatbots",         section: "Navigate" },
  { id: "conversations",  label: "Go to Conversations",   href: "/conversations",    section: "Navigate" },
  { id: "intelligence",   label: "Go to Intelligence",    href: "/intelligence",     section: "Navigate" },
  { id: "settings",       label: "Go to Settings",        href: "/settings",         section: "Navigate" },
  { id: "new-chatbot",    label: "New chatbot",           href: "/chatbots/new",     section: "Actions" },
  { id: "team",           label: "Manage team",           href: "/settings/team",    section: "Settings" },
  { id: "billing",        label: "Billing & plans",       href: "/settings/billing", section: "Settings" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const openPalette = useCallback(() => setOpen(true), []);

  useEffect(() => {
    window.addEventListener("open-command-palette", openPalette);
    return () => window.removeEventListener("open-command-palette", openPalette);
  }, [openPalette]);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleSelect = (href: string) => {
    setOpen(false);
    navigate(href);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20 backdrop-blur-[1px]" />

      {/* Palette */}
      <div
        className="relative w-full max-w-lg mx-4 bg-white rounded-2xl shadow-2xl border border-[#f0ebe3] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="w-full">
          {/* Search input */}
          <div className="flex items-center gap-2.5 px-4 py-3 border-b border-[#f0ebe3]">
            <IconSearch size={14} className="stroke-gray-400 flex-shrink-0" />
            <Command.Input
              placeholder="Search or jump to…"
              className="flex-1 text-[13px] text-gray-700 outline-none placeholder-gray-400 bg-transparent"
              autoFocus
            />
            <kbd className="text-[10px] font-medium bg-[#faf8f5] border border-[#e8e2d8] rounded px-1.5 py-0.5 text-gray-400">esc</kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto py-2">
            <Command.Empty className="py-8 text-center text-[12px] text-gray-400">
              No results found.
            </Command.Empty>

            {["Navigate", "Actions", "Settings"].map((section) => {
              const items = COMMANDS.filter((c) => c.section === section);
              if (items.length === 0) return null;
              return (
                <Command.Group key={section} heading={section}
                  className="[&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-gray-400 [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide"
                >
                  {items.map((cmd) => (
                    <Command.Item
                      key={cmd.id}
                      value={cmd.label}
                      onSelect={() => handleSelect(cmd.href)}
                      className="flex items-center gap-2.5 px-4 py-2 text-[13px] text-gray-700 cursor-pointer hover:bg-[#faf8f5] data-[selected=true]:bg-primary-50 data-[selected=true]:text-primary-600 transition-colors"
                    >
                      {cmd.label}
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
