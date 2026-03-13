import { describe, it, expect } from "vitest";

// Logic extracted from the component for testability
function isSetupInProgress(setupStatus: string | null | undefined): boolean {
  return ["crawling", "configuring", "ready", "setup_failed"].includes(setupStatus ?? "");
}

function needsActivePoll(setupStatus: string | null | undefined): boolean {
  return ["crawling", "configuring"].includes(setupStatus ?? "");
}

function getSetupBadgeLabel(setupStatus: string | null | undefined): string | null {
  if (setupStatus === "crawling") return "Crawling";
  if (setupStatus === "configuring") return "Configuring";
  if (setupStatus === "ready") return "Review needed";
  if (setupStatus === "setup_failed") return "Setup failed";
  return null;
}

function getProgressText(bot: {
  setup_status?: string | null;
  crawl_progress?: { pages_queued: number; pages_discovered: number } | null;
}): string | null {
  if (bot.setup_status === "crawling" && bot.crawl_progress) {
    const { pages_queued, pages_discovered } = bot.crawl_progress;
    if (pages_discovered > 0) return `${pages_queued} / ${pages_discovered} pages`;
  }
  if (bot.setup_status === "configuring" || bot.setup_status === "ready") {
    return "Almost there…";
  }
  return null;
}

describe("chatbot card setup state", () => {
  it("isSetupInProgress: true for crawling", () => {
    expect(isSetupInProgress("crawling")).toBe(true);
  });

  it("isSetupInProgress: true for configuring", () => {
    expect(isSetupInProgress("configuring")).toBe(true);
  });

  it("isSetupInProgress: true for ready", () => {
    expect(isSetupInProgress("ready")).toBe(true);
  });

  it("isSetupInProgress: true for setup_failed", () => {
    expect(isSetupInProgress("setup_failed")).toBe(true);
  });

  it("isSetupInProgress: false for done", () => {
    expect(isSetupInProgress("done")).toBe(false);
  });

  it("isSetupInProgress: false for null", () => {
    expect(isSetupInProgress(null)).toBe(false);
  });

  it("needsActivePoll: only crawling and configuring", () => {
    expect(needsActivePoll("crawling")).toBe(true);
    expect(needsActivePoll("configuring")).toBe(true);
    expect(needsActivePoll("ready")).toBe(false);
    expect(needsActivePoll("setup_failed")).toBe(false);
    expect(needsActivePoll(null)).toBe(false);
  });

  it("getSetupBadgeLabel: correct labels", () => {
    expect(getSetupBadgeLabel("crawling")).toBe("Crawling");
    expect(getSetupBadgeLabel("configuring")).toBe("Configuring");
    expect(getSetupBadgeLabel("ready")).toBe("Review needed");
    expect(getSetupBadgeLabel("setup_failed")).toBe("Setup failed");
    expect(getSetupBadgeLabel(null)).toBeNull();
  });

  it("getProgressText: shows pages for crawling", () => {
    expect(
      getProgressText({ setup_status: "crawling", crawl_progress: { pages_queued: 5, pages_discovered: 20 } }),
    ).toBe("5 / 20 pages");
  });

  it("getProgressText: 'Almost there…' for configuring", () => {
    expect(getProgressText({ setup_status: "configuring" })).toBe("Almost there…");
  });

  it("getProgressText: null for null status", () => {
    expect(getProgressText({ setup_status: null })).toBeNull();
  });
});
