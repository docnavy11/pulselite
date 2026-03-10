"use client";

import { useState, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  getWebhooks,
  createWebhook,
  deleteWebhook,
  Webhook,
} from "@/lib/api-functions";

const ALL_EVENT_TYPES = [
  { value: "conversation.created", label: "Conversation Created" },
  { value: "conversation.escalated", label: "Conversation Escalated" },
  { value: "conversation.resolved", label: "Conversation Resolved" },
  { value: "message.feedback", label: "Message Feedback" },
];

export default function WebhooksPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([
    "conversation.created",
    "conversation.escalated",
  ]);

  useEffect(() => {
    if (!workspace) return;
    getWebhooks(workspace.id)
      .then(setWebhooks)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  function toggleEvent(value: string) {
    setSelectedEvents((prev) =>
      prev.includes(value) ? prev.filter((e) => e !== value) : [...prev, value]
    );
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setError(null);
    setSaving(true);
    try {
      const payload: { url: string; event_types: string[]; secret?: string } = {
        url,
        event_types: selectedEvents,
      };
      if (secret) payload.secret = secret;
      const created = await createWebhook(workspace.id, payload);
      setWebhooks((prev) => [...prev, created]);
      setUrl("");
      setSecret("");
      setSelectedEvents(["conversation.created", "conversation.escalated"]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create webhook";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(webhookId: string) {
    if (!workspace) return;
    try {
      await deleteWebhook(workspace.id, webhookId);
      setWebhooks((prev) => prev.filter((h) => h.id !== webhookId));
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Webhooks</h1>
      </div>

      <p className="text-sm text-gray-500 mb-6">
        Configure outbound webhooks to receive real-time notifications when key events happen in your workspace.
      </p>

      {/* Existing webhooks */}
      {webhooks.length > 0 && (
        <Card className="mb-8">
          <CardContent className="py-5">
            <h2 className="text-base font-semibold text-gray-900 mb-4">Active Webhooks</h2>
            <div className="divide-y divide-gray-100">
              {webhooks.map((hook) => (
                <div key={hook.id} className="flex items-start justify-between py-3 gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{hook.url}</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {hook.event_types.map((et) => (
                        <span
                          key={et}
                          className="inline-flex items-center rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
                        >
                          {et}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Added {new Date(hook.created_at).toLocaleDateString()}
                      {" · "}
                      <span className={hook.is_active ? "text-green-600" : "text-gray-400"}>
                        {hook.is_active ? "Active" : "Inactive"}
                      </span>
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(hook.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors shrink-0 mt-0.5"
                    aria-label="Delete webhook"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add webhook form */}
      <Card>
        <CardContent className="pt-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Add Webhook</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Endpoint URL <span className="text-red-500">*</span>
              </label>
              <Input
                type="url"
                placeholder="https://your-server.com/webhook"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
              <p className="text-xs text-gray-400 mt-1">Must use HTTPS.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Events to subscribe to
              </label>
              <div className="space-y-2">
                {ALL_EVENT_TYPES.map((et) => (
                  <label key={et.value} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedEvents.includes(et.value)}
                      onChange={() => toggleEvent(et.value)}
                      className="h-4 w-4 rounded border-gray-300 text-primary-500"
                    />
                    <span className="text-sm text-gray-700">{et.label}</span>
                    <code className="text-xs text-gray-400 font-mono">{et.value}</code>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Secret (optional)
              </label>
              <Input
                type="text"
                placeholder="Used to sign requests with X-Pulse-Signature header"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
              />
              <p className="text-xs text-gray-400 mt-1">
                If set, each request will include an{" "}
                <code className="font-mono">X-Pulse-Signature</code> header with an HMAC-SHA256
                signature you can use to verify authenticity.
              </p>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button type="submit" loading={saving} disabled={selectedEvents.length === 0}>
              Add Webhook
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
