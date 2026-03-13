// frontend/src/lib/socket.ts
import { io, Socket } from "socket.io-client";
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

let socket: Socket | null = null;
let joinedWorkspaceId: string | null = null;

export function getSocket(): Socket {
  if (socket) return socket;
  const token = useAuthStore.getState().tokens?.access_token;
  socket = io(import.meta.env.VITE_API_URL || "http://localhost:8000", {
    auth: { token },
    transports: ["websocket", "polling"],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });

  // Join workspace room once on connect (and on reconnect)
  const joinCurrentWorkspace = () => {
    const workspace = useWorkspaceStore.getState().currentWorkspace;
    if (workspace && socket) {
      socket.emit("join_workspace", { workspace_id: workspace.id });
      joinedWorkspaceId = workspace.id;
    }
  };
  socket.on("connect", joinCurrentWorkspace);

  return socket;
}

export function disconnectSocket(): void {
  socket?.disconnect();
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
