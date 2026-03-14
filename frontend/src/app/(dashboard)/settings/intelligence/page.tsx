import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  getIntelligenceConfig,
  updateIntelligenceConfig,
  triggerAnalyzeAll,
  triggerSentimentTrends,
  triggerClusterGaps,
  type IntelligenceConfig,
} from "@/lib/api-functions";

interface TaskDef {
  key: keyof IntelligenceConfig;
  label: string;
  description: string;
  schedule: string;
  triggerLabel: string;
  trigger: (wsId: string) => Promise<unknown>;
}

const TASKS: TaskDef[] = [
  {
    key: "auto_analyze",
    label: "Conversation Analysis",
    description:
      "Automatically analyze every conversation after it completes. Extracts sentiment, intent, topics, and outcome using LLM.",
    schedule: "After every chat response",
    triggerLabel: "Analyze all unanalyzed",
    trigger: triggerAnalyzeAll,
  },
  {
    key: "sentiment_trends",
    label: "Sentiment Trends",
    description:
      "Compute daily sentiment averages and detect negative-sentiment alerts across all workspaces.",
    schedule: "Daily at 04:00 UTC",
    triggerLabel: "Compute now",
    trigger: triggerSentimentTrends,
  },
  {
    key: "gap_clustering",
    label: "Gap Clustering",
    description:
      "Cluster unanswered questions into topic groups using BERTopic. Requires at least 10 unclustered gap events.",
    schedule: "Daily at 03:00 UTC",
    triggerLabel: "Cluster now",
    trigger: triggerClusterGaps,
  },
];

const FREQUENCY_OPTIONS = [
  { value: "off", label: "Off" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
];

const SECTION_OPTIONS = [
  { key: "conversations", label: "Conversations (total, resolved, escalated)" },
  { key: "confidence", label: "Confidence Score" },
  { key: "sentiment", label: "Sentiment Score & Trend" },
  { key: "gaps", label: "Knowledge Gaps" },
  { key: "top_topics", label: "Top 5 Topics" },
  { key: "qa_performance", label: "Q&A Performance" },
];

export default function IntelligenceSettingsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [config, setConfig] = useState<IntelligenceConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<Record<string, string>>({});
  const [triggering, setTriggering] = useState<Record<string, boolean>>({});
  const [reportSaving, setReportSaving] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getIntelligenceConfig(workspace.id)
      .then(setConfig)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id]);

  async function toggle(key: keyof IntelligenceConfig) {
    if (!workspace || !config) return;
    const newVal = !config[key];
    setSaving(key);
    try {
      const updated = await updateIntelligenceConfig(workspace.id, { [key]: newVal });
      setConfig(updated);
    } catch {
      // revert optimistic
    } finally {
      setSaving(null);
    }
  }

  async function runTrigger(key: string, trigger: (wsId: string) => Promise<unknown>) {
    if (!workspace) return;
    setTriggering((prev) => ({ ...prev, [key]: true }));
    setTriggerResult((prev) => ({ ...prev, [key]: "" }));
    try {
      const res = await trigger(workspace.id);
      const msg =
        typeof res === "object" && res !== null && "conversations_queued" in res
          ? `Queued ${(res as { conversations_queued: number }).conversations_queued} conversations`
          : "Dispatched";
      setTriggerResult((prev) => ({ ...prev, [key]: msg }));
    } catch (e) {
      setTriggerResult((prev) => ({
        ...prev,
        [key]: `Error: ${e instanceof Error ? e.message : "unknown"}`,
      }));
    } finally {
      setTriggering((prev) => ({ ...prev, [key]: false }));
    }
  }

  if (loading || !config) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold text-gray-900 mb-4">Intelligence Pipeline</h1>
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Intelligence Pipeline</h1>
        <p className="text-sm text-gray-500 mt-1">
          Configure which intelligence tasks run automatically. Admin only.
        </p>
      </div>

      <div className="space-y-4">
        {TASKS.map((task) => {
          const enabled = config[task.key];
          return (
            <div
              key={task.key}
              className={`bg-white border rounded-xl p-5 transition-colors ${
                enabled ? "border-gray-200" : "border-gray-200 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-sm font-semibold text-gray-900">
                      {task.label}
                    </h3>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        enabled
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {enabled ? "Active" : "Disabled"}
                    </span>
                  </div>
                  <p className="text-[13px] text-gray-500 mb-2">
                    {task.description}
                  </p>
                  <p className="text-[11px] text-gray-400">
                    Schedule: {task.schedule}
                  </p>
                </div>

                {/* Toggle */}
                <button
                  onClick={() => toggle(task.key)}
                  disabled={saving === task.key}
                  className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    enabled ? "bg-primary-500" : "bg-gray-200"
                  } ${saving === task.key ? "opacity-50" : ""}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      enabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              {/* Manual trigger */}
              <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-3">
                <button
                  onClick={() => runTrigger(task.key, task.trigger)}
                  disabled={triggering[task.key]}
                  className="px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 rounded-lg text-[12px] font-medium transition-colors disabled:opacity-50 disabled:cursor-wait"
                >
                  {triggering[task.key] ? "Running..." : task.triggerLabel}
                </button>
                {triggerResult[task.key] && (
                  <span
                    className={`text-[11px] font-medium ${
                      triggerResult[task.key].startsWith("Error")
                        ? "text-red-500"
                        : "text-green-600"
                    }`}
                  >
                    {triggerResult[task.key]}
                  </span>
                )}
              </div>
            </div>
          );
        })}

        {/* Email Reports */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Email Reports</h3>
          <p className="text-[13px] text-gray-500 mb-4">
            Receive periodic email reports with workspace stats. Configure email provider in{" "}
            <a href="/settings/integrations" className="text-primary-500 hover:underline">
              Integrations
            </a>.
          </p>

          {/* Frequency */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-500 mb-1">Frequency</label>
            <select
              value={config.report_frequency || "off"}
              onChange={async (e) => {
                if (!workspace) return;
                setReportSaving(true);
                try {
                  const updated = await updateIntelligenceConfig(workspace.id, {
                    report_frequency: e.target.value,
                  });
                  setConfig(updated);
                } finally {
                  setReportSaving(false);
                }
              }}
              disabled={reportSaving}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {FREQUENCY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Recipients */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Recipients (comma-separated)
            </label>
            <input
              type="text"
              defaultValue={(config.report_recipients || []).join(", ")}
              onBlur={async (e) => {
                if (!workspace) return;
                const recipients = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean);
                setReportSaving(true);
                try {
                  const updated = await updateIntelligenceConfig(workspace.id, {
                    report_recipients: recipients,
                  });
                  setConfig(updated);
                } finally {
                  setReportSaving(false);
                }
              }}
              placeholder="admin@example.com, team@example.com"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Defaults to the email configured in integrations if empty.
            </p>
          </div>

          {/* Section toggles */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">Sections</label>
            <div className="space-y-2">
              {SECTION_OPTIONS.map((section) => (
                <label key={section.key} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.report_sections?.[section.key] !== false}
                    onChange={async (e) => {
                      if (!workspace) return;
                      const newSections = {
                        ...config.report_sections,
                        [section.key]: e.target.checked,
                      };
                      setReportSaving(true);
                      try {
                        const updated = await updateIntelligenceConfig(workspace.id, {
                          report_sections: newSections,
                        });
                        setConfig(updated);
                      } finally {
                        setReportSaving(false);
                      }
                    }}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700">{section.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
