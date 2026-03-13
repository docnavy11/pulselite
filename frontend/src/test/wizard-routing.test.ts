import { describe, it, expect } from "vitest";

// Pure logic: getSetupStep maps setup_status to a wizard step.
function getSetupStep(setupStatus: string | null | undefined): "crawling" | "configuring" | "failed" | "review" | "done" {
  if (!setupStatus || setupStatus === "done") return "done";
  if (setupStatus === "crawling") return "crawling";
  if (setupStatus === "configuring") return "configuring";
  if (setupStatus === "setup_failed") return "failed";
  if (setupStatus === "ready") return "review";
  return "done";
}

describe("getSetupStep", () => {
  it("null → done (redirect to settings)", () => {
    expect(getSetupStep(null)).toBe("done");
  });

  it("undefined → done", () => {
    expect(getSetupStep(undefined)).toBe("done");
  });

  it("'done' → done", () => {
    expect(getSetupStep("done")).toBe("done");
  });

  it("'crawling' → crawling", () => {
    expect(getSetupStep("crawling")).toBe("crawling");
  });

  it("'configuring' → configuring", () => {
    expect(getSetupStep("configuring")).toBe("configuring");
  });

  it("'setup_failed' → failed", () => {
    expect(getSetupStep("setup_failed")).toBe("failed");
  });

  it("'ready' → review", () => {
    expect(getSetupStep("ready")).toBe("review");
  });
});
