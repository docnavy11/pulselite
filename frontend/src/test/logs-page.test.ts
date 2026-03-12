import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { getCrawlRunLogs, getDocumentLogs } from "@/lib/api-functions";
import { setTokens } from "@/lib/auth";

const WS = "ws-test-id";
const BASE = `http://localhost:8000/api/v1/workspaces/${WS}`;
const TOKENS = { access_token: "tok", refresh_token: "ref", token_type: "bearer" };

beforeEach(() => setTokens(TOKENS));

const mockCrawlRuns = {
  total: 2,
  items: [
    {
      job_id: "job-1", chatbot_id: "bot-1", chatbot_name: "My Bot",
      root_url: "https://example.com", status: "completed", phase: null,
      pages_discovered: 10, pages_queued: 10, pages_failed: 0, docs_indexed: 10,
      error_message: null, created_at: new Date().toISOString(),
      started_at: new Date().toISOString(), completed_at: new Date().toISOString(),
    },
    {
      job_id: "job-2", chatbot_id: null, chatbot_name: null,
      root_url: "https://other.com", status: "failed", phase: null,
      pages_discovered: 5, pages_queued: 3, pages_failed: 2, docs_indexed: 0,
      error_message: "Could not discover pages: timeout",
      created_at: new Date().toISOString(), started_at: null, completed_at: null,
    },
  ],
};

const mockDocLogs = {
  total: 1,
  items: [
    {
      id: "doc-1", title: "Home Page", source_url: "https://example.com",
      source_type: "url", status: "indexed", chunk_count: 5,
      last_indexed_at: new Date().toISOString(),
      error_message: null,
      ingestion_steps: [
        { step: "extract", status: "ok", started_at: new Date().toISOString(),
          duration_ms: 342, detail: "5000 chars extracted", error: null },
        { step: "chunk", status: "ok", started_at: new Date().toISOString(),
          duration_ms: 12, detail: "5 chunks produced", error: null },
      ],
      knowledge_base_id: "kb-1", knowledge_base_name: "Main KB",
      chatbot_id: "bot-1", chatbot_name: "My Bot",
    },
  ],
};

describe("getCrawlRunLogs", () => {
  it("fetches crawl run logs with correct URL", async () => {
    server.use(
      http.get(`${BASE}/logs/crawl-runs`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("50");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json(mockCrawlRuns);
      }),
    );
    const result = await getCrawlRunLogs(WS);
    expect(result.total).toBe(2);
    expect(result.items).toHaveLength(2);
    expect(result.items[0].job_id).toBe("job-1");
    expect(result.items[1].error_message).toBe("Could not discover pages: timeout");
  });

  it("passes limit and offset params", async () => {
    const captured = { params: null as URLSearchParams | null };
    server.use(
      http.get(`${BASE}/logs/crawl-runs`, ({ request }) => {
        captured.params = new URL(request.url).searchParams;
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    await getCrawlRunLogs(WS, 10, 50);
    expect(captured.params?.get("limit")).toBe("10");
    expect(captured.params?.get("offset")).toBe("50");
  });
});

describe("getDocumentLogs", () => {
  it("returns document log items with ingestion_steps", async () => {
    server.use(
      http.get(`${BASE}/logs/documents`, () => HttpResponse.json(mockDocLogs)),
    );
    const result = await getDocumentLogs(WS);
    expect(result.total).toBe(1);
    expect(result.items[0].ingestion_steps).toHaveLength(2);
    expect(result.items[0].ingestion_steps![0].step).toBe("extract");
  });

  it("handles null ingestion_steps", async () => {
    server.use(
      http.get(`${BASE}/logs/documents`, () =>
        HttpResponse.json({
          total: 1,
          items: [{ ...mockDocLogs.items[0], ingestion_steps: null }],
        }),
      ),
    );
    const result = await getDocumentLogs(WS);
    expect(result.items[0].ingestion_steps).toBeNull();
  });
});
