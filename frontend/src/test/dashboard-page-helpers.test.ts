import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatDelta,
  resolutionBadgeColor,
  formatRelativeTime,
} from "@/app/(dashboard)/chatbots/[id]/dashboard/page";

// ---------------------------------------------------------------------------
// formatDelta
// ---------------------------------------------------------------------------

describe("formatDelta", () => {
  it("returns 'No change' when diff is essentially zero", () => {
    const result = formatDelta(0.5, 0.5);
    expect(result.text).toBe("No change");
    expect(result.color).toBe("text-gray-400");
  });

  it("returns 'No change' for very small diffs below threshold", () => {
    const result = formatDelta(1.0, 1.0005);
    expect(result.text).toBe("No change");
  });

  it("returns green up arrow for positive absolute diff", () => {
    const result = formatDelta(10, 8);
    expect(result.text).toBe("\u2191 2.0");
    expect(result.color).toBe("text-green-500");
  });

  it("returns red down arrow for negative absolute diff", () => {
    const result = formatDelta(5, 8);
    expect(result.text).toBe("\u2193 3.0");
    expect(result.color).toBe("text-red-500");
  });

  it("formats percent type with pp suffix", () => {
    // current=0.85, previous=0.80 => diff=0.05 => 5.0pp
    const result = formatDelta(0.85, 0.80, "percent");
    expect(result.text).toBe("\u2191 5.0pp");
    expect(result.color).toBe("text-green-500");
  });

  it("formats negative percent type with pp suffix", () => {
    const result = formatDelta(0.70, 0.80, "percent");
    expect(result.text).toBe("\u2193 10.0pp");
    expect(result.color).toBe("text-red-500");
  });
});

// ---------------------------------------------------------------------------
// resolutionBadgeColor
// ---------------------------------------------------------------------------

describe("resolutionBadgeColor", () => {
  it("returns green for rate >= 0.7", () => {
    expect(resolutionBadgeColor(0.7)).toBe("bg-green-100 text-green-700");
    expect(resolutionBadgeColor(0.95)).toBe("bg-green-100 text-green-700");
  });

  it("returns yellow for rate >= 0.4 and < 0.7", () => {
    expect(resolutionBadgeColor(0.4)).toBe("bg-yellow-100 text-yellow-700");
    expect(resolutionBadgeColor(0.69)).toBe("bg-yellow-100 text-yellow-700");
  });

  it("returns red for rate < 0.4", () => {
    expect(resolutionBadgeColor(0.39)).toBe("bg-red-100 text-red-700");
    expect(resolutionBadgeColor(0)).toBe("bg-red-100 text-red-700");
  });
});

// ---------------------------------------------------------------------------
// formatRelativeTime
// ---------------------------------------------------------------------------

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-13T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "just now" for times less than 1 minute ago', () => {
    expect(formatRelativeTime("2026-03-13T12:00:00Z")).toBe("just now");
    expect(formatRelativeTime("2026-03-13T11:59:45Z")).toBe("just now");
  });

  it("returns minutes ago for times < 60 minutes", () => {
    expect(formatRelativeTime("2026-03-13T11:30:00Z")).toBe("30m ago");
    expect(formatRelativeTime("2026-03-13T11:55:00Z")).toBe("5m ago");
  });

  it("returns hours ago for times < 24 hours", () => {
    expect(formatRelativeTime("2026-03-13T06:00:00Z")).toBe("6h ago");
    expect(formatRelativeTime("2026-03-13T00:00:00Z")).toBe("12h ago");
  });

  it("returns days ago for times >= 24 hours", () => {
    expect(formatRelativeTime("2026-03-12T12:00:00Z")).toBe("1d ago");
    expect(formatRelativeTime("2026-03-06T12:00:00Z")).toBe("7d ago");
  });
});
