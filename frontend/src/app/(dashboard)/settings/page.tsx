"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { requestDataExport, deleteWorkspace } from "@/lib/api-functions";

const tabs = ["General", "Team", "Integrations", "Billing"] as const;
type Tab = (typeof tabs)[number];


export default function SettingsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [activeTab, setActiveTab] = useState<Tab>("General");
  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [workspaceName, setWorkspaceName] = useState(workspace?.name || "");

  function handleTabClick(tab: Tab) {
    if (tab === "Integrations") {
      router.push("/settings/integrations");
      return;
    }
    if (tab === "Billing") {
      router.push("/settings/billing");
      return;
    }
    setActiveTab(tab);
  }

  async function handleExport() {
    if (!workspace) return;
    setExporting(true);
    try {
      const result = await requestDataExport(workspace.id);
      setExportUrl(result.download_url);
    } catch {
      // handle error
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteWorkspace() {
    if (!workspace || deleteConfirmText !== workspace.name) return;
    try {
      await deleteWorkspace(workspace.id);
      router.push("/workspaces");
    } catch {
      // handle error
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabClick(tab)}
              className={clsx(
                "pb-3 text-sm font-medium border-b-2 transition-all duration-200",
                activeTab === tab
                  ? "border-primary-500 text-primary-500"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
              )}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "General" && (
        <div className="space-y-6 max-w-lg">
          <Card>
            <CardContent className="pt-6 pb-6 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">
                Workspace Settings
              </h2>
              <Input
                label="Workspace Name"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
              />
              <Input label="Timezone" defaultValue="UTC" />
              <Button size="sm" onClick={() => {}}>Save</Button>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6 pb-6 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">
                Data Export (GDPR)
              </h2>
              <p className="text-sm text-gray-500">
                Export all your workspace data for compliance.
              </p>
              <Button
                variant="secondary"
                onClick={handleExport}
                loading={exporting}
                size="sm"
              >
                Export My Data
              </Button>
              {exportUrl && (
                <a
                  href={exportUrl}
                  className="block text-sm text-primary-500 hover:text-primary-700 font-medium"
                >
                  Download export
                </a>
              )}
            </CardContent>
          </Card>

          <Card className="border-red-200">
            <CardContent className="pt-6 pb-6 space-y-4">
              <h2 className="text-sm font-semibold text-red-600">
                Danger Zone
              </h2>
              <p className="text-sm text-gray-500">
                Permanently delete this workspace and all its data.
              </p>
              <Button
                variant="danger"
                onClick={() => setShowDeleteConfirm(true)}
                size="sm"
              >
                Delete Workspace
              </Button>
            </CardContent>
          </Card>

          {showDeleteConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
              <Card className="w-full max-w-md">
                <CardContent className="pt-6 pb-6 space-y-4">
                  <h2 className="text-lg font-semibold text-red-600">
                    Delete Workspace
                  </h2>
                  <p className="text-sm text-gray-500">
                    This action is permanent and cannot be undone. Type{" "}
                    <strong>{workspace?.name}</strong> to confirm.
                  </p>
                  <Input
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    placeholder={workspace?.name}
                  />
                  <div className="flex gap-3 justify-end">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setShowDeleteConfirm(false);
                        setDeleteConfirmText("");
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="danger"
                      onClick={handleDeleteWorkspace}
                      disabled={deleteConfirmText !== workspace?.name}
                    >
                      Delete Forever
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {activeTab === "Team" && (
        <div className="py-4">
          <p className="text-sm text-gray-600">
            Manage team members and invitations on the{" "}
            <a href="/settings/team" className="text-blue-600 underline">Team page</a>.
          </p>
        </div>
      )}
    </div>
  );
}
