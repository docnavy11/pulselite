import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { getLLMSettings } from "@/lib/api-functions";
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

// ── AI config detection logic ────────────────────────────────────────────

describe("AI setup gating", () => {
  it("detects AI is fully configured when key + models present", async () => {
    server.use(
      http.get(`${BASE}/llm-settings`, () =>
        HttpResponse.json({
          openrouter_api_key_set: false,
          openrouter_base_url: null,
          effective_base_url: "https://openrouter.ai/api/v1",
          effective_api_key_set: true,
          allowed_models: ["model-a", "model-b"],
          internal_model: null,
          default_chatbot_model: null,
          env_api_key_set: true,
          env_base_url: "https://openrouter.ai/api/v1",
          env_default_chatbot_model: null,
          env_internal_model: null,
        }),
      ),
    );
    const settings = await getLLMSettings(WS);
    const aiConfigured =
      settings.effective_api_key_set && settings.allowed_models.length > 0;
    expect(aiConfigured).toBe(true);
  });

  it("detects AI not configured when no key", async () => {
    server.use(
      http.get(`${BASE}/llm-settings`, () =>
        HttpResponse.json({
          openrouter_api_key_set: false,
          openrouter_base_url: null,
          effective_base_url: null,
          effective_api_key_set: false,
          allowed_models: [],
          internal_model: null,
          default_chatbot_model: null,
          env_api_key_set: false,
          env_base_url: null,
          env_default_chatbot_model: null,
          env_internal_model: null,
        }),
      ),
    );
    const settings = await getLLMSettings(WS);
    const aiConfigured =
      settings.effective_api_key_set && settings.allowed_models.length > 0;
    expect(aiConfigured).toBe(false);
  });

  it("detects AI not configured when key set but no models selected", async () => {
    server.use(
      http.get(`${BASE}/llm-settings`, () =>
        HttpResponse.json({
          openrouter_api_key_set: false,
          openrouter_base_url: null,
          effective_base_url: "https://openrouter.ai/api/v1",
          effective_api_key_set: true,
          allowed_models: [],
          internal_model: null,
          default_chatbot_model: null,
          env_api_key_set: true,
          env_base_url: "https://openrouter.ai/api/v1",
          env_default_chatbot_model: null,
          env_internal_model: null,
        }),
      ),
    );
    const settings = await getLLMSettings(WS);
    const aiConfigured =
      settings.effective_api_key_set && settings.allowed_models.length > 0;
    expect(aiConfigured).toBe(false);
  });

  it("detects needs setup when key is missing (for ProtectedRoute)", async () => {
    server.use(
      http.get(`${BASE}/llm-settings`, () =>
        HttpResponse.json({
          openrouter_api_key_set: false,
          openrouter_base_url: null,
          effective_base_url: null,
          effective_api_key_set: false,
          allowed_models: [],
          internal_model: null,
          default_chatbot_model: null,
          env_api_key_set: false,
          env_base_url: null,
          env_default_chatbot_model: null,
          env_internal_model: null,
        }),
      ),
    );
    const settings = await getLLMSettings(WS);
    const needsKey = !settings.effective_api_key_set;
    const needsModels = settings.allowed_models.length === 0;
    const needsAISetup = needsKey || needsModels;
    expect(needsAISetup).toBe(true);
    expect(needsKey).toBe(true);
    expect(needsModels).toBe(true);
  });

  it("detects setup complete when workspace key + models configured", async () => {
    server.use(
      http.get(`${BASE}/llm-settings`, () =>
        HttpResponse.json({
          openrouter_api_key_set: true,
          openrouter_base_url: "https://custom.api/v1",
          effective_base_url: "https://custom.api/v1",
          effective_api_key_set: true,
          allowed_models: ["openai/gpt-4o"],
          internal_model: "openai/gpt-4o-mini",
          default_chatbot_model: "openai/gpt-4o",
          env_api_key_set: false,
          env_base_url: null,
          env_default_chatbot_model: null,
          env_internal_model: null,
        }),
      ),
    );
    const settings = await getLLMSettings(WS);
    const needsKey = !settings.effective_api_key_set;
    const needsModels = settings.allowed_models.length === 0;
    const needsAISetup = needsKey || needsModels;
    expect(needsAISetup).toBe(false);
  });
});
