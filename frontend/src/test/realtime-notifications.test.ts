import { describe, it, expect, vi, beforeEach } from "vitest";

const mockOn = vi.fn();
const mockOff = vi.fn();
const mockEmit = vi.fn();

vi.mock("socket.io-client", () => ({
  io: vi.fn(() => ({
    on: mockOn,
    off: mockOff,
    emit: mockEmit,
    connected: true,
  })),
}));

vi.mock("@/stores/auth-store", () => ({
  useAuthStore: {
    getState: () => ({ tokens: { access_token: "test-token" } }),
  },
}));

vi.mock("@/stores/workspace-store", () => ({
  useWorkspaceStore: {
    getState: () => ({ currentWorkspace: { id: "ws-123" } }),
    subscribe: vi.fn(() => vi.fn()),
  },
}));

// Mock React hooks for non-component usage
vi.mock("react", () => ({
  useEffect: (fn: () => void) => fn(),
  useRef: (val: unknown) => ({ current: val }),
}));

const mockSuccess = vi.fn();
const mockError = vi.fn();
vi.mock("@/lib/toast", () => ({
  useToast: () => ({ success: mockSuccess, error: mockError, info: vi.fn(), loading: vi.fn(), dismiss: vi.fn() }),
}));

describe("useRealtimeNotifications", { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it("subscribes to crawl:completed, document:status_changed, chatbot:status_changed", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const events = mockOn.mock.calls.map((c: unknown[]) => c[0]);
    expect(events).toContain("crawl:completed");
    expect(events).toContain("document:status_changed");
    expect(events).toContain("chatbot:status_changed");
  });

  it("toasts success on crawl:completed with status completed", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const crawlHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "crawl:completed",
    )![1] as (data: unknown) => void;

    crawlHandler({ status: "completed", pages_queued: 5 });
    expect(mockSuccess).toHaveBeenCalledWith("Crawl completed — 5 pages indexed");
  });

  it("toasts error on crawl:completed with non-completed status", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const crawlHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "crawl:completed",
    )![1] as (data: unknown) => void;

    crawlHandler({ status: "failed", error_message: "timeout" });
    expect(mockError).toHaveBeenCalledWith("Crawl failed: timeout");
  });

  it("toasts error on document:status_changed with failed status", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const docHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "document:status_changed",
    )![1] as (data: unknown) => void;

    docHandler({ status: "failed", title: "page.html", error_message: "parse error" });
    expect(mockError).toHaveBeenCalledWith("Failed to index: page.html — parse error");
  });

  it("toasts success when chatbot becomes ready", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const chatbotHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "chatbot:status_changed",
    )![1] as (data: unknown) => void;

    chatbotHandler({ setup_status: "ready" });
    expect(mockSuccess).toHaveBeenCalledWith("Chatbot is ready for review");
  });

  it("toasts error when chatbot setup fails", async () => {
    const { useRealtimeNotifications } = await import("@/hooks/useRealtimeNotifications");
    useRealtimeNotifications();

    const chatbotHandler = mockOn.mock.calls.find(
      (c: unknown[]) => c[0] === "chatbot:status_changed",
    )![1] as (data: unknown) => void;

    chatbotHandler({ setup_status: "setup_failed" });
    expect(mockError).toHaveBeenCalledWith("Chatbot auto-configuration failed");
  });
});
