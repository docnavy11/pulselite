import { create } from "zustand";
import { User, AuthTokens } from "@/lib/types";
import {
  getTokens,
  setTokens,
  clearTokens,
  getCurrentUser,
  setCurrentUser,
} from "@/lib/auth";
import { disconnectSocket } from "@/lib/socket";

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
    disconnectSocket();
    set({ user: null, tokens: null });
    // Reset other stores asynchronously to avoid circular import issues
    import("@/stores/workspace-store").then((m) => m.useWorkspaceStore.getState().reset());
    import("@/stores/chatbot-store").then((m) => m.useChatbotStore.getState().reset());
  },

  setUser: (user: User) => {
    setCurrentUser(user);
    set({ user });
  },
}));
