import { DEFAULT_CONFIG, WidgetConfig } from "./config";
import { Widget } from "./widget";

let widgetInstance: Widget | null = null;

function detectApiUrl(): string {
  const scripts = Array.from(document.querySelectorAll("script[data-chatbot-id]"));
  for (const script of scripts) {
    const src = script.getAttribute("src");
    if (src) {
      try {
        const url = new URL(src);
        return url.origin;
      } catch {
        // Relative URL, use current origin
      }
    }
  }
  return window.location.origin;
}

async function fetchConfig(
  apiUrl: string,
  chatbotId: string
): Promise<Partial<WidgetConfig>> {
  try {
    const response = await fetch(
      `${apiUrl}/api/v1/widget/${chatbotId}/config`
    );
    if (!response.ok) return {};
    const data = await response.json();
    return {
      workspaceId: data.workspace_id || "",
      displayName: data.display_name || DEFAULT_CONFIG.displayName,
      avatarUrl: data.avatar_url || null,
      primaryColor: data.primary_color || DEFAULT_CONFIG.primaryColor,
      backgroundColor: data.background_color || DEFAULT_CONFIG.backgroundColor,
      textColor: data.text_color || DEFAULT_CONFIG.textColor,
      position: data.position || DEFAULT_CONFIG.position,
      welcomeMessage: data.welcome_message || DEFAULT_CONFIG.welcomeMessage,
      placeholder: data.placeholder || DEFAULT_CONFIG.placeholder,
      poweredBy: data.powered_by !== false && !data.white_label_enabled,
      quickReplies: data.quick_replies || [],
      leadCaptureEnabled: data.lead_capture_enabled || false,
      leadCaptureFields: data.lead_capture_fields || ["name", "email"],
      gdprConsentEnabled: data.gdpr_consent_enabled || false,
      gdprConsentText: data.gdpr_consent_text || "",
      autoOpenDelay: data.auto_open_delay != null ? data.auto_open_delay : null,
      persistConversation: data.persist_conversation ?? false,
      customCss: data.custom_css ?? undefined,
    };
  } catch {
    return {};
  }
}

async function initFromScript(): Promise<void> {
  const script = document.querySelector(
    "script[data-chatbot-id]"
  ) as HTMLScriptElement | null;
  if (!script) return;

  const chatbotId = script.getAttribute("data-chatbot-id");
  if (!chatbotId) return;

  const apiUrl =
    script.getAttribute("data-api-url") || detectApiUrl();

  const remoteConfig = await fetchConfig(apiUrl, chatbotId);

  const config: WidgetConfig = {
    ...DEFAULT_CONFIG,
    ...remoteConfig,
    chatbotId,
    apiUrl,
  };

  widgetInstance = new Widget(config);
}

function init(options: { chatbotId: string; apiUrl?: string } & Partial<WidgetConfig>): void {
  if (widgetInstance) {
    widgetInstance.destroy();
  }

  const apiUrl = options.apiUrl || detectApiUrl();

  fetchConfig(apiUrl, options.chatbotId).then((remoteConfig) => {
    const config: WidgetConfig = {
      ...DEFAULT_CONFIG,
      ...remoteConfig,
      ...options,
      apiUrl,
    };

    widgetInstance = new Widget(config);
  });
}

function destroy(): void {
  if (widgetInstance) {
    widgetInstance.destroy();
    widgetInstance = null;
  }
}

// Auto-init from script tag
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initFromScript);
} else {
  initFromScript();
}

// Export for programmatic use
export { init, destroy };
