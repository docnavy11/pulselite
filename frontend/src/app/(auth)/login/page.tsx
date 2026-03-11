import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface SSOCheckResponse {
  has_sso: boolean;
  provider_name: string | null;
  workspace_id: string | null;
}

interface AuthResponse {
  user: { id: string; email: string; name: string; display_name?: string; avatar_url?: string };
  tokens: { access_token: string; refresh_token: string; token_type: string };
}

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export default function LoginPage() {
  const navigate = useNavigate();
  const storeLogin = useAuthStore((s) => s.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  // 2FA state
  const [requires2fa, setRequires2fa] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [totpError, setTotpError] = useState("");
  const [totpLoading, setTotpLoading] = useState(false);

  // SSO state
  const [ssoEmail, setSsoEmail] = useState("");
  const [ssoLoading, setSsoLoading] = useState(false);
  const [ssoError, setSsoError] = useState("");

  async function attemptLogin(totpCodeValue?: string) {
    const body: Record<string, string> = { email, password };
    if (totpCodeValue) body.totp_code = totpCodeValue;

    // Use raw fetch so we can inspect the 202 status before ApiClient throws
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (response.status === 202) {
      const data = await response.json();
      if (data.requires_2fa) {
        setRequires2fa(true);
        return;
      }
    }

    if (!response.ok) {
      const text = await response.text();
      let detail = "Invalid email or password";
      try {
        const parsed = JSON.parse(text);
        if (parsed.detail) detail = parsed.detail;
      } catch {
        // ignore parse error
      }
      throw new Error(detail);
    }

    const data: AuthResponse = await response.json();
    storeLogin(data.user, data.tokens);
    navigate("/");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});
    setApiError("");

    const result = loginSchema.safeParse({ email, password });
    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      result.error.issues.forEach((err) => {
        if (err.path[0]) fieldErrors[err.path[0] as string] = err.message;
      });
      setErrors(fieldErrors);
      return;
    }

    setLoading(true);
    try {
      await attemptLogin();
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Invalid email or password");
    } finally {
      setLoading(false);
    }
  }

  async function handleTotpVerify(e: React.FormEvent) {
    e.preventDefault();
    setTotpError("");
    if (!totpCode.trim()) {
      setTotpError("Please enter your 6-digit code");
      return;
    }
    setTotpLoading(true);
    try {
      await attemptLogin(totpCode.trim());
    } catch (err) {
      setTotpError(err instanceof Error ? err.message : "Invalid 2FA code");
    } finally {
      setTotpLoading(false);
    }
  }

  async function handleSSOContinue(e: React.FormEvent) {
    e.preventDefault();
    if (!ssoEmail.trim()) return;
    setSsoLoading(true);
    setSsoError("");
    try {
      const result = await api.get<SSOCheckResponse>(
        `/api/v1/auth/sso/check?email=${encodeURIComponent(ssoEmail)}`
      );
      if (result.has_sso && result.workspace_id) {
        window.location.href = `${API_BASE}/api/v1/auth/sso/authorize?workspace_id=${result.workspace_id}`;
      } else {
        setSsoError(
          "No SSO configured for this domain. Please sign in with email/password."
        );
      }
    } catch {
      setSsoError("Failed to check SSO. Please try again.");
    } finally {
      setSsoLoading(false);
    }
  }

  // 2FA verification step
  if (requires2fa) {
    return (
      <Card>
        <CardContent className="pt-8 pb-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-500 to-primary-400 bg-clip-text text-transparent">
              Pulse
            </h1>
            <p className="text-gray-500 mt-2 text-sm">Two-factor authentication</p>
          </div>

          <p className="text-sm text-gray-600 mb-4 text-center">
            Enter the 6-digit code from your authenticator app.
          </p>

          {totpError && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
              {totpError}
            </div>
          )}

          <form onSubmit={handleTotpVerify} className="space-y-4">
            <Input
              label="Authentication code"
              type="text"
              inputMode="numeric"
              placeholder="000000"
              maxLength={6}
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
              autoFocus
            />
            <Button type="submit" className="w-full" loading={totpLoading}>
              Verify
            </Button>
          </form>

          <button
            type="button"
            className="mt-4 w-full text-center text-sm text-gray-500 hover:text-gray-700"
            onClick={() => {
              setRequires2fa(false);
              setTotpCode("");
              setTotpError("");
            }}
          >
            Back to login
          </button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="pt-8 pb-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-500 to-primary-400 bg-clip-text text-transparent">
            Pulse
          </h1>
          <p className="text-gray-500 mt-2 text-sm">Sign in to your account</p>
        </div>

        {apiError && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">
            {apiError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
          />
          <Input
            label="Password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
          />
          <Button type="submit" className="w-full" loading={loading}>
            Sign in
          </Button>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-white px-2 text-gray-500">or</span>
          </div>
        </div>

        <Button
          variant="secondary"
          className="w-full"
          onClick={() => {
            window.location.href = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/auth/google`;
          }}
        >
          <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </Button>

        {/* SSO section */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-white px-2 text-gray-500">or</span>
          </div>
        </div>

        <div>
          <p className="mb-3 text-sm font-medium text-gray-700">
            Sign in with SSO
          </p>
          {ssoError && (
            <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">
              {ssoError}
            </div>
          )}
          <form onSubmit={handleSSOContinue} className="flex gap-2">
            <div className="flex-1">
              <Input
                type="email"
                placeholder="you@company.com"
                value={ssoEmail}
                onChange={(e) => {
                  setSsoEmail(e.target.value);
                  setSsoError("");
                }}
              />
            </div>
            <Button type="submit" variant="secondary" loading={ssoLoading}>
              Continue
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-gray-500">
          Don&apos;t have an account?{" "}
          <Link
            to="/register"
            className="font-medium text-primary-500 hover:text-primary-500"
          >
            Sign up
          </Link>
        </p>

        {import.meta.env.DEV && (
          <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
            <p className="text-xs font-medium text-gray-500 mb-2">Dev login</p>
            <button
              type="button"
              className="w-full text-left text-xs text-gray-600 hover:bg-gray-100 rounded px-2 py-1.5 transition-colors"
              onClick={() => {
                setEmail("test@pulse.dev");
                setPassword("test");
              }}
            >
              <span className="font-mono">test@pulse.dev</span> / <span className="font-mono">test</span>
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
