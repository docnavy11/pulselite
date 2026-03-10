"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setTokens } from "@/lib/auth";
import { useAuthStore } from "@/stores/auth-store";
import { Spinner } from "@/components/ui/Spinner";

export default function SSOCompletePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { initialize } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");

    if (!accessToken || !refreshToken) {
      setError("SSO authentication failed — missing tokens.");
      return;
    }

    setTokens({
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: "bearer",
    });

    // Re-initialize auth store so the rest of the app picks up the new tokens
    initialize();

    router.push("/");
  }, [searchParams, router, initialize]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="rounded-lg bg-red-50 p-6 text-center max-w-sm">
          <p className="text-sm font-medium text-red-700">{error}</p>
          <a
            href="/login"
            className="mt-4 inline-block text-sm text-primary-600 hover:text-primary-500"
          >
            Back to sign in
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <Spinner />
      <p className="text-sm text-gray-500">Completing sign-in...</p>
    </div>
  );
}
