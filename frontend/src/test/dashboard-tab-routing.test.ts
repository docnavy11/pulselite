import { describe, it, expect } from "vitest";

// Extracted TABS definition mirroring layout.tsx
const TABS = [
  { label: "Dashboard",  segment: null },
  { label: "Knowledge",  segment: "sources" },
  { label: "Configure",  segment: "settings" },
  { label: "Actions",    segment: "actions" },
  { label: "Appearance", segment: "customize" },
  { label: "Test",       segment: "chat" },
  { label: "Publish",    segment: "deploy" },
] as const;

// Extracted routing logic mirroring layout.tsx
function tabHref(chatbotId: string, segment: string | null): string {
  return segment ? `/chatbots/${chatbotId}/${segment}` : `/chatbots/${chatbotId}`;
}

function isActive(pathname: string, chatbotId: string, segment: string | null): boolean {
  if (segment === null) {
    return pathname === `/chatbots/${chatbotId}`;
  }
  return pathname.startsWith(`/chatbots/${chatbotId}/${segment}`);
}

describe("chatbot dashboard tab routing", () => {
  const botId = "abc-123";

  it("Dashboard tab is first with null segment", () => {
    expect(TABS[0].label).toBe("Dashboard");
    expect(TABS[0].segment).toBeNull();
  });

  it("Knowledge tab uses 'sources' segment", () => {
    const knowledgeTab = TABS.find((t) => t.label === "Knowledge");
    expect(knowledgeTab?.segment).toBe("sources");
  });

  it("has 7 tabs total", () => {
    expect(TABS).toHaveLength(7);
  });

  it("tabHref: dashboard tab points to /chatbots/:id", () => {
    expect(tabHref(botId, null)).toBe(`/chatbots/${botId}`);
  });

  it("tabHref: sources tab points to /chatbots/:id/sources", () => {
    expect(tabHref(botId, "sources")).toBe(`/chatbots/${botId}/sources`);
  });

  it("isActive: dashboard tab active for exact path", () => {
    expect(isActive(`/chatbots/${botId}`, botId, null)).toBe(true);
  });

  it("isActive: dashboard tab not active for sub-path", () => {
    expect(isActive(`/chatbots/${botId}/sources`, botId, null)).toBe(false);
  });

  it("isActive: sources tab active for /chatbots/:id/sources", () => {
    expect(isActive(`/chatbots/${botId}/sources`, botId, "sources")).toBe(true);
  });

  it("isActive: settings tab active for /chatbots/:id/settings", () => {
    expect(isActive(`/chatbots/${botId}/settings`, botId, "settings")).toBe(true);
  });

  it("all expected tab labels are present", () => {
    const labels = TABS.map((t) => t.label);
    expect(labels).toEqual([
      "Dashboard",
      "Knowledge",
      "Configure",
      "Actions",
      "Appearance",
      "Test",
      "Publish",
    ]);
  });
});
