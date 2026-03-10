"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";
import { AuthResponse } from "@/lib/types";

export function useAuth() {
  const router = useRouter();
  const { user, tokens, isLoading, initialize, login: storeLogin, logout: storeLogout } = useAuthStore();

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await api.post<AuthResponse>("/api/v1/auth/login", {
        email,
        password,
      });
      storeLogin(data.user, data.tokens);
      router.push("/");
    },
    [storeLogin, router],
  );

  const register = useCallback(
    async (name: string, email: string, password: string, workspaceName?: string) => {
      const data = await api.post<AuthResponse>("/api/v1/auth/register", {
        name,
        email,
        password,
        workspace_name: workspaceName || `${name}'s Workspace`,
      });
      storeLogin(data.user, data.tokens);
      router.push("/");
    },
    [storeLogin, router],
  );

  const logout = useCallback(() => {
    storeLogout();
    router.push("/login");
  }, [storeLogout, router]);

  return {
    user,
    tokens,
    isLoading,
    isAuthenticated: !!tokens,
    initialize,
    login,
    register,
    logout,
  };
}
