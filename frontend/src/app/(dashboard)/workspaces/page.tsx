"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useWorkspace } from "@/hooks/useWorkspace";

export default function WorkspacesPage() {
  const router = useRouter();
  const { workspaces, fetchWorkspaces, createWorkspace, switchWorkspace } =
    useWorkspace();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    try {
      await createWorkspace(name.trim());
      setShowCreate(false);
      setName("");
      router.push("/");
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Workspaces</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {workspaces.map((ws) => (
          <Card
            key={ws.id}
            className="cursor-pointer hover:shadow-md transition-all duration-200"
            onClick={() => {
              switchWorkspace(ws);
              router.push("/");
            }}
          >
            <CardContent className="py-6">
              <h3 className="text-lg font-semibold text-gray-900">{ws.name}</h3>
              <p className="mt-1 text-sm text-gray-500">{ws.slug}</p>
              <span className="mt-3 inline-block rounded-full bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700">
                {ws.plan}
              </span>
            </CardContent>
          </Card>
        ))}

        <Card
          className="cursor-pointer border-2 border-dashed border-gray-300 hover:border-primary-400 hover:shadow-md transition-all duration-200"
          onClick={() => setShowCreate(true)}
        >
          <CardContent className="flex flex-col items-center justify-center py-8 text-gray-400 hover:text-primary-500">
            <Plus className="h-8 w-8 mb-2" />
            <p className="text-sm font-medium">Create new workspace</p>
          </CardContent>
        </Card>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md">
            <CardContent className="pt-6 pb-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Create workspace
              </h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <Input
                  label="Workspace name"
                  placeholder="My workspace"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
                <div className="flex gap-3 justify-end">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setShowCreate(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" loading={loading}>
                    Create
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
