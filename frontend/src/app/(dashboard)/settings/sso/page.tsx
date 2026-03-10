"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getSSOConfig, updateSSOConfig, deleteSSOConfig } from "@/lib/api-functions";
import { SSOConfig } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default function SSOPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [config, setConfig] = useState<SSOConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form fields
  const [providerName, setProviderName] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [discoveryUrl, setDiscoveryUrl] = useState("");
  const [emailDomain, setEmailDomain] = useState("");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (!workspace?.id) return;

    async function fetchConfig() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSSOConfig(workspace!.id);
        setConfig(data);
        if (data) {
          setProviderName(data.provider_name);
          setClientId(data.client_id);
          setClientSecret(""); // leave blank; backend shows "***"
          setDiscoveryUrl(data.discovery_url);
          setEmailDomain(data.email_domain);
          setIsActive(data.is_active);
        }
      } catch {
        setError("Failed to load SSO configuration.");
      } finally {
        setLoading(false);
      }
    }

    fetchConfig();
  }, [workspace?.id]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace?.id) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const body = {
        provider_name: providerName,
        client_id: clientId,
        client_secret: clientSecret || undefined,
        discovery_url: discoveryUrl,
        email_domain: emailDomain,
        is_active: isActive,
      };
      const updated = await updateSSOConfig(workspace.id, body);
      setConfig(updated);
      setSuccess("SSO configuration saved.");
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError("Failed to save SSO configuration. Please check your inputs.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!workspace?.id) return;
    if (
      !window.confirm(
        "Are you sure you want to delete the SSO configuration? Your team will no longer be able to sign in with SSO."
      )
    )
      return;

    setDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      await deleteSSOConfig(workspace.id);
      setConfig(null);
      setProviderName("");
      setClientId("");
      setClientSecret("");
      setDiscoveryUrl("");
      setEmailDomain("");
      setIsActive(true);
      setSuccess("SSO configuration deleted.");
      setTimeout(() => setSuccess(null), 3000);
    } catch {
      setError("Failed to delete SSO configuration.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Single Sign-On (SSO)
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure OIDC-based SSO to let your team sign in with their identity
          provider.
        </p>
      </div>

      {loading ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-gray-500">
            Loading SSO configuration...
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-6 pb-6 space-y-6">
            {/* Status badge */}
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-gray-700">Status</span>
              {config ? (
                <Badge variant="success">Configured</Badge>
              ) : (
                <Badge variant="default">Not configured</Badge>
              )}
            </div>

            {/* Feedback messages */}
            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-lg bg-green-50 p-3 text-sm text-green-600">
                {success}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSave} className="space-y-4">
              <Input
                label="Provider Name"
                type="text"
                placeholder="Okta / Microsoft Entra / Google Workspace"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                required
              />

              <Input
                label="Email Domain"
                type="text"
                placeholder="company.com"
                value={emailDomain}
                onChange={(e) => setEmailDomain(e.target.value)}
                required
              />

              <Input
                label="Discovery URL"
                type="text"
                placeholder="https://your-org.okta.com/oauth2/default"
                value={discoveryUrl}
                onChange={(e) => setDiscoveryUrl(e.target.value)}
                required
              />

              <Input
                label="Client ID"
                type="text"
                placeholder="Client ID from your IdP"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                required
              />

              <Input
                label="Client Secret"
                type="password"
                placeholder={
                  config ? "Leave blank to keep existing secret" : "Client Secret from your IdP"
                }
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
              />

              <div className="flex items-center gap-3">
                <input
                  id="isActive"
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
                <label
                  htmlFor="isActive"
                  className="text-sm font-medium text-gray-700"
                >
                  Enable SSO for this workspace
                </label>
              </div>

              <div className="flex gap-3 pt-2">
                <Button type="submit" loading={saving}>
                  Save Configuration
                </Button>
                {config && (
                  <Button
                    type="button"
                    variant="danger"
                    loading={deleting}
                    onClick={handleDelete}
                  >
                    Delete
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Help box */}
      <Card>
        <CardContent className="pt-5 pb-5">
          <h2 className="text-sm font-semibold text-gray-800 mb-3">
            Setup Instructions
          </h2>

          <div className="space-y-3 text-sm text-gray-600">
            <div>
              <p className="font-medium text-gray-700 mb-1">
                Callback URL to register in your IdP:
              </p>
              <code className="block rounded bg-gray-100 px-3 py-2 font-mono text-xs text-gray-800 break-all">
                http://localhost:8000/api/v1/auth/sso/callback
              </code>
            </div>

            <div>
              <p className="font-medium text-gray-700 mb-2">
                Common Discovery URLs:
              </p>
              <ul className="space-y-1.5">
                <li>
                  <span className="font-medium">Okta:</span>{" "}
                  <code className="text-xs bg-gray-100 rounded px-1 py-0.5">
                    https://your-domain.okta.com/oauth2/default
                  </code>
                </li>
                <li>
                  <span className="font-medium">Microsoft Entra:</span>{" "}
                  <code className="text-xs bg-gray-100 rounded px-1 py-0.5">
                    https://login.microsoftonline.com/&#123;tenant-id&#125;/v2.0
                  </code>
                </li>
                <li>
                  <span className="font-medium">Google Workspace:</span>{" "}
                  <code className="text-xs bg-gray-100 rounded px-1 py-0.5">
                    https://accounts.google.com
                  </code>
                </li>
                <li>
                  <span className="font-medium">Auth0:</span>{" "}
                  <code className="text-xs bg-gray-100 rounded px-1 py-0.5">
                    https://your-domain.auth0.com
                  </code>
                </li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
