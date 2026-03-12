import { useState, useCallback, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { CommandPalette } from "@/components/CommandPalette";
import { ToastProvider } from "@/components/ui/Toast";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { CopilotProvider } from "@/components/copilot/CopilotProvider";
import { CopilotPanel } from "@/components/copilot/CopilotPanel";

function DashboardShell() {
  useKeyboardShortcuts();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Stable reference so Sidebar's useEffect dep array doesn't re-fire on every render
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  const [sidebarPinned, setSidebarPinned] = useState<boolean>(() => {
    const stored = localStorage.getItem("sidebar-pinned");
    return stored === null ? true : stored === "true";
  });

  // Persist pin preference on every change
  useEffect(() => {
    localStorage.setItem("sidebar-pinned", String(sidebarPinned));
  }, [sidebarPinned]);

  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        {/* Backdrop — mobile/tablet only, dismisses drawer */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/40 z-40 xl:hidden"
            onClick={closeSidebar}
          />
        )}
        <Sidebar
          isOpen={sidebarOpen}
          onClose={closeSidebar}
          pinned={sidebarPinned}
          onPinToggle={() => setSidebarPinned((p) => !p)}
        />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar onMenuToggle={() => setSidebarOpen((o) => !o)} />
          <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 overflow-auto bg-[#faf8f5] p-6">
              <Outlet />
            </main>
            {/* CopilotPanel hidden below xl */}
            <div className="hidden xl:flex">
              <CopilotPanel />
            </div>
          </div>
        </div>
      </div>
      <CommandPalette />
      <ToastProvider />
    </ProtectedRoute>
  );
}

export default function DashboardLayout() {
  return (
    <CopilotProvider>
      <DashboardShell />
    </CopilotProvider>
  );
}
