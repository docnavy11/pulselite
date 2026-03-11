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
  return (
    <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <div className="flex flex-1 overflow-hidden">
            <main className="flex-1 overflow-auto bg-[#faf8f5] p-6">
              <Outlet />
            </main>
            <CopilotPanel />
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
