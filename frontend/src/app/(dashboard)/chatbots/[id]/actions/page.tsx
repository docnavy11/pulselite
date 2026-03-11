import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Plus, Trash2, Zap } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Action, ActionCreate, ActionParameter, ActionType, IntegrationConfig } from "@/lib/types";
import { getActions, createAction, updateAction, deleteAction, getIntegrations } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  collect_lead: "Collect Lead",
  webhook: "Webhook",
  custom_button: "Custom Button",
  slack_message: "Slack Message",
  calendly: "Calendly",
  calcom: "Cal.com",
  custom_tool: "Custom JS Tool",
  stripe_lookup: "Stripe Lookup",
  salesforce_ticket: "Salesforce Ticket",
};

const EMPTY_FORM: ActionCreate = {
  action_type: "webhook",
  name: "",
  trigger_description: "",
  config: {},
  parameters: [],
};

function ConfigFields({
  type,
  config,
  onChange,
  slackIntegration,
}: {
  type: ActionType;
  config: Record<string, string>;
  onChange: (config: Record<string, string>) => void;
  slackIntegration: IntegrationConfig | null;
}) {
  function textField(key: string, label: string, placeholder: string, required = false) {
    return (
      <div key={key}>
        <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
          {label} {required && <span className="text-red-400">*</span>}
        </label>
        <input
          value={config[key] ?? ""}
          onChange={(e) => onChange({ ...config, [key]: e.target.value })}
          placeholder={placeholder}
          className="w-full px-3 py-2 text-sm border border-[#e8e2d9] rounded-lg focus:outline-none focus:border-primary-400 bg-white"
        />
      </div>
    );
  }

  if (type === "webhook") return (
    <div className="space-y-3">
      {textField("url", "Webhook URL", "https://your-server.com/hook", true)}
      <div>
        <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Method</label>
        <select
          value={config.method ?? "POST"}
          onChange={(e) => onChange({ ...config, method: e.target.value })}
          className="w-full px-3 py-2 text-sm border border-[#e8e2d9] rounded-lg focus:outline-none focus:border-primary-400 bg-white"
        >
          <option value="POST">POST</option>
          <option value="GET">GET</option>
        </select>
      </div>
      {textField("secret", "Secret (optional)", "used to sign payloads")}
    </div>
  );

  if (type === "collect_lead") return (
    <div className="space-y-3">
      {textField("fields", "Fields to collect", "name,email,phone")}
      <p className="text-[11px] text-gray-400">Comma-separated. Defaults to name and email.</p>
    </div>
  );

  if (type === "custom_button") return (
    <div className="space-y-3">
      {textField("label", "Button label", "Book a demo", true)}
      {textField("url", "Button URL", "https://calendly.com/...", true)}
    </div>
  );

  if (type === "slack_message") {
    const slackWebhookUrl = slackIntegration?.config?.webhook_url as string | undefined;
    const hasWorkspaceSlack = slackIntegration?.is_connected && !!slackWebhookUrl;
    return (
      <div className="space-y-3">
        {hasWorkspaceSlack && (
          <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-green-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-medium text-green-700">Workspace Slack connected</p>
              <p className="text-[11px] text-green-600 truncate">{slackWebhookUrl}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="slack_source"
                  checked={!config.webhook_url}
                  onChange={() => {
                    const { webhook_url, ...rest } = config;
                    onChange(rest);
                  }}
                  className="accent-primary-500"
                />
                <span className="text-[11px] text-gray-600">Use workspace</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="slack_source"
                  checked={!!config.webhook_url}
                  onChange={() => onChange({ ...config, webhook_url: "" })}
                  className="accent-primary-500"
                />
                <span className="text-[11px] text-gray-600">Custom</span>
              </label>
            </div>
          </div>
        )}
        {(!hasWorkspaceSlack || config.webhook_url !== undefined) &&
          textField("webhook_url", "Slack Webhook URL", "https://hooks.slack.com/services/...", !hasWorkspaceSlack)}
        {textField("message_template", "Message template (optional)", "New lead: {{name}} — {{message}}")}
        <p className="text-[11px] text-gray-400">
          Available variables: {"{{message}}"}, {"{{response}}"}, {"{{conversation_id}}"}
        </p>
      </div>
    );
  }

  if (type === "calendly") return (
    <div className="space-y-3">
      {textField("calendly_url", "Calendly URL", "https://calendly.com/your-name/30min", true)}
    </div>
  );

  if (type === "calcom") return (
    <div className="space-y-3">
      {textField("calcom_url", "Cal.com URL", "https://cal.com/your-name/30min", true)}
    </div>
  );

  if (type === "custom_tool") return (
    <div className="space-y-3">
      {textField("tool_name", "Function name", "openCart", true)}
      <p className="text-[11px] text-gray-400">
        Must match the name passed to{" "}
        <code className="bg-gray-100 px-1 rounded text-[10px]">window.__pulseRegisterTool(&quot;name&quot;, fn)</code>{" "}
        on your page.
      </p>
    </div>
  );

  if (type === "stripe_lookup") return (
    <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
      <p className="text-[12px] text-amber-700 font-medium">Requires Stripe integration</p>
      <p className="text-[11px] text-amber-600 mt-0.5">
        Configure your Stripe API key in Settings → Integrations first.
        Add an <code className="bg-amber-100 px-1 rounded text-[10px]">email</code> parameter so the AI can collect it before lookup.
      </p>
    </div>
  );

  if (type === "salesforce_ticket") return (
    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <p className="text-[12px] text-blue-700 font-medium">Requires Salesforce integration</p>
      <p className="text-[11px] text-blue-600 mt-0.5">
        Configure Salesforce in Settings → Integrations. Add an{" "}
        <code className="bg-blue-100 px-1 rounded text-[10px]">email</code> parameter to attach the contact&apos;s email to the created case.
      </p>
    </div>
  );

  return null;
}

