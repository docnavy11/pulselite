"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Trash2, Zap } from "lucide-react";
import { getActions, createAction, deleteAction } from "@/lib/api-functions";
import { Action } from "@/lib/types";

const ACTION_TYPES = [
  { value: "collect_lead", label: "Collect Lead", description: "Show a form to capture name and email" },
  { value: "webhook", label: "Webhook", description: "POST data to a custom URL" },
  { value: "custom_button", label: "Custom Button", description: "Show a clickable button that opens a URL" },
  { value: "slack_message", label: "Slack Message", description: "Send a message to a Slack channel webhook" },
  { value: "calendly", label: "Calendly", description: "Show a Calendly booking link in the chat" },
  { value: "calcom", label: "Cal.com", description: "Show a Cal.com booking link in the chat" },
  { value: "shopify_order_status", label: "Shopify: Order Status", description: "Look up a customer's order status by order number" },
  { value: "shopify_storefront", label: "Shopify: Store Link", description: "Show a button linking to your Shopify store" },
  { value: "stripe_get_invoices", label: "Stripe: Get Invoices", description: "Look up a customer's recent invoices by email" },
  { value: "stripe_subscription_status", label: "Stripe: Subscription Status", description: "Show a customer's current subscription plan and status" },
  { value: "salesforce_contact_lookup", label: "Salesforce: Contact Lookup", description: "Look up a Salesforce contact by email" },
  { value: "salesforce_create_case", label: "Salesforce: Create Case", description: "Create a support case in Salesforce" },
];

export default function ActionsPage() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    action_type: "collect_lead",
    name: "",
    trigger_description: "",
    config: {} as Record<string, unknown>,
  });

  useEffect(() => {
    if (!workspace) return;
    getActions(workspace.id, chatbotId)
      .then((data) => setActions(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  async function handleCreate() {
    if (!workspace) return;
    setSaving(true);
    setError(null);
    try {
      const action = await createAction(workspace.id, chatbotId, form);
      setActions((prev) => [...prev, action]);
      setShowForm(false);
      setForm({ action_type: "collect_lead", name: "", trigger_description: "", config: {} });
    } catch {
      setError("Failed to save action. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(actionId: string) {
    if (!workspace) return;
    try {
      await deleteAction(workspace.id, chatbotId, actionId);
      setActions((prev) => prev.filter((a) => a.id !== actionId));
    } catch {
      setError("Failed to delete action. Please try again.");
    }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner className="h-6 w-6 text-primary-600" /></div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">AI Actions</h2>
          <p className="text-sm text-gray-500">Actions the AI can trigger during conversations.</p>
        </div>
        <Button onClick={() => setShowForm(true)} size="sm">
          <Zap className="h-4 w-4 mr-1" />
          Add Action
        </Button>
      </div>

      {error && (
        <div className="mb-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {actions.length === 0 && !showForm && (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-gray-400">
            <Zap className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No actions yet</p>
            <p className="text-xs mt-1">Add actions the AI can trigger mid-conversation</p>
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card className="mb-4">
          <CardContent className="py-5 space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Action Type</label>
              <select
                value={form.action_type}
                onChange={(e) => setForm({ ...form, action_type: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {ACTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label} — {t.description}</option>
                ))}
              </select>
            </div>
            <Input
              label="Button / Action Label"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder='e.g. "Get a Demo"'
            />
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">
                When should the AI trigger this?
              </label>
              <textarea
                value={form.trigger_description}
                onChange={(e) => setForm({ ...form, trigger_description: e.target.value })}
                rows={3}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Trigger this when the user expresses interest in a demo or pricing"
              />
            </div>
            {form.action_type === "webhook" && (
              <Input
                label="Webhook URL"
                value={(form.config.url as string) || ""}
                onChange={(e) => setForm({ ...form, config: { ...form.config, url: e.target.value } })}
                placeholder="https://your-server.com/webhook"
              />
            )}
            {form.action_type === "custom_button" && (
              <>
                <Input
                  label="Button Label"
                  value={(form.config.label as string) || ""}
                  onChange={(e) => setForm({ ...form, config: { ...form.config, label: e.target.value } })}
                  placeholder='e.g. "Book a Demo"'
                />
                <Input
                  label="Button URL"
                  value={(form.config.url as string) || ""}
                  onChange={(e) => setForm({ ...form, config: { ...form.config, url: e.target.value } })}
                  placeholder="https://example.com/book"
                />
              </>
            )}
            {form.action_type === "slack_message" && (
              <>
                <Input
                  label="Slack Webhook URL"
                  value={(form.config.webhook_url as string) || ""}
                  onChange={(e) => setForm({ ...form, config: { ...form.config, webhook_url: e.target.value } })}
                  placeholder="https://hooks.slack.com/services/..."
                />
                <Input
                  label="Message Template"
                  value={(form.config.message_template as string) || ""}
                  onChange={(e) => setForm({ ...form, config: { ...form.config, message_template: e.target.value } })}
                  placeholder="New conversation from Pulse chat"
                />
              </>
            )}
            {(form.action_type === "calendly" || form.action_type === "calcom") && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Scheduling URL
                  </label>
                  <Input
                    value={(form.config.scheduling_url as string) || ""}
                    onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, scheduling_url: e.target.value } }))}
                    placeholder={form.action_type === "calendly" ? "https://calendly.com/your-name/30min" : "https://cal.com/your-name/30min"}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Button Label
                  </label>
                  <Input
                    value={(form.config.label as string) || ""}
                    onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, label: e.target.value } }))}
                    placeholder={form.action_type === "calendly" ? "Book a meeting" : "Schedule a call"}
                  />
                </div>
              </>
            )}
            {form.action_type === "shopify_order_status" && (
              <Input
                label="Shop Domain"
                value={(form.config.shop_domain as string) || ""}
                onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, shop_domain: e.target.value } }))}
                placeholder="mystore.myshopify.com"
              />
            )}
            {form.action_type === "shopify_storefront" && (
              <>
                <Input
                  label="Store URL"
                  value={(form.config.shop_url as string) || ""}
                  onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, shop_url: e.target.value } }))}
                  placeholder="https://mystore.com"
                />
                <Input
                  label="Button Label"
                  value={(form.config.button_label as string) || ""}
                  onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, button_label: e.target.value } }))}
                  placeholder="Shop Now"
                />
              </>
            )}
            {form.action_type === "salesforce_create_case" && (
              <Input
                label="Case Subject Prefix (optional)"
                value={(form.config.default_subject_prefix as string) || ""}
                onChange={(e) => setForm((f) => ({ ...f, config: { ...f.config, default_subject_prefix: e.target.value } }))}
                placeholder="Support: "
              />
            )}
            <div className="flex gap-2">
              <Button onClick={handleCreate} loading={saving} disabled={!form.name || !form.trigger_description}>
                Save Action
              </Button>
              <Button variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {actions.map((action) => (
          <Card key={action.id}>
            <CardContent className="py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                  <Zap className="h-4 w-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">{action.name}</span>
                    <Badge variant="default">{action.action_type}</Badge>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{action.trigger_description}</p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(action.id)}
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-all duration-200"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
