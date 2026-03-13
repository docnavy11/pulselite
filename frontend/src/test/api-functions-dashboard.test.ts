import { describe, it, expect } from "vitest";

// Test the URL-building logic extracted from api-functions.ts

function buildSentimentTrendsUrl(workspaceId: string, range: string, chatbotId?: string): string {
  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
  const params = new URLSearchParams({ days: String(days) });
  if (chatbotId) params.set("chatbot_id", chatbotId);
  return `/api/v1/workspaces/${workspaceId}/sentiment-trends?${params}`;
}

function buildGapClustersUrl(
  workspaceId: string,
  filters?: { status?: string; chatbot_id?: string },
): string {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.chatbot_id) params.set("chatbot_id", filters.chatbot_id);
  const qs = params.toString();
  return `/api/v1/workspaces/${workspaceId}/gap-clusters${qs ? `?${qs}` : ""}`;
}

function buildConversationsUrl(
  workspaceId: string,
  filters?: { status?: string; chatbot_id?: string; date_from?: string; date_to?: string; limit?: number },
): string {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.chatbot_id) params.set("chatbot_id", filters.chatbot_id);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.limit) params.set("limit", String(filters.limit));
  const qs = params.toString();
  return `/api/v1/workspaces/${workspaceId}/conversations${qs ? `?${qs}` : ""}`;
}

describe("sentiment trends URL building", () => {
  const ws = "ws-1";

  it("builds URL without chatbotId", () => {
    const url = buildSentimentTrendsUrl(ws, "30d");
    expect(url).toBe(`/api/v1/workspaces/${ws}/sentiment-trends?days=30`);
  });

  it("builds URL with chatbotId", () => {
    const url = buildSentimentTrendsUrl(ws, "30d", "bot-1");
    expect(url).toContain("days=30");
    expect(url).toContain("chatbot_id=bot-1");
  });

  it("maps 7d range to 7 days", () => {
    const url = buildSentimentTrendsUrl(ws, "7d");
    expect(url).toContain("days=7");
  });

  it("maps 90d range to 90 days", () => {
    const url = buildSentimentTrendsUrl(ws, "90d");
    expect(url).toContain("days=90");
  });

  it("defaults unknown range to 30 days", () => {
    const url = buildSentimentTrendsUrl(ws, "unknown");
    expect(url).toContain("days=30");
  });
});

describe("gap clusters URL building", () => {
  const ws = "ws-1";

  it("builds URL without filters", () => {
    expect(buildGapClustersUrl(ws)).toBe(`/api/v1/workspaces/${ws}/gap-clusters`);
  });

  it("builds URL with status filter", () => {
    expect(buildGapClustersUrl(ws, { status: "open" })).toContain("status=open");
  });

  it("builds URL with chatbot_id filter", () => {
    expect(buildGapClustersUrl(ws, { chatbot_id: "bot-1" })).toContain("chatbot_id=bot-1");
  });

  it("builds URL with both filters", () => {
    const url = buildGapClustersUrl(ws, { status: "open", chatbot_id: "bot-1" });
    expect(url).toContain("status=open");
    expect(url).toContain("chatbot_id=bot-1");
  });
});

describe("conversations URL building", () => {
  const ws = "ws-1";

  it("builds URL without filters", () => {
    expect(buildConversationsUrl(ws)).toBe(`/api/v1/workspaces/${ws}/conversations`);
  });

  it("builds URL with limit filter", () => {
    expect(buildConversationsUrl(ws, { limit: 10 })).toContain("limit=10");
  });

  it("builds URL with chatbot_id and limit", () => {
    const url = buildConversationsUrl(ws, { chatbot_id: "bot-1", limit: 5 });
    expect(url).toContain("chatbot_id=bot-1");
    expect(url).toContain("limit=5");
  });

  it("does not include limit when not specified", () => {
    const url = buildConversationsUrl(ws, { status: "active" });
    expect(url).not.toContain("limit");
  });
});
