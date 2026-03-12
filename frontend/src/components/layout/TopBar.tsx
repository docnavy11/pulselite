import { useLocation, useNavigate } from "react-router-dom";
import { IconBell, IconPlus, IconSearch } from "@/components/icons/NavIcons";
import { Breadcrumb } from "@/components/ui/Breadcrumb";

interface TopBarProps {
  onMenuToggle: () => void;
}

const NEW_BUTTON_ACTIONS: Record<string, { label: string; href: string }> = {
  "/chatbots":      { label: "New chatbot",  href: "/chatbots/new" },
  "/conversations": { label: "Export",       href: "/conversations" },
  "/intelligence":  { label: "Add source",   href: "/intelligence" },
};

export function TopBar({ onMenuToggle }: TopBarProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const action = NEW_BUTTON_ACTIONS[pathname] ?? { label: "New chatbot", href: "/chatbots/new" };

  const openCommandPalette = () => {
    window.dispatchEvent(new CustomEvent("open-command-palette"));
  };

  return (
    <header className="h-12 flex items-center gap-3 px-5 bg-white border-b border-[#f0ebe3] flex-shrink-0">
      {/* Hamburger — hidden at xl+ */}
      <button
        onClick={onMenuToggle}
        className="xl:hidden p-1.5 -ml-1.5 rounded-lg hover:bg-[#faf8f5] transition-colors"
        aria-label="Open menu"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2 4h12M2 8h12M2 12h12" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      {/* Left: breadcrumb — truncate wrapper prevents overflow on small screens */}
      <div className="flex-1 min-w-0 truncate max-w-[160px] sm:max-w-none">
        <Breadcrumb />
      </div>

      {/* Centre-right: ⌘K trigger */}
      <button
        onClick={openCommandPalette}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#faf8f5] border border-[#f0ebe3] text-gray-400 hover:border-[#e0dbd2] hover:text-gray-600 transition-colors text-[11px]"
      >
        <IconSearch size={11} className="stroke-gray-400" />
        <span className="hidden sm:inline">Search…</span>
        <kbd className="hidden sm:inline ml-1 text-[9px] font-medium bg-white border border-[#e8e2d8] rounded px-1 py-0.5 text-gray-400">⌘K</kbd>
      </button>

      {/* Bell */}
      <button className="p-1.5 rounded-lg hover:bg-[#faf8f5] transition-colors">
        <IconBell size={14} className="stroke-gray-400" />
      </button>

      {/* + New */}
      <button
        onClick={() => navigate(action.href)}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-[11px] font-semibold transition-colors"
      >
        <IconPlus size={11} className="stroke-white" />
        <span className="hidden sm:inline">{action.label}</span>
      </button>
    </header>
  );
}
