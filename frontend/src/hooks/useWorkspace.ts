import { useCallback } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { api } from "@/lib/api";
import { Workspace } from "@/lib/types";

export function useWorkspace() {
  const { currentWorkspace, workspaces, setCurrentWorkspace, setWorkspaces } =
    useWorkspaceStore();

  const fetchWorkspaces = useCallback(async () => {
    const data = await api.get<Workspace[]>("/api/v1/workspaces");
    setWorkspaces(data);
    if (data.length === 1 && !currentWorkspace) {
      setCurrentWorkspace(data[0]);
    }
  }, [setWorkspaces, setCurrentWorkspace, currentWorkspace]);

  const createWorkspace = useCallback(
    async (name: string) => {
      const workspace = await api.post<Workspace>("/api/v1/workspaces", {
        name,
      });
      setWorkspaces([...workspaces, workspace]);
      setCurrentWorkspace(workspace);
      return workspace;
    },
    [workspaces, setWorkspaces, setCurrentWorkspace],
  );

  const switchWorkspace = useCallback(
    (workspace: Workspace) => {
      setCurrentWorkspace(workspace);
    },
    [setCurrentWorkspace],
  );

  return {
    currentWorkspace,
    workspaces,
    fetchWorkspaces,
    createWorkspace,
    switchWorkspace,
  };
}
