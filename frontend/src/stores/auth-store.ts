import { create } from "zustand";
import { User, AuthTokens } from "@/lib/types";
import {
  getTokens,
  setTokens,
  clearTokens,
  getCurrentUser,
  setCurrentUser,
} from "@/lib/auth";

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  initialize: () => void;
  login: (user: User, tokens: AuthTokens) => void;
  logout: () => void;
  setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  tokens: null,
  isLoading: true,

  initialize: () => {
    const tokens = getTokens();
    const user = getCurrentUser();
    set({ tokens, user, isLoading: false });
  },

  login: (user: User, tokens: AuthTokens) => {
    setTokens(tokens);
    setCurrentUser(user);
    set({ user, tokens, isLoading: false });
  },

  logout: () => {
    clearTokens();
    set({ user: null, tokens: null });
  },

  setUser: (user: User) => {
    setCurrentUser(user);
    set({ user });
  },
}));
