// XSS NOTE: Tokens are stored in localStorage for MVP convenience.
// In production, auth tokens should be stored in httpOnly cookies to prevent
// token theft via XSS attacks. localStorage is accessible to any JS running
// on the page, making it vulnerable if an XSS vulnerability exists elsewhere.
import { AuthTokens, User } from "./types";

const TOKENS_KEY = "pulse_tokens";
const USER_KEY = "pulse_user";

export function getTokens(): AuthTokens | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(TOKENS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
}

export function clearTokens(): void {
  localStorage.removeItem(TOKENS_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return getTokens() !== null;
}

export function getCurrentUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setCurrentUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
