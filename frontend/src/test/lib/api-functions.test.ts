import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import {
  getSentimentTrends,
  getExceptions,
  getExceptionDetail,
  getCreditsBalance,
  getConversations,
} from "@/lib/api-functions";
import { setTokens } from "@/lib/auth";

const WS = "ws-test-id";
const BASE = `http://localhost:8000/api/v1/workspaces/${WS}`;
const TOKENS = {
  access_token: "tok",
  refresh_token: "ref",
  token_type: "bearer",
};

beforeEach(() => {
  setTokens(TOKENS);
});

// ── getCreditsBalance ──────────────────────────────────────────────────────

describe("getCreditsBalance", () => {
  it("maps used_this_month → usage_this_month", async () => {
    server.use(
      http.get(`${BASE}/credits/balance`, () =>
        HttpResponse.json({ balance: 500, used_this_month: 120 }),
      ),
    );
    const result = await getCreditsBalance(WS);
    expect(result.balance).toBe(500);
    expect(result.usage_this_month).toBe(120);
    expect(result.usage_history).toEqual([]);
  });

  it("defaults usage_this_month to 0 when missing", async () => {
    server.use(
      http.get(`${BASE}/credits/balance`, () =>
        HttpResponse.json({ balance: 100, used_this_month: undefined }),
      ),
    );
    const result = await getCreditsBalance(WS);
    expect(result.usage_this_month).toBe(0);
  });
});

// ── getConversations URL params ────────────────────────────────────────────

