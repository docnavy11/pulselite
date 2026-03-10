import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/stores/auth-store";
import { setTokens, setCurrentUser } from "@/lib/auth";
import { AuthTokens, User } from "@/lib/types";

const TOKENS: AuthTokens = {
  access_token: "acc",
  refresh_token: "ref",
  token_type: "bearer",
};
const USER: User = { id: "u1", email: "a@b.com", name: "Alice" };

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ user: null, tokens: null, isLoading: true });
});

describe("initialize", () => {
  it("sets isLoading false when no tokens stored", () => {
    useAuthStore.getState().initialize();
    expect(useAuthStore.getState().isLoading).toBe(false);
    expect(useAuthStore.getState().tokens).toBeNull();
  });

  it("loads tokens and user from localStorage", () => {
    setTokens(TOKENS);
    setCurrentUser(USER);
    useAuthStore.getState().initialize();
    expect(useAuthStore.getState().tokens).toEqual(TOKENS);
    expect(useAuthStore.getState().user).toEqual(USER);
  });
});

describe("login", () => {
  it("persists tokens and user in localStorage", () => {
    useAuthStore.getState().login(USER, TOKENS);
    expect(localStorage.getItem("pulse_tokens")).toBe(JSON.stringify(TOKENS));
    expect(localStorage.getItem("pulse_user")).toBe(JSON.stringify(USER));
  });

  it("sets user and tokens in store state", () => {
    useAuthStore.getState().login(USER, TOKENS);
    expect(useAuthStore.getState().user).toEqual(USER);
    expect(useAuthStore.getState().tokens).toEqual(TOKENS);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });
});

describe("logout", () => {
  it("clears store state", () => {
    useAuthStore.getState().login(USER, TOKENS);
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().tokens).toBeNull();
  });

  it("clears localStorage", () => {
    useAuthStore.getState().login(USER, TOKENS);
    useAuthStore.getState().logout();
    expect(localStorage.getItem("pulse_tokens")).toBeNull();
  });
});

describe("setUser", () => {
  it("updates user in state and localStorage", () => {
    const updated: User = { id: "u1", email: "new@b.com", name: "New Name" };
    useAuthStore.getState().setUser(updated);
    expect(useAuthStore.getState().user).toEqual(updated);
    expect(JSON.parse(localStorage.getItem("pulse_user")!)).toEqual(updated);
  });
});
