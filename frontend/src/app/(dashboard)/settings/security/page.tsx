import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { ShieldAlert, ShieldCheck } from "lucide-react";

interface SetupResponse {
  secret: string;
  qr_uri: string;
}

interface StatusResponse {
  two_fa_enabled: boolean;
}

export default function SecuritySettingsPage() {
  const [is2faEnabled, setIs2faEnabled] = useState<boolean | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);

  // Setup flow state
  const [setupData, setSetupData] = useState<SetupResponse | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [verifyCode, setVerifyCode] = useState("");
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState("");
  const [verifySuccess, setVerifySuccess] = useState(false);

  // Disable flow state
  const [showDisable, setShowDisable] = useState(false);
  const [disableCode, setDisableCode] = useState("");
  const [disableLoading, setDisableLoading] = useState(false);
  const [disableError, setDisableError] = useState("");

  useEffect(() => {
    api
      .get<StatusResponse>("/api/v1/auth/2fa/status")
      .then((data) => {
        setIs2faEnabled(data.two_fa_enabled);
      })
      .catch(() => {
        setIs2faEnabled(false);
      })
      .finally(() => {
        setLoadingStatus(false);
      });
  }, []);

  async function handleSetup() {
    setSetupLoading(true);
    setVerifyError("");
    setVerifySuccess(false);
    try {
      const data = await api.post<SetupResponse>("/api/v1/auth/2fa/setup");
      setSetupData(data);
    } catch {
      setVerifyError("Failed to start 2FA setup. Please try again.");
    } finally {
      setSetupLoading(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setVerifyError("");
    if (!verifyCode.trim()) {
      setVerifyError("Please enter the 6-digit code");
      return;
    }
    setVerifyLoading(true);
    try {
      await api.post("/api/v1/auth/2fa/verify", { code: verifyCode.trim() });
      setIs2faEnabled(true);
      setVerifySuccess(true);
      setSetupData(null);
      setVerifyCode("");
    } catch (err) {
      if (err instanceof ApiError) {
        try {
          const parsed = JSON.parse(err.message);
          setVerifyError(parsed.detail ?? "Invalid code");
        } catch {
          setVerifyError("Invalid TOTP code. Please try again.");
        }
      } else {
        setVerifyError("Verification failed. Please try again.");
      }
    } finally {
      setVerifyLoading(false);
    }
  }

  async function handleDisable(e: React.FormEvent) {
    e.preventDefault();
    setDisableError("");
    if (!disableCode.trim()) {
      setDisableError("Please enter your current 6-digit code");
      return;
    }
    setDisableLoading(true);
    try {
      await api.post("/api/v1/auth/2fa/disable", { code: disableCode.trim() });
      setIs2faEnabled(false);
      setShowDisable(false);
      setDisableCode("");
    } catch (err) {
      if (err instanceof ApiError) {
        try {
          const parsed = JSON.parse(err.message);
          setDisableError(parsed.detail ?? "Invalid code");
        } catch {
          setDisableError("Invalid TOTP code. Please try again.");
        }
      } else {
        setDisableError("Failed to disable 2FA. Please try again.");
      }
    } finally {
      setDisableLoading(false);
    }
  }

  const qrImageUrl = setupData
    ? `https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(setupData.qr_uri)}&size=200x200`
    : null;

  if (loadingStatus) {
    return (
      <div className="p-8">
        <p className="text-gray-500 text-sm">Loading security settings...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Security</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Manage your account security settings.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 pb-6">
          <div className="flex items-start gap-4">
            <div className="rounded-lg bg-primary-50 p-2">
              <ShieldAlert className="h-6 w-6 text-primary-500" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <h2 className="text-base font-semibold text-gray-900">
                  Two-Factor Authentication
                </h2>
                {is2faEnabled && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                    <ShieldCheck className="h-3 w-3" />
                    Active
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mb-4">
                Add an extra layer of security to your account using a TOTP
                authenticator app (e.g. Google Authenticator, Authy, 1Password).
              </p>

              {/* Success message after enabling */}
              {verifySuccess && (
                <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">
                  Two-factor authentication has been enabled successfully.
                </div>
              )}

              {/* 2FA is ENABLED */}
              {is2faEnabled && (
                <>
                  {!showDisable ? (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setShowDisable(true);
                        setDisableCode("");
                        setDisableError("");
                      }}
                    >
                      Disable 2FA
                    </Button>
                  ) : (
                    <form onSubmit={handleDisable} className="space-y-3 max-w-xs">
                      <p className="text-sm text-gray-600">
                        Enter your current authenticator code to confirm:
                      </p>
                      {disableError && (
                        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
                          {disableError}
                        </div>
                      )}
                      <Input
                        type="text"
                        inputMode="numeric"
                        placeholder="000000"
                        maxLength={6}
                        value={disableCode}
                        onChange={(e) =>
                          setDisableCode(e.target.value.replace(/\D/g, ""))
                        }
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <Button type="submit" loading={disableLoading}>
                          Confirm Disable
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => {
                            setShowDisable(false);
                            setDisableCode("");
                            setDisableError("");
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </form>
                  )}
                </>
              )}

              {/* 2FA is DISABLED — show setup flow */}
              {!is2faEnabled && (
                <>
                  {!setupData ? (
                    <Button onClick={handleSetup} loading={setupLoading}>
                      Enable Two-Factor Authentication
                    </Button>
                  ) : (
                    <div className="space-y-4">
                      <p className="text-sm text-gray-700 font-medium">
                        Step 1: Scan this QR code with your authenticator app
                      </p>
                      {/* QR code via public free API */}
                      <div className="inline-block rounded-lg border border-gray-200 p-3 bg-white">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={qrImageUrl!}
                          alt="TOTP QR code"
                          width={200}
                          height={200}
                        />
                      </div>

                      <p className="text-sm text-gray-500">
                        Or enter this secret manually in your authenticator app:
                      </p>
                      <code className="block rounded bg-gray-100 px-3 py-2 text-sm font-mono text-gray-800 break-all select-all">
                        {setupData.secret}
                      </code>

                      <p className="text-sm text-gray-700 font-medium mt-4">
                        Step 2: Enter the 6-digit code from your app to confirm
                      </p>
                      {verifyError && (
                        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
                          {verifyError}
                        </div>
                      )}
                      <form onSubmit={handleVerify} className="flex gap-2 max-w-xs">
                        <Input
                          type="text"
                          inputMode="numeric"
                          placeholder="000000"
                          maxLength={6}
                          value={verifyCode}
                          onChange={(e) =>
                            setVerifyCode(e.target.value.replace(/\D/g, ""))
                          }
                          autoFocus
                        />
                        <Button type="submit" loading={verifyLoading}>
                          Verify &amp; Enable
                        </Button>
                      </form>

                      <button
                        type="button"
                        className="text-sm text-gray-500 hover:text-gray-700"
                        onClick={() => {
                          setSetupData(null);
                          setVerifyCode("");
                          setVerifyError("");
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
