import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import {
  getSentimentTrends,
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