describe("getConversations", () => {
  it("calls /conversations with no params when no filters", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS);
    expect(url).not.toContain("status=");
    expect(url).not.toContain("chatbot_id=");
  });

  it("appends status filter to URL", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, { status: "open" });
    expect(url).toContain("status=open");
  });

  it("appends chatbot_id filter to URL", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, { chatbot_id: "bot-1" });
    expect(url).toContain("chatbot_id=bot-1");
  });

  it("appends date_from and date_to filters", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/conversations`, ({ request }) => {
        url = request.url;
        return HttpResponse.json([]);
      }),
    );
    await getConversations(WS, {
      date_from: "2026-01-01",
      date_to: "2026-01-31",
    });
    expect(url).toContain("date_from=2026-01-01");
    expect(url).toContain("date_to=2026-01-31");
  });
});

// ── getExceptions ──────────────────────────────────────────────────────────

describe("getExceptions", () => {
  const backendItem = {
    id: "conv-1",
    workspace_id: WS,
    chatbot_id: "bot-1",
    chatbot_name: "Support Bot",
    contact_id: "c-1",
    contact_name: "Alice",
    contact_email: "alice@example.com",
    escalation_reason: "low_confidence",
    confidence_avg: 0.42,
    status: "open",
    last_message_preview: "Hello",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T01:00:00Z",
  };

  it("maps items array to Exception[]", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const result = await getExceptions(WS);
    expect(result).toHaveLength(1);
  });

  it("maps conversation fields correctly", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.conversation.id).toBe("conv-1");
    expect(exc.conversation.chatbot_id).toBe("bot-1");
    expect(exc.conversation.status).toBe("open");
  });

  it("maps contact when name/email present", async () => {
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [backendItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.contact).toBeDefined();
    expect(exc.contact!.name).toBe("Alice");
    expect(exc.contact!.email).toBe("alice@example.com");
  });

  it("sets contact to undefined when no name or email", async () => {
    const anonymousItem = {
      ...backendItem,
      contact_name: undefined,
      contact_email: undefined,
    };
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [anonymousItem], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.contact).toBeUndefined();
  });

  it("defaults escalation_reason to empty string when missing", async () => {
    const noReason = { ...backendItem, escalation_reason: undefined };
    server.use(
      http.get(`${BASE}/exceptions`, () =>
        HttpResponse.json({ items: [noReason], total: 1 }),
      ),
    );
    const [exc] = await getExceptions(WS);
    expect(exc.escalation_reason).toBe("");
  });
});

// ── getExceptionDetail ─────────────────────────────────────────────────────

describe("getExceptionDetail", () => {
  const backendDetail = {
    conversation: {
      id: "conv-2",
      workspace_id: WS,
      chatbot_id: "bot-1",
      chatbot_name: "Bot",
      escalation_reason: "human_requested",
      confidence_avg: 0.3,
      status: "open",
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T01:00:00Z",
    },
    messages: [],
    contact_context: {
      id: "c-2",
      name: "Bob",
      email: "bob@example.com",
      lead_score: 55,
      lead_tier: "hot",
    },
    suggested_action: "offer_demo",
  };

  it("maps contact_context to contact field", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.contact).toBeDefined();
    expect(exc.contact!.id).toBe("c-2");
    expect(exc.contact!.name).toBe("Bob");
    expect(exc.contact!.lead_score).toBe(55);
    expect(exc.contact!.lead_tier).toBe("hot");
  });

  it("maps escalation_reason from conversation", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.escalation_reason).toBe("human_requested");
  });

  it("passes suggested_action through", async () => {
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(backendDetail),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.suggested_action).toBe("offer_demo");
  });

  it("sets contact to undefined when no contact_context", async () => {
    const noContact = { ...backendDetail, contact_context: undefined };
    server.use(
      http.get(`${BASE}/exceptions/conv-2`, () =>
        HttpResponse.json(noContact),
      ),
    );
    const exc = await getExceptionDetail(WS, "conv-2");
    expect(exc.contact).toBeUndefined();
  });
});

// ── getSentimentTrends ─────────────────────────────────────────────────────

describe("getSentimentTrends", () => {
  it("computes avg_sentiment correctly", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.6, count: 5 },
            { date: "2026-01-02", avg_sentiment: 0.4, count: 3 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    // avg of 0.6 + 0.4 = 1.0 / 2 = 0.5
    expect(result.avg_sentiment).toBe(0.5);
  });

  it("computes positive_pct (score >= 0.3)", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.8, count: 1 },
            { date: "2026-01-02", avg_sentiment: 0.5, count: 1 },
            { date: "2026-01-03", avg_sentiment: -0.5, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "30d");
    // 2 of 3 scores are >= 0.3 (0.8 and 0.5), so positive = 2/3 * 100
    expect(result.positive_pct).toBeCloseTo(66.67, 1);
  });

  it("computes negative_pct (score <= -0.3)", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.5, count: 1 },
            { date: "2026-01-02", avg_sentiment: -0.5, count: 1 },
            { date: "2026-01-03", avg_sentiment: -0.8, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "30d");
    // 2 out of 3 are <= -0.3
    expect(result.negative_pct).toBeCloseTo(66.67, 1);
  });

  it("computes trend as last - first score", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: 0.2, count: 1 },
            { date: "2026-01-02", avg_sentiment: 0.7, count: 1 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    // 0.7 - 0.2 = 0.5
    expect(result.trend).toBeCloseTo(0.5, 3);
  });

  it("filters out null avg_sentiment data points", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({
          data: [
            { date: "2026-01-01", avg_sentiment: null, count: 0 },
            { date: "2026-01-02", avg_sentiment: 0.6, count: 2 },
          ],
        }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    expect(result.data_points).toHaveLength(1);
    expect(result.avg_sentiment).toBe(0.6);
  });

  it("returns zeros for empty data", async () => {
    server.use(
      http.get(`${BASE}/sentiment-trends`, () =>
        HttpResponse.json({ data: [] }),
      ),
    );
    const result = await getSentimentTrends(WS, "7d");
    expect(result.avg_sentiment).toBe(0);
    expect(result.positive_pct).toBe(0);
    expect(result.negative_pct).toBe(0);
    expect(result.trend).toBe(0);
  });

  it("passes correct days param for range strings", async () => {
    let url = "";
    server.use(
      http.get(`${BASE}/sentiment-trends`, ({ request }) => {
        url = request.url;
        return HttpResponse.json({ data: [] });
      }),
    );
    await getSentimentTrends(WS, "90d");
    expect(url).toContain("days=90");
  });
});
