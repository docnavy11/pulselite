"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { api } from "@/lib/api";
import { Workspace } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { tokens, isLoading, initialize } = useAuthStore();
  const { currentWorkspace, setCurrentWorkspace, setWorkspaces } =
    useWorkspaceStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && !tokens) {
      router.push("/login");
    }
  }, [isLoading, tokens, router]);

  useEffect(() => {
    if (!tokens || currentWorkspace) return;
    api
      .get<Workspace[]>("/api/v1/workspaces")
      .then((workspaces) => {
        setWorkspaces(workspaces);
        if (workspaces.length > 0) {
          setCurrentWorkspace(workspaces[0]);
        }
      })
      .catch(() => {});
  }, [tokens, currentWorkspace, setWorkspaces, setCurrentWorkspace]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  if (!tokens) return null;

  return <>{children}</>;
}
