import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import { Input } from "@/components/ui/Input";
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

const DEFAULT_CONFIG: WidgetConfig = {
  primary_color: "#4f46e5",
  position: "bottom-right",
  welcome_message: "Hi! How can I help you today?",
  launcher_text: "Chat with us",
  avatar_url: "",
};

export default function CustomizePage() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [config, setConfig] = useState<WidgetConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewMobile, setPreviewMobile] = useState(false);

  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [chipInput, setChipInput] = useState("");
  const [leadCaptureEnabled, setLeadCaptureEnabled] = useState(false);
  const [leadCaptureFields, setLeadCaptureFields] = useState<string[]>(["name", "email"]);
  const [allowedDomains, setAllowedDomains] = useState("");
  const [autoOpenDelay, setAutoOpenDelay] = useState<string>("");
  const [persistConversation, setPersistConversation] = useState(false);
  const [customCss, setCustomCss] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Store initial values for reset
  const initialState = useRef<{
    config: WidgetConfig;
    quickReplies: string[];
    leadCaptureEnabled: boolean;
    leadCaptureFields: string[];
    allowedDomains: string;
    autoOpenDelay: string;
    persistConversation: boolean;
    customCss: string;
  } | null>(null);

  useEffect(() => {
    if (!workspace) return;
    getWidgetConfig(workspace.id, chatbotId)
      .then((cfg) => {
        setConfig(cfg);
        const qr = cfg.quick_replies || [];
        const lce = cfg.lead_capture_enabled ?? false;
        const lcf = cfg.lead_capture_fields ?? ["name", "email"];
        const ad = (cfg.allowed_domains ?? []).join(", ");
        const aod = cfg.auto_open_delay != null ? String(cfg.auto_open_delay) : "";
        const pc = cfg.persist_conversation ?? false;
        const css = cfg.custom_css ?? "";

        setQuickReplies(qr);
        setLeadCaptureEnabled(lce);
        setLeadCaptureFields(lcf);
        setAllowedDomains(ad);
        setAutoOpenDelay(aod);
        setPersistConversation(pc);
        setCustomCss(css);

        initialState.current = {
          config: cfg,
          quickReplies: qr,
          leadCaptureEnabled: lce,
          leadCaptureFields: lcf,
          allowedDomains: ad,
          autoOpenDelay: aod,
          persistConversation: pc,
          customCss: css,
        };
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  function handleReset() {
    if (!initialState.current) return;
    const s = initialState.current;
    setConfig(s.config);
    setQuickReplies(s.quickReplies);
    setLeadCaptureEnabled(s.leadCaptureEnabled);
    setLeadCaptureFields(s.leadCaptureFields);
    setAllowedDomains(s.allowedDomains);
    setAutoOpenDelay(s.autoOpenDelay);
    setPersistConversation(s.persistConversation);
    setCustomCss(s.customCss);
  }

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
      await updateWidgetConfig(workspace.id, chatbotId, {
        ...config,
        quick_replies: quickReplies,
        lead_capture_enabled: leadCaptureEnabled,
        lead_capture_fields: leadCaptureFields,
        allowed_domains: allowedDomains.split(",").map((d) => d.trim()).filter(Boolean),
        auto_open_delay: autoOpenDelay.trim() !== "" ? Number(autoOpenDelay) : null,
        persist_conversation: persistConversation,
        custom_css: customCss.trim() || null,
      });
      // Update initial state so reset reflects saved values
      initialState.current = {
        config,
        quickReplies,
        leadCaptureEnabled,
        leadCaptureFields,
        allowedDomains,
        autoOpenDelay,
        persistConversation,
        customCss,
      };
    } catch {
      // handle error
    } finally {
      setSaving(false);
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
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 bg-white border-b border-[#f0ebe3]">
        <h1 className="text-[15px] font-bold text-gray-900">Widget Appearance</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="px-3 py-1.5 text-[12px] font-medium text-gray-500 hover:text-gray-700 border border-[#f0ebe3] rounded-lg transition-colors"
          >
            Reset to defaults
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 text-[12px] font-semibold bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex gap-6 px-6 py-5 flex-1 overflow-auto">
        {/* Form column */}
        <div className="flex-1 min-w-0 space-y-4">

          {/* Identity */}
          <div className="bg-white border border-[#f0ebe3] rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[#faf8f5]">
              <h2 className="text-[12px] font-semibold text-gray-700">Identity</h2>
              <p className="text-[11px] text-gray-400">Bot name, brand colour, welcome message</p>
            </div>
            <div className="px-5 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Brand Color
                </label>
                <div className="flex items-center gap-3">
                  <div className="flex gap-2 flex-wrap">
                    {colorPresets.map((color) => (
                      <button
                        key={color}
                        onClick={() => setConfig({ ...config, primary_color: color })}
                        className="h-8 w-8 rounded-full border-2 transition-all duration-200"
                        style={{
                          backgroundColor: color,
                          borderColor: config.primary_color === color ? color : "transparent",
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
                    onChange={(e) => setConfig({ ...config, primary_color: e.target.value })}
                    className="h-8 w-8 rounded cursor-pointer border-0"
                  />
                </div>
              </div>

              <Input
                label="Bot Name / Display Name"
                value={config.display_name || ""}
                onChange={(e) => setConfig({ ...config, display_name: e.target.value })}
                placeholder="e.g. Support Bot"
              />

              <Input
                label="Welcome Message"
                value={config.welcome_message}
                onChange={(e) => setConfig({ ...config, welcome_message: e.target.value })}
              />

              <Input
                label="Launcher Button Text"
                value={config.launcher_text}
                onChange={(e) => setConfig({ ...config, launcher_text: e.target.value })}
              />

              <Input
                label="Avatar URL"
                value={config.avatar_url || ""}
                onChange={(e) => setConfig({ ...config, avatar_url: e.target.value })}
                placeholder="https://example.com/avatar.png"
              />
            </div>
          </div>

          {/* Layout & Position */}
          <div className="bg-white border border-[#f0ebe3] rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[#faf8f5]">
              <h2 className="text-[12px] font-semibold text-gray-700">Layout &amp; Position</h2>
              <p className="text-[11px] text-gray-400">Where the widget appears on the page</p>
            </div>
            <div className="px-5 py-4 space-y-4">
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

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Auto-open Delay (seconds)
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Automatically open the chat window after this many seconds. Leave empty to disable.
                </p>
                <input
                  type="number"
                  min={0}
                  value={autoOpenDelay}
                  onChange={(e) => setAutoOpenDelay(e.target.value)}
                  placeholder="e.g. 5"
                  className="w-32 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          {/* Quick Replies */}
          <div className="bg-white border border-[#f0ebe3] rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[#faf8f5]">
              <h2 className="text-[12px] font-semibold text-gray-700">Quick Replies</h2>
              <p className="text-[11px] text-gray-400">Suggested questions shown to visitors (max 8)</p>
            </div>
            <div className="px-5 py-4 space-y-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chipInput}
                  onChange={(e) => setChipInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addChip();
                    }
                  }}
                  placeholder="Type a chip label and press Enter"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <button
                  onClick={addChip}
                  className="px-3 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Add
                </button>
              </div>
              {quickReplies.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {quickReplies.map((chip) => (
                    <span
                      key={chip}
                      className="flex items-center gap-1 bg-gray-100 rounded-full px-3 py-1 text-sm text-gray-700"
                    >
                      {chip}
                      <button
                        onClick={() => setQuickReplies(quickReplies.filter((c) => c !== chip))}
                        className="text-gray-400 hover:text-red-500 ml-1"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Behaviour */}
          <div className="bg-white border border-[#f0ebe3] rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[#faf8f5]">
              <h2 className="text-[12px] font-semibold text-gray-700">Behaviour</h2>
              <p className="text-[11px] text-gray-400">Lead capture, consent, and session settings</p>
            </div>
            <div className="px-5 py-4 space-y-4">
              {/* Persist conversation */}
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-900">
                    Persist conversation across sessions
                  </label>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Resume the previous conversation when a visitor returns to the page
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={persistConversation}
                  onChange={(e) => setPersistConversation(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-500"
                />
              </div>

              {/* Lead Capture */}
              <div className="border-t border-gray-100 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-gray-900">Lead Capture Form</label>
                  <input
                    type="checkbox"
                    checked={leadCaptureEnabled}
                    onChange={(e) => setLeadCaptureEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary-500"
                  />
                </div>
                <p className="text-xs text-gray-500 mb-2">
                  Show a form before the first message to capture visitor details
                </p>
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

              {/* GDPR Consent */}
              <div className="border-t border-gray-100 pt-4 space-y-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.gdpr_consent_enabled ?? false}
                    onChange={(e) =>
                      setConfig((prev) => ({ ...prev, gdpr_consent_enabled: e.target.checked }))
                    }
                    className="h-4 w-4 rounded border-gray-300 text-primary-500"
                  />
                  <span className="text-sm text-gray-700">
                    Require GDPR consent before chat starts
                  </span>
                </label>
                {config.gdpr_consent_enabled && (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Consent message
                    </label>
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

              {/* Allowed Domains */}
              <div className="border-t border-gray-100 pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Allowed Domains
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Comma-separated list of domains that can embed this widget. Leave empty to allow all.
                </p>
                <input
                  type="text"
                  value={allowedDomains}
                  onChange={(e) => setAllowedDomains(e.target.value)}
                  placeholder="example.com, app.example.com"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          {/* Advanced (collapsible) */}
          <div className="bg-white border border-[#f0ebe3] rounded-xl overflow-hidden mb-4">
            <button
              onClick={() => setShowAdvanced((s) => !s)}
              className="w-full flex items-center justify-between px-5 py-3 text-left"
            >
              <div>
                <h2 className="text-[12px] font-semibold text-gray-700">Advanced</h2>
                <p className="text-[11px] text-gray-400">Custom CSS overrides</p>
              </div>
              <span className="text-gray-400 text-[11px]">{showAdvanced ? "Hide" : "Show"}</span>
            </button>
            {showAdvanced && (
              <div className="px-5 py-4 border-t border-[#faf8f5]">
                <label className="block text-sm font-medium text-gray-700 mb-1">Custom CSS</label>
                <p className="text-xs text-gray-500 mb-2">
                  Inject custom styles into the widget&apos;s shadow DOM. These rules override the default styles.
                </p>
                <textarea
                  rows={6}
                  value={customCss}
                  onChange={(e) => setCustomCss(e.target.value)}
                  placeholder={`/* Override widget styles */\n.pulse-widget { ... }`}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            )}
          </div>

        </div>

        {/* Preview column */}
        <div className="w-72 flex-shrink-0">
          <div className="sticky top-16 bg-white border border-[#f0ebe3] rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#faf8f5]">
              <button
                onClick={() => setPreviewMobile(false)}
                className={`text-[11px] font-medium px-2 py-1 rounded ${
                  !previewMobile ? "bg-primary-50 text-primary-500" : "text-gray-400"
                }`}
              >
                Desktop
              </button>
              <button
                onClick={() => setPreviewMobile(true)}
                className={`text-[11px] font-medium px-2 py-1 rounded ${
                  previewMobile ? "bg-primary-50 text-primary-500" : "text-gray-400"
                }`}
              >
                Mobile
              </button>
            </div>
            <div className={`p-4 bg-[#faf8f5] ${previewMobile ? "max-w-[375px] mx-auto" : ""}`}>
              {/* Mock chat widget */}
              <div className="relative rounded-lg border border-gray-200 bg-gray-100 h-[380px] overflow-hidden">
                {/* Open chat panel */}
                <div
                  className={`absolute bottom-16 ${
                    config.position === "bottom-right" ? "right-3" : "left-3"
                  } w-56 rounded-xl shadow-2xl overflow-hidden`}
                >
                  <div
                    className="px-4 py-3 text-white"
                    style={{ backgroundColor: config.primary_color }}
                  >
                    <div className="flex items-center gap-2">
                      {config.avatar_url ? (
                        <img
                          src={config.avatar_url}
                          alt="Avatar"
                          className="h-6 w-6 rounded-full object-cover"
                        />
                      ) : (
                        <div className="h-6 w-6 rounded-full bg-white/20 flex items-center justify-center">
                          <MessageCircle className="h-3 w-3" />
                        </div>
                      )}
                      <span className="font-medium text-xs">
                        {config.display_name || "Chat"}
                      </span>
                    </div>
                  </div>
                  <div className="bg-white p-3 h-32 flex items-end">
                    <div className="bg-gray-100 rounded-lg px-2 py-1.5 text-xs text-gray-700 max-w-[85%]">
                      {config.welcome_message}
                    </div>
                  </div>
                  <div className="bg-white border-t border-gray-100 px-3 py-2">
                    <div className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-400">
                      Type a message...
                    </div>
                  </div>
                </div>

                {/* Launcher button */}
                <div
                  className={`absolute bottom-3 ${
                    config.position === "bottom-right" ? "right-3" : "left-3"
                  } flex items-center gap-1.5 rounded-full px-3 py-2 text-white text-xs font-medium shadow-lg`}
                  style={{ backgroundColor: config.primary_color }}
                >
                  <MessageCircle className="h-4 w-4" />
                  {config.launcher_text}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
