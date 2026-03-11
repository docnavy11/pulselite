"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { requestDataExport, deleteWorkspace } from "@/lib/api-functions";
import { useCopilot } from "@/components/copilot/CopilotProvider";

export default function SettingsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const { register } = useCopilot();

  useEffect(() => {
    register({ page: "settings", data: {} });
  }, [register]);
  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [workspaceName, setWorkspaceName] = useState(workspace?.name || "");

  useEffect(() => {
    if (workspace?.name) setWorkspaceName(workspace.name);
  }, [workspace?.name]);

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
      <h1 className="text-2xl font-bold text-gray-900 mb-6">General</h1>

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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
                <select
                  defaultValue={Intl.DateTimeFormat().resolvedOptions().timeZone}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {Intl.supportedValuesOf("timeZone").map((tz) => {
                    const offset = new Intl.DateTimeFormat("en", { timeZone: tz, timeZoneName: "shortOffset" })
                      .formatToParts(new Date())
                      .find((p) => p.type === "timeZoneName")?.value ?? "";
                    return (
                      <option key={tz} value={tz}>
                        {tz.replace(/_/g, " ")} ({offset})
                      </option>
                    );
                  })}
                </select>
              </div>
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
    </div>
  );
}
