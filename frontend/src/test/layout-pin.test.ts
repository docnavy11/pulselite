import { describe, it, expect, beforeEach } from "vitest";

// Pure logic: the localStorage init expression used in useState initializer
function readSidebarPinned(): boolean {
  const stored = localStorage.getItem("sidebar-pinned");
  return stored === null ? true : stored === "true";
}

describe("sidebarPinned localStorage logic", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to true when localStorage is empty", () => {
    expect(readSidebarPinned()).toBe(true);
  });

  it("reads false from localStorage", () => {
    localStorage.setItem("sidebar-pinned", "false");
    expect(readSidebarPinned()).toBe(false);
  });

  it("reads true from localStorage", () => {
    localStorage.setItem("sidebar-pinned", "true");
    expect(readSidebarPinned()).toBe(true);
  });

  it("writes the string representation", () => {
    localStorage.setItem("sidebar-pinned", String(false));
    expect(localStorage.getItem("sidebar-pinned")).toBe("false");
    localStorage.setItem("sidebar-pinned", String(true));
    expect(localStorage.getItem("sidebar-pinned")).toBe("true");
  });
});
