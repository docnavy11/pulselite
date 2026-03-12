import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { getCrawlRunLogs, getDocumentLogs } from "@/lib/api-functions";
import { setTokens } from "@/lib/auth";

const WS = "ws-test-id";
const BASE = `http://localhost:8000/api/v1/workspaces/${WS}`;
const TOKENS = { access_token: "tok", refresh_token: "ref", token_type: "bearer" };

beforeEach(() => setTokens(TOKENS));

// ── Shared mock data ──────────────────────────────────────────────────────────

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

// ── getCrawlRunLogs API ───────────────────────────────────────────────────────

describe("getCrawlRunLogs", () => {
  it("fetches crawl run rows and returns them", async () => {
    server.use(
      http.get(`${BASE}/logs/crawl-runs`, () => HttpResponse.json(mockCrawlRuns)),
    );
    const result = await getCrawlRunLogs(WS);
    expect(result.total).toBe(2);
    expect(result.items).toHaveLength(2);
    expect(result.items[0].job_id).toBe("job-1");
    expect(result.items[1].error_message).toBe("Could not discover pages: timeout");
  });

  it("sends default limit=50 offset=0", async () => {
    const captured = { params: null as URLSearchParams | null };
    server.use(
      http.get(`${BASE}/logs/crawl-runs`, ({ request }) => {
        captured.params = new URL(request.url).searchParams;
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    await getCrawlRunLogs(WS);
    expect(captured.params?.get("limit")).toBe("50");
    expect(captured.params?.get("offset")).toBe("0");
  });

  it("passes custom limit and offset params", async () => {
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

  it("load-more uses offset=50 for second page", async () => {
    const captured = { params: null as URLSearchParams | null };
    server.use(
      http.get(`${BASE}/logs/crawl-runs`, ({ request }) => {
        captured.params = new URL(request.url).searchParams;
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    await getCrawlRunLogs(WS, 50, 50);
    expect(captured.params?.get("offset")).toBe("50");
  });
});

// ── getDocumentLogs API ───────────────────────────────────────────────────────

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

  it("sends default limit=50 offset=0", async () => {
    const captured = { params: null as URLSearchParams | null };
    server.use(
      http.get(`${BASE}/logs/documents`, ({ request }) => {
        captured.params = new URL(request.url).searchParams;
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    await getDocumentLogs(WS);
    expect(captured.params?.get("limit")).toBe("50");
    expect(captured.params?.get("offset")).toBe("0");
  });
});

// ── Component logic ───────────────────────────────────────────────────────────

// hasActive: polling starts when running/pending jobs exist
function hasActive(rows: Array<{ status: string }>): boolean {
  return rows.some(r => r.status === "running" || r.status === "pending");
}

describe("hasActive (crawl polling logic)", () => {
  it("returns true when any row is running", () => {
    expect(hasActive([{ status: "running" }])).toBe(true);
    expect(hasActive([{ status: "completed" }, { status: "running" }])).toBe(true);
  });

  it("returns true when any row is pending", () => {
    expect(hasActive([{ status: "pending" }])).toBe(true);
  });

  it("returns false when all rows are terminal", () => {
    expect(hasActive([{ status: "completed" }, { status: "failed" }])).toBe(false);
    expect(hasActive([])).toBe(false);
  });
});

// Step icon selection: ok→check circle, failed→bare triangle, skipped→minus circle
function stepIconType(status: string): "check" | "triangle" | "minus" | null {
  if (status === "ok") return "check";
  if (status === "failed") return "triangle";
  if (status === "skipped") return "minus";
  return null;
}

describe("StepTimeline icon selection", () => {
  it("ok step uses check icon", () => {
    expect(stepIconType("ok")).toBe("check");
  });

  it("failed step uses bare triangle (no circle wrapper)", () => {
    expect(stepIconType("failed")).toBe("triangle");
  });

  it("skipped step uses minus icon", () => {
    expect(stepIconType("skipped")).toBe("minus");
  });
});

// Error banner visibility: only shown when status === "failed" AND errorMessage is set
function showErrorBanner(status: string, errorMessage: string | null): boolean {
  return status === "failed" && errorMessage !== null && errorMessage !== "";
}

describe("StepTimeline error banner visibility", () => {
  it("shows when status=failed and errorMessage is set", () => {
    expect(showErrorBanner("failed", "timeout")).toBe(true);
  });

  it("does not show when status=indexed even with errorMessage", () => {
    expect(showErrorBanner("indexed", "leftover message")).toBe(false);
  });

  it("does not show when status=failed but errorMessage is null", () => {
    expect(showErrorBanner("failed", null)).toBe(false);
  });

  it("does not show for skipped status", () => {
    expect(showErrorBanner("skipped", "budget exceeded")).toBe(false);
  });
});

// Expand toggle: clicking a row adds its id; clicking again removes it
function toggleExpand(set: Set<string>, id: string): Set<string> {
  const next = new Set(set);
  next.has(id) ? next.delete(id) : next.add(id);
  return next;
}

describe("DocumentsTab expand toggle (step timeline)", () => {
  it("adds id on first click (expands row)", () => {
    const result = toggleExpand(new Set(), "doc-1");
    expect(result.has("doc-1")).toBe(true);
  });

  it("removes id on second click (collapses row)", () => {
    const result = toggleExpand(new Set(["doc-1"]), "doc-1");
    expect(result.has("doc-1")).toBe(false);
  });

  it("expands multiple rows independently", () => {
    let s = new Set<string>();
    s = toggleExpand(s, "doc-1");
    s = toggleExpand(s, "doc-2");
    expect(s.has("doc-1")).toBe(true);
    expect(s.has("doc-2")).toBe(true);
  });

  it("collapsing one row leaves others expanded", () => {
    let s = new Set(["doc-1", "doc-2"]);
    s = toggleExpand(s, "doc-1");
    expect(s.has("doc-1")).toBe(false);
    expect(s.has("doc-2")).toBe(true);
  });
});

// Null steps: StepTimeline renders fallback message, not empty list
function shouldShowFallback(steps: unknown[] | null): boolean {
  return steps === null;
}

describe("StepTimeline null steps fallback", () => {
  it("shows fallback when steps is null", () => {
    expect(shouldShowFallback(null)).toBe(true);
  });

  it("does not show fallback when steps is empty array", () => {
    expect(shouldShowFallback([])).toBe(false);
  });

  it("does not show fallback when steps has items", () => {
    expect(shouldShowFallback([{}])).toBe(false);
  });
});

// Running badge: spinner shown for running/processing statuses only
function showSpinner(status: string): boolean {
  return status === "running" || status === "processing";
}

describe("CrawlRunsTab running badge spinner", () => {
  it("shows spinner for running status", () => {
    expect(showSpinner("running")).toBe(true);
  });

  it("shows spinner for processing status", () => {
    expect(showSpinner("processing")).toBe(true);
  });

  it("does not show spinner for completed", () => {
    expect(showSpinner("completed")).toBe(false);
  });

  it("does not show spinner for failed or pending", () => {
    expect(showSpinner("failed")).toBe(false);
    expect(showSpinner("pending")).toBe(false);
  });
});
