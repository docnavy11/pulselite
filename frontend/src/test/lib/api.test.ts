import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { api, ApiError } from "@/lib/api";
import { setTokens, clearTokens } from "@/lib/auth";
import { AuthTokens } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "test-access-token",
  refresh_token: "test-refresh-token",
  token_type: "bearer",
};

const BASE = "http://localhost:8000";

beforeEach(() => {
  clearTokens();
});

// ── Basic GET ──────────────────────────────────────────────────────────────

describe("api.get", () => {
  it("returns parsed JSON on 200", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json({ hello: "world" }),
      ),
    );
    const result = await api.get("/api/v1/test");
    expect(result).toEqual({ hello: "world" });
  });

  it("includes Authorization header when tokens set", async () => {
    setTokens(TOKENS);
    let captured: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/test`, ({ request }) => {
        captured = request.headers.get("authorization");
        return HttpResponse.json({});
      }),
    );
    await api.get("/api/v1/test");
    expect(captured).toBe(`Bearer ${TOKENS.access_token}`);
  });

  it("throws ApiError on 4xx", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );
    await expect(api.get("/api/v1/test")).rejects.toBeInstanceOf(ApiError);
  });

  it("ApiError carries the status code", async () => {
    server.use(
      http.get(`${BASE}/api/v1/test`, () =>
        new HttpResponse(null, { status: 422 }),
      ),
    );
    try {
      await api.get("/api/v1/test");
    } catch (e) {
      expect((e as ApiError).status).toBe(422);
    }
  });
});

// ── DELETE returns undefined on 204 ───────────────────────────────────────

describe("api.delete", () => {
  it("returns undefined for 204 No Content", async () => {
    server.use(
      http.delete(`${BASE}/api/v1/test/1`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    const result = await api.delete("/api/v1/test/1");
    expect(result).toBeUndefined();
  });
});

// ── POST / PUT ────────────────────────────────────────────────────────────

describe("api.post", () => {
  it("sends JSON body", async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/api/v1/test`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await api.post("/api/v1/test", { key: "value" });
    expect(body).toEqual({ key: "value" });
  });
});

// ── 401 → refresh → retry ─────────────────────────────────────────────────

describe("401 token refresh", () => {
  it("retries with new token after successful refresh", async () => {
    setTokens(TOKENS);
    let callCount = 0;

    server.use(
      http.get(`${BASE}/api/v1/protected`, () => {
        callCount++;
        if (callCount === 1) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json({ data: "secret" });
      }),
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        HttpResponse.json({
          access_token: "new-access-token",
          refresh_token: "new-refresh-token",
          token_type: "bearer",
        }),
      ),
    );

    const result = await api.get("/api/v1/protected");
    expect(result).toEqual({ data: "secret" });
    expect(callCount).toBe(2);
  });

  it("throws ApiError 401 when refresh fails", async () => {
    setTokens(TOKENS);
    server.use(
      http.get(`${BASE}/api/v1/protected`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${BASE}/api/v1/auth/refresh`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
    );

    await expect(api.get("/api/v1/protected")).rejects.toMatchObject({
      status: 401,
    });
  });
});
