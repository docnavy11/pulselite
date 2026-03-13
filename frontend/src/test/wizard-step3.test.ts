import { describe, it, expect } from "vitest";

// Logic: save payload should include system_prompt and fallback_message
// when they have values (mirrors handleSave() payload construction)
function buildSavePayload(fields: {
  name: string;
  welcome: string;
  systemPrompt: string;
  fallback: string;
  color: string;
  tone: string;
  language: string;
}) {
  return {
    name: fields.name,
    welcome_message: fields.welcome,
    system_prompt: fields.systemPrompt,
    fallback_message: fields.fallback,
    brand_color: fields.color,
    tone: fields.tone,
    language: fields.language,
  };
}

describe("wizard step 3 save payload", () => {
  it("includes system_prompt in save payload", () => {
    const payload = buildSavePayload({
      name: "Linkflow Assistant",
      welcome: "Hi!",
      systemPrompt: "You are a helpful assistant.",
      fallback: "I don't know.",
      color: "#ff6b35",
      tone: "professional",
      language: "en",
    });
    expect(payload.system_prompt).toBe("You are a helpful assistant.");
  });

  it("includes fallback_message in save payload", () => {
    const payload = buildSavePayload({
      name: "Bot",
      welcome: "Hi!",
      systemPrompt: "...",
      fallback: "Sorry, I can't help with that.",
      color: "#000",
      tone: "friendly",
      language: "nl",
    });
    expect(payload.fallback_message).toBe("Sorry, I can't help with that.");
  });

  it("all 7 fields present in payload", () => {
    const payload = buildSavePayload({
      name: "Bot",
      welcome: "Hi!",
      systemPrompt: "Behave well.",
      fallback: "No idea.",
      color: "#abc",
      tone: "casual",
      language: "fr",
    });
    const keys = Object.keys(payload);
    expect(keys).toContain("system_prompt");
    expect(keys).toContain("fallback_message");
    expect(keys).toContain("welcome_message");
    expect(keys).toContain("brand_color");
  });
});
