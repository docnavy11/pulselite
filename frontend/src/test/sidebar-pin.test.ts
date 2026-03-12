import { describe, it, expect } from "vitest";

// Pure logic: the condition used in the pathname useEffect
function shouldClose(pinned: boolean): boolean {
  return !pinned;
}

describe("sidebar pin close-on-navigate logic", () => {
  it("closes drawer when not pinned", () => {
    expect(shouldClose(false)).toBe(true);
  });

  it("does NOT close drawer when pinned", () => {
    expect(shouldClose(true)).toBe(false);
  });
});
