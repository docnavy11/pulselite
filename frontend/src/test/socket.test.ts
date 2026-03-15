// frontend/src/test/socket.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock socket.io-client
const mockOn = vi.fn();
const mockOff = vi.fn();
const mockOffAny = vi.fn();
const mockEmit = vi.fn();
const mockDisconnect = vi.fn();

vi.mock("socket.io-client", () => ({
  io: vi.fn(() => ({
    on: mockOn,
    off: mockOff,
    offAny: mockOffAny,
    emit: mockEmit,
    disconnect: mockDisconnect,
    connected: true,
  })),
}));

// Mock stores
vi.mock("@/stores/auth-store", () => ({
  useAuthStore: {
    getState: () => ({ tokens: { access_token: "test-token" } }),
  },
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: {
    getState: () => ({ currentWorkspace: { id: "ws-123" } }),
  },
}));

// Mock React hooks for non-component usage
vi.mock("react", () => ({
  useEffect: (fn: () => void) => fn(),
  useRef: (val: unknown) => ({ current: val }),
}));

describe("socket", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("getSocket creates socket with auth token and registers connect handler", async () => {
    const { getSocket } = await import("@/lib/socket");
    const { io } = await import("socket.io-client");

    const s = getSocket();

    expect(io).toHaveBeenCalledWith("http://localhost:8000", {
      auth: { token: "test-token" },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
    expect(mockOn).toHaveBeenCalledWith("connect", expect.any(Function));

    // Simulate connect — should emit join_workspace
    const connectHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "connect",
    )![1] as () => void;
    connectHandler();
    expect(mockEmit).toHaveBeenCalledWith("join_workspace", {
      workspace_id: "ws-123",
    });
  });

  it("getSocket returns the same instance on second call", async () => {
    const { getSocket } = await import("@/lib/socket");

    const s1 = getSocket();
    const s2 = getSocket();
    expect(s1).toBe(s2);
  });

  it("disconnectSocket disconnects and clears singleton", async () => {
    const { getSocket, disconnectSocket } = await import("@/lib/socket");
    const { io } = await import("socket.io-client");

    getSocket();
    disconnectSocket();

    expect(mockDisconnect).toHaveBeenCalled();
    // After disconnect, getSocket should create a new instance
    getSocket();
    expect(io).toHaveBeenCalledTimes(2);
  });

  it("useSocketEvent subscribes and returns cleanup that unsubscribes", async () => {
    const { useSocketEvent } = await import("@/lib/socket");
    const handler = vi.fn();

    // useEffect mock runs fn immediately; we capture the cleanup
    const cleanups: (() => void)[] = [];
    const react = await import("react");
    vi.spyOn(react, "useEffect" as never).mockImplementation(
      ((fn: () => (() => void) | void) => {
        const cleanup = fn();
        if (cleanup) cleanups.push(cleanup);
      }) as never,
    );

    useSocketEvent("crawl:progress", handler);

    expect(mockOn).toHaveBeenCalledWith("crawl:progress", expect.any(Function));

    // Run cleanup
    cleanups.forEach((c) => c());
    expect(mockOff).toHaveBeenCalledWith("crawl:progress", expect.any(Function));
  });
});
