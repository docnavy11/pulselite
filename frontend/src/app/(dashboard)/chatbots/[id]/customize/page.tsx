"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { WidgetConfig } from "@/lib/types";
import { getWidgetConfig, updateWidgetConfig } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const colorPresets = [
  "#4f46e5",
  "#2563eb",
  "#0891b2",
  "#059669",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#db2777",
  "#0f172a",
];

export default function CustomizePage() {
  const params = useParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbotId = params.id as string;
  const [config, setConfig] = useState<WidgetConfig>({
    primary_color: "#4f46e5",
    position: "bottom-right",
    welcome_message: "Hi! How can I help you today?",
    launcher_text: "Chat with us",
    avatar_url: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [chipInput, setChipInput] = useState("");
  const [leadCaptureEnabled, setLeadCaptureEnabled] = useState(false);
  const [leadCaptureFields, setLeadCaptureFields] = useState<string[]>(["name", "email"]);
  const [allowedDomains, setAllowedDomains] = useState("");
  const [autoOpenDelay, setAutoOpenDelay] = useState<string>("");
  const [persistConversation, setPersistConversation] = useState(false);
  const [customCss, setCustomCss] = useState("");

  useEffect(() => {
    if (!workspace) return;
    getWidgetConfig(workspace.id, chatbotId)
      .then((cfg) => {
        setConfig(cfg);
        setQuickReplies(cfg.quick_replies || []);
        setLeadCaptureEnabled(cfg.lead_capture_enabled ?? false);
        setLeadCaptureFields(cfg.lead_capture_fields ?? ["name", "email"]);
        setAllowedDomains((cfg.allowed_domains ?? []).join(", "));
        setAutoOpenDelay(cfg.auto_open_delay != null ? String(cfg.auto_open_delay) : "");
        setPersistConversation(cfg.persist_conversation ?? false);
        setCustomCss(cfg.custom_css ?? "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  function addChip() {
    const val = chipInput.trim();
    if (val && !quickReplies.includes(val) && quickReplies.length < 8) {
      setQuickReplies([...quickReplies, val]);
      setChipInput("");
    }
  }

  async function handleSave() {
    if (!workspace) return;
    setSaving(true);
    try {
      await updateWidgetConfig(workspace.id, chatbotId, { ...config, quick_replies: quickReplies, lead_capture_enabled: leadCaptureEnabled, lead_capture_fields: leadCaptureFields, allowed_domains: allowedDomains.split(",").map(d => d.trim()).filter(Boolean), auto_open_delay: autoOpenDelay.trim() !== "" ? Number(autoOpenDelay) : null, persist_conversation: persistConversation, custom_css: customCss.trim() || null });
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="flex gap-6">
      <div className="flex-1">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Widget Customization
        </h1>

        <Card>
          <CardContent className="pt-6 pb-6 space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Primary Color
              </label>
              <div className="flex items-center gap-3">
                <div className="flex gap-2 flex-wrap">
                  {colorPresets.map((color) => (
                    <button
                      key={color}
                      onClick={() =>
                        setConfig({ ...config, primary_color: color })
                      }
                      className="h-8 w-8 rounded-full border-2 transition-all duration-200"
                      style={{
                        backgroundColor: color,
                        borderColor:
                          config.primary_color === color
                            ? color
                            : "transparent",
                        boxShadow:
                          config.primary_color === color
                            ? `0 0 0 2px white, 0 0 0 4px ${color}`
                            : "none",
                      }}
                    />
                  ))}
                </div>
                <input
                  type="color"
                  value={config.primary_color}
                  onChange={(e) =>
                    setConfig({ ...config, primary_color: e.target.value })
                  }
                  className="h-8 w-8 rounded cursor-pointer border-0"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Position
              </label>
              <div className="flex gap-2">
                {(["bottom-right", "bottom-left"] as const).map((pos) => (
                  <button
                    key={pos}
                    onClick={() => setConfig({ ...config, position: pos })}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      config.position === pos
                        ? "bg-primary-100 text-primary-700 ring-1 ring-primary-300"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {pos === "bottom-right" ? "Bottom Right" : "Bottom Left"}
                  </button>
                ))}
              </div>
            </div>

            <Input
              label="Welcome Message"
              value={config.welcome_message}
              onChange={(e) =>
                setConfig({ ...config, welcome_message: e.target.value })
              }
            />

            <Input
              label="Launcher Button Text"
              value={config.launcher_text}
              onChange={(e) =>
                setConfig({ ...config, launcher_text: e.target.value })
              }
            />

            <Input
              label="Avatar URL"
              value={config.avatar_url || ""}
              onChange={(e) =>
                setConfig({ ...config, avatar_url: e.target.value })
              }
              placeholder="https://example.com/avatar.png"
            />

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Quick Reply Chips</label>
              <p className="text-xs text-gray-500">Suggested replies shown after bot messages (max 8)</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chipInput}
                  onChange={(e) => setChipInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addChip(); } }}
                  placeholder="Type a chip label and press Enter"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <button onClick={addChip} className="px-3 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">Add</button>
              </div>
              {quickReplies.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {quickReplies.map((chip) => (
                    <span key={chip} className="flex items-center gap-1 bg-gray-100 rounded-full px-3 py-1 text-sm text-gray-700">
                      {chip}
                      <button onClick={() => setQuickReplies(quickReplies.filter((c) => c !== chip))} className="text-gray-400 hover:text-red-500 ml-1">×</button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t border-gray-100 pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Auto-open Delay (seconds)</label>
              <p className="text-xs text-gray-500 mb-2">Automatically open the chat window after this many seconds. Leave empty to disable.</p>
              <input
                type="number"
                min={0}
                value={autoOpenDelay}
                onChange={(e) => setAutoOpenDelay(e.target.value)}
                placeholder="e.g. 5"
                className="w-32 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center justify-between mb-1">
                <div>
                  <label className="text-sm font-medium text-gray-900">Persist conversation across sessions</label>
                  <p className="text-xs text-gray-500 mt-0.5">Resume the previous conversation when a visitor returns to the page</p>
                </div>
                <input
                  type="checkbox"
                  checked={persistConversation}
                  onChange={(e) => setPersistConversation(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600"
                />
              </div>
            </div>

            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-gray-900">Lead Capture Form</label>
                <input
                  type="checkbox"
                  checked={leadCaptureEnabled}
                  onChange={(e) => setLeadCaptureEnabled(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600"
                />
              </div>
              <p className="text-xs text-gray-500 mb-2">Show a form before the first message to capture visitor details</p>
              {leadCaptureEnabled && (
                <div className="flex gap-4">
                  {["name", "email", "phone"].map((field) => (
                    <label key={field} className="flex items-center gap-1 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={leadCaptureFields.includes(field)}
                        onChange={(e) => {
                          setLeadCaptureFields(
                            e.target.checked
                              ? [...leadCaptureFields, field]
                              : leadCaptureFields.filter((f) => f !== field)
                          );
                        }}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      {field.charAt(0).toUpperCase() + field.slice(1)}
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t border-gray-100 pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Allowed Domains</label>
              <p className="text-xs text-gray-500 mb-2">Comma-separated list of domains that can embed this widget. Leave empty to allow all.</p>
              <input
                type="text"
                value={allowedDomains}
                onChange={(e) => setAllowedDomains(e.target.value)}
                placeholder="example.com, app.example.com"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            {/* GDPR Consent */}
            <div className="space-y-3 pt-4 border-t border-gray-100">
              <h4 className="text-sm font-medium text-gray-700">Privacy & Consent</h4>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.gdpr_consent_enabled ?? false}
                  onChange={(e) =>
                    setConfig((prev) => ({ ...prev, gdpr_consent_enabled: e.target.checked }))
                  }
                  className="h-4 w-4 rounded border-gray-300 text-primary-600"
                />
                <span className="text-sm text-gray-700">Require GDPR consent before chat starts</span>
              </label>
              {config.gdpr_consent_enabled && (
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Consent message</label>
                  <textarea
                    rows={3}
                    value={config.gdpr_consent_text ?? ""}
                    onChange={(e) =>
                      setConfig((prev) => ({ ...prev, gdpr_consent_text: e.target.value }))
                    }
                    className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              )}
            </div>

            <div className="border-t border-gray-100 pt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Custom CSS</label>
              <p className="text-xs text-gray-500 mb-2">Inject custom styles into the widget&apos;s shadow DOM. These rules override the default styles.</p>
              <textarea
                rows={6}
                value={customCss}
                onChange={(e) => setCustomCss(e.target.value)}
                placeholder={`/* Override widget styles */\n.pulse-widget { ... }`}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="pt-2">
              <Button onClick={handleSave} loading={saving}>
                Save Configuration
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="w-96">
        <h2 className="text-sm font-medium text-gray-500 mb-4">
          Live Preview
        </h2>
        <div className="relative rounded-lg border border-gray-200 bg-gray-100 h-[500px] overflow-hidden">
          {previewOpen && (
            <div
              className={`absolute bottom-16 ${config.position === "bottom-right" ? "right-4" : "left-4"} w-80 rounded-xl shadow-2xl overflow-hidden`}
            >
              <div
                className="px-5 py-4 text-white"
                style={{ backgroundColor: config.primary_color }}
              >
                <div className="flex items-center gap-3">
                  {config.avatar_url ? (
                    <img
                      src={config.avatar_url}
                      alt="Avatar"
                      className="h-8 w-8 rounded-full object-cover"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-white/20 flex items-center justify-center">
                      <MessageCircle className="h-4 w-4" />
                    </div>
                  )}
                  <span className="font-medium text-sm">
                    {config.display_name || "Chat"}
                  </span>
                </div>
              </div>
              <div className="bg-white p-4 h-48 flex items-end">
                <div className="bg-gray-100 rounded-lg px-3 py-2 text-sm text-gray-700 max-w-[80%]">
                  {config.welcome_message}
                </div>
              </div>
              <div className="bg-white border-t border-gray-100 px-4 py-3">
                <div className="rounded-full border border-gray-200 px-4 py-2 text-sm text-gray-400">
                  Type a message...
                </div>
              </div>
            </div>
          )}

          <button
            onClick={() => setPreviewOpen(!previewOpen)}
            className={`absolute bottom-4 ${config.position === "bottom-right" ? "right-4" : "left-4"} flex items-center gap-2 rounded-full px-5 py-3 text-white text-sm font-medium shadow-lg transition-all duration-200 hover:scale-105`}
            style={{ backgroundColor: config.primary_color }}
          >
            <MessageCircle className="h-5 w-5" />
            {config.launcher_text}
          </button>
        </div>
      </div>
    </div>
  );
}
