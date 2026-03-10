import { create } from "zustand";
import { Workspace } from "@/lib/types";

interface WorkspaceState {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  setCurrentWorkspace: (workspace: Workspace) => void;
  setWorkspaces: (workspaces: Workspace[]) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  currentWorkspace: null,
  workspaces: [],

  setCurrentWorkspace: (workspace: Workspace) => {
    set({ currentWorkspace: workspace });
  },

  setWorkspaces: (workspaces: Workspace[]) => {
    set({ workspaces });
  },
}));