function ParameterEditor({
  parameters,
  onChange,
}: {
  parameters: ActionParameter[];
  onChange: (params: ActionParameter[]) => void;
}) {
  function addParam() {
    onChange([...parameters, { name: "", type: "string", required: false, description: "" }]);
  }
  function removeParam(i: number) {
    onChange(parameters.filter((_, idx) => idx !== i));
  }
  function updateParam(i: number, field: keyof ActionParameter, value: unknown) {
    onChange(parameters.map((p, idx) => (idx === i ? { ...p, [field]: value } : p)));
  }

  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center justify-between">
        <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
          Parameters (optional)
        </label>
        <button
          type="button"
          onClick={addParam}
          className="text-[11px] text-primary-500 font-medium hover:text-primary-600"
        >
          + Add parameter
        </button>
      </div>
      <p className="text-[11px] text-gray-400">
        If you add parameters, the AI will collect them from the user before triggering this action.
      </p>
      {parameters.map((param, i) => (
        <div key={i} className="flex gap-2 items-start p-3 bg-white border border-[#e8e2d9] rounded-lg">
          <input
            value={param.name}
            onChange={(e) => updateParam(i, "name", e.target.value)}
            placeholder="name"
            className="w-24 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400"
          />
          <select
            value={param.type}
            onChange={(e) => updateParam(i, "type", e.target.value)}
            className="w-24 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400 bg-white"
          >
            <option value="string">string</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
          </select>
          <input
            value={param.description}
            onChange={(e) => updateParam(i, "description", e.target.value)}
            placeholder="description"
            className="flex-1 px-2 py-1.5 text-xs border border-[#e8e2d9] rounded-md focus:outline-none focus:border-primary-400"
          />
          <label className="flex items-center gap-1 text-[11px] text-gray-500 whitespace-nowrap mt-1.5">
            <input
              type="checkbox"
              checked={param.required}
              onChange={(e) => updateParam(i, "required", e.target.checked)}
              className="accent-primary-500"
            />
            required
          </label>
          <button
            type="button"
            onClick={() => removeParam(i)}
            className="text-gray-300 hover:text-red-400 mt-0.5 text-lg leading-none"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

function ActionTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    webhook: "bg-blue-50 text-blue-600 border-blue-200",
    collect_lead: "bg-orange-50 text-orange-600 border-orange-200",
    custom_button: "bg-purple-50 text-purple-600 border-purple-200",
    slack_message: "bg-green-50 text-green-700 border-green-200",
    calendly: "bg-cyan-50 text-cyan-700 border-cyan-200",
    calcom: "bg-teal-50 text-teal-700 border-teal-200",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold border ${colors[type] ?? "bg-gray-50 text-gray-600 border-gray-200"}`}>
      {ACTION_TYPE_LABELS[type as ActionType] ?? type}
    </span>
  );
}

export default function ActionsPage() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ActionCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [slackIntegration, setSlackIntegration] = useState<IntegrationConfig | null>(null);

  useEffect(() => {
    if (!workspace) return;
    Promise.all([
      getActions(workspace.id, chatbotId),
      getIntegrations(workspace.id).catch(() => [] as IntegrationConfig[]),
    ]).then(([acts, integrations]) => {
      setActions(acts);
      setSlackIntegration(integrations.find((i) => i.service === "slack" || i.service === "slack_bot") ?? null);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  async function handleSave() {
    if (!workspace || !form.name.trim() || !form.trigger_description.trim()) return;
    setSaving(true);
    try {
      const created = await createAction(workspace.id, chatbotId, form);
      setActions((prev) => [...prev, created]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(action: Action) {
    if (!workspace) return;
    setTogglingId(action.id);
    try {
      const updated = await updateAction(workspace.id, chatbotId, action.id, { is_enabled: !action.is_enabled });
      setActions((prev) => prev.map((a) => (a.id === action.id ? updated : a)));
    } finally {
      setTogglingId(null);
    }
  }

  async function handleDelete(id: string) {
    if (!workspace) return;
    setDeletingId(id);
    try {
      await deleteAction(workspace.id, chatbotId, id);
      setActions((prev) => prev.filter((a) => a.id !== id));
    } finally {
      setDeletingId(null);
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
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Actions</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            Trigger webhooks, lead forms, or booking links automatically during chat.
          </p>
        </div>
        {!showForm && (
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="h-4 w-4 mr-1.5" />
            Add action
          </Button>
        )}
      </div>

      {/* Add form */}
      {showForm && (
        <div className="mb-6 p-5 border border-[#e8e2d9] rounded-xl bg-[#faf8f5] space-y-4">
          <p className="text-[13px] font-semibold text-gray-800">New action</p>

          <div>
            <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Action type
            </label>
            <select
              value={form.action_type}
              onChange={(e) => setForm({ ...form, action_type: e.target.value as ActionType, config: {} })}
              className="w-full px-3 py-2 text-sm border border-[#e8e2d9] rounded-lg focus:outline-none focus:border-primary-400 bg-white"
            >
              {(Object.entries(ACTION_TYPE_LABELS) as [ActionType, string][]).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Name <span className="text-red-400">*</span>
            </label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Notify sales team"
              className="w-full px-3 py-2 text-sm border border-[#e8e2d9] rounded-lg focus:outline-none focus:border-primary-400 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
              When to trigger <span className="text-red-400">*</span>
            </label>
            <textarea
              value={form.trigger_description}
              onChange={(e) => setForm({ ...form, trigger_description: e.target.value })}
              placeholder="e.g. When the user asks about pricing or wants to speak to a human"
              rows={2}
              className="w-full px-3 py-2 text-sm border border-[#e8e2d9] rounded-lg focus:outline-none focus:border-primary-400 bg-white resize-none"
            />
            <p className="mt-1 text-[11px] text-gray-400">
              Plain English — the AI uses this to decide when to fire the action.
            </p>
          </div>

          <ConfigFields
            type={form.action_type}
            config={form.config}
            onChange={(config) => setForm({ ...form, config })}
            slackIntegration={slackIntegration}
          />

          <ParameterEditor
            parameters={form.parameters ?? []}
            onChange={(parameters) => setForm({ ...form, parameters })}
          />

          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              onClick={handleSave}
              loading={saving}
              disabled={!form.name.trim() || !form.trigger_description.trim()}
            >
              Save action
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {actions.length === 0 && !showForm && (
        <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-[#e8e2d9] rounded-xl">
          <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center mb-3">
            <Zap className="h-5 w-5 text-primary-400" />
          </div>
          <h3 className="text-[14px] font-semibold text-gray-700 mb-1">No actions yet</h3>
          <p className="text-[12px] text-gray-400 max-w-xs">
            Actions let your chatbot trigger webhooks, capture leads, or show booking links — automatically, when the moment is right.
          </p>
        </div>
      )}

      {/* Actions list */}
      <div className="space-y-3">
        {actions.map((action) => (
          <div
            key={action.id}
            className={`flex items-start gap-3 p-4 border rounded-xl bg-white transition-opacity ${
              action.is_enabled ? "border-[#e8e2d9]" : "border-[#e8e2d9] opacity-50"
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <ActionTypeBadge type={action.action_type} />
                <span className="text-[13px] font-semibold text-gray-800 truncate">{action.name}</span>
              </div>
              <p className="text-[12px] text-gray-400 line-clamp-2 mt-0.5">{action.trigger_description}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0 mt-0.5">
              <button
                onClick={() => handleToggle(action)}
                disabled={togglingId === action.id}
                className={`text-[11px] font-medium px-2.5 py-1 rounded-lg border transition-colors disabled:opacity-50 ${
                  action.is_enabled
                    ? "border-[#e8e2d9] text-gray-500 hover:bg-[#faf8f5]"
                    : "border-primary-200 text-primary-500 bg-primary-50 hover:bg-primary-100"
                }`}
              >
                {togglingId === action.id ? "…" : action.is_enabled ? "Enabled" : "Disabled"}
              </button>
              <button
                onClick={() => handleDelete(action.id)}
                disabled={deletingId === action.id}
                className="p-1.5 text-gray-300 hover:text-red-400 transition-colors disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
