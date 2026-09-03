// frontend/src/lib/socket.ts
import { io, Socket } from "socket.io-client";
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

let socket: Socket | null = null;
let joinedWorkspaceId: string | null = null;
let unsubWorkspace: (() => void) | null = null;

function _joinRoom(workspaceId: string) {
  if (!socket?.connected) return;
  if (joinedWorkspaceId === workspaceId) return;
  if (joinedWorkspaceId) {
    socket.emit("leave_workspace", { workspace_id: joinedWorkspaceId });
  }
  socket.emit("join_workspace", { workspace_id: workspaceId });
  joinedWorkspaceId = workspaceId;
}

export function getSocket(): Socket {
  if (socket) return socket;
  socket = io(import.meta.env.VITE_API_URL || "http://localhost:8000", {
    auth: (cb) => {
      cb({ token: useAuthStore.getState().tokens?.access_token });
    },
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });

  // Join workspace room on connect (and on reconnect)
  socket.on("connect", () => {
    joinedWorkspaceId = null; // reset so _joinRoom re-emits
    const workspace = useWorkspaceStore.getState().currentWorkspace;
    if (workspace) {
      _joinRoom(workspace.id);
    }
  });

  // Also watch for workspace changes (covers the case where
  // the socket connects before the workspace store is populated)
  unsubWorkspace = useWorkspaceStore.subscribe((state, prev) => {
    const wsId = state.currentWorkspace?.id;
    const prevId = prev.currentWorkspace?.id;
    if (wsId && wsId !== prevId) {
      _joinRoom(wsId);
    }
  });

  // On auth failure, try refreshing the token and reconnecting
  socket.on("connect_error", async (err) => {
    if (err.message?.includes("token") || err.message?.includes("Missing")) {
      const { getTokens, setTokens } = await import("./auth");
      const tokens = getTokens();
      if (!tokens?.refresh_token) return;
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/auth/refresh`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: tokens.refresh_token }),
          },
        );
        if (res.ok) {
          const data = await res.json();
          setTokens(data);
          useAuthStore.setState({ tokens: data });
          socket?.connect();
        }
      } catch {
        // Refresh failed — user will be redirected by next API call
      }
    }
  });

  return socket;
}

/**
 * Update the socket auth token and force a reconnect.
 * Call this after a successful token refresh so the server
 * sees the new JWT on the next connection.
 */
export function reconnectSocket(): void {
  if (!socket) return;
  socket.disconnect().connect();
}

/**
 * Leave the current workspace room and join a new one.
 */
export function joinWorkspace(workspaceId: string): void {
  getSocket();
  _joinRoom(workspaceId);
}

export function disconnectSocket(): void {
  if (unsubWorkspace) {
    unsubWorkspace();
    unsubWorkspace = null;
  }
  if (socket) {
    socket.offAny();
    socket.disconnect();
  }
  socket = null;
  joinedWorkspaceId = null;
}

/**
 * Hook: subscribe to a Socket.IO event while the component is mounted.
 * Room join happens once in getSocket(), not per subscription.
 */
export function useSocketEvent<T = unknown>(
  event: string,
  handler: (data: T) => void,
  deps: unknown[] = [],
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const s = getSocket();

    const listener = (data: T) => handlerRef.current(data);
    s.on(event, listener);

    return () => {
      s.off(event, listener);
    };
  }, [event, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps
}
