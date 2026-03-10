import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Workspace } from "@/lib/types";

const WS_A: Workspace = { id: "ws-a", name: "Alpha", slug: "alpha", plan: "free" };
const WS_B: Workspace = { id: "ws-b", name: "Beta", slug: "beta", plan: "starter" };

beforeEach(() => {
  useWorkspaceStore.setState({ currentWorkspace: null, workspaces: [] });
});

describe("setCurrentWorkspace", () => {
  it("sets the current workspace", () => {
    useWorkspaceStore.getState().setCurrentWorkspace(WS_A);
    expect(useWorkspaceStore.getState().currentWorkspace).toEqual(WS_A);
  });

  it("replaces a previously set workspace", () => {
    useWorkspaceStore.getState().setCurrentWorkspace(WS_A);
    useWorkspaceStore.getState().setCurrentWorkspace(WS_B);
    expect(useWorkspaceStore.getState().currentWorkspace).toEqual(WS_B);
  });
});

describe("setWorkspaces", () => {
  it("stores a list of workspaces", () => {
    useWorkspaceStore.getState().setWorkspaces([WS_A, WS_B]);
    expect(useWorkspaceStore.getState().workspaces).toHaveLength(2);
  });

  it("replaces the existing list", () => {
    useWorkspaceStore.getState().setWorkspaces([WS_A, WS_B]);
    useWorkspaceStore.getState().setWorkspaces([WS_A]);
    expect(useWorkspaceStore.getState().workspaces).toHaveLength(1);
    expect(useWorkspaceStore.getState().workspaces[0]).toEqual(WS_A);
  });
});
