import { describe, it, expect, beforeEach } from "vitest";
import {
  getTokens,
  setTokens,
  clearTokens,
  isAuthenticated,
  getCurrentUser,
  setCurrentUser,
} from "@/lib/auth";
import { AuthTokens, User } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "acc.tok.en",
  refresh_token: "ref.tok.en",
  token_type: "bearer",
};

const USER: User = { id: "u1", email: "a@b.com", name: "Alice" };

beforeEach(() => {
  localStorage.clear();
});

// ── getTokens ──────────────────────────────────────────────────────────────

describe("getTokens", () => {
  it("returns null when nothing stored", () => {
    expect(getTokens()).toBeNull();
  });

  it("returns parsed tokens after setTokens", () => {
    setTokens(TOKENS);
    expect(getTokens()).toEqual(TOKENS);
  });

  it("returns null for corrupted JSON", () => {
    localStorage.setItem("pulse_tokens", "not-json");
    expect(getTokens()).toBeNull();
  });
});

// ── setTokens / clearTokens ────────────────────────────────────────────────

describe("setTokens", () => {
  it("persists tokens to localStorage", () => {
    setTokens(TOKENS);
    expect(localStorage.getItem("pulse_tokens")).toBe(JSON.stringify(TOKENS));
  });
});

describe("clearTokens", () => {
  it("removes pulse_tokens key", () => {
    setTokens(TOKENS);
    clearTokens();
    expect(localStorage.getItem("pulse_tokens")).toBeNull();
  });

  it("removes pulse_user key", () => {
    setCurrentUser(USER);
    clearTokens();
    expect(localStorage.getItem("pulse_user")).toBeNull();
  });
});

// ── isAuthenticated ────────────────────────────────────────────────────────

describe("isAuthenticated", () => {
  it("returns false when no tokens", () => {
    expect(isAuthenticated()).toBe(false);
  });

  it("returns true when tokens exist", () => {
    setTokens(TOKENS);
    expect(isAuthenticated()).toBe(true);
  });
});

// ── setCurrentUser ────────────────────────────────────────────────────────

describe("setCurrentUser", () => {
  it("persists user to localStorage", () => {
    setCurrentUser(USER);
    expect(localStorage.getItem("pulse_user")).toBe(JSON.stringify(USER));
  });
});

// ── getCurrentUser ────────────────────────────────────────────────────────

describe("getCurrentUser", () => {
  it("returns null when nothing stored", () => {
    expect(getCurrentUser()).toBeNull();
  });

  it("returns parsed user after setCurrentUser", () => {
    setCurrentUser(USER);
    expect(getCurrentUser()).toEqual(USER);
  });

  it("returns null for corrupted JSON", () => {
    localStorage.setItem("pulse_user", "{bad}");
    expect(getCurrentUser()).toBeNull();
  });
});
