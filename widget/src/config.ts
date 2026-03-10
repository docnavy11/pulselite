export interface WidgetConfig {
  chatbotId: string;
  workspaceId: string;
  apiUrl: string;
  displayName: string;
  avatarUrl: string | null;
  primaryColor: string;
  backgroundColor: string;
  textColor: string;
  position: "bottom-right" | "bottom-left";
  welcomeMessage: string;
  placeholder: string;
  poweredBy: boolean;
  quickReplies: string[];
  leadCaptureEnabled: boolean;
  leadCaptureFields: string[];
  gdprConsentEnabled: boolean;
  gdprConsentText: string;
  autoOpenDelay: number | null;
  persistConversation?: boolean;
  customCss?: string;
}

export const DEFAULT_CONFIG: Omit<WidgetConfig, "chatbotId"> = {
  workspaceId: "",
  apiUrl: "",
  displayName: "Assistant",
  avatarUrl: null,
  primaryColor: "#6366f1",
  backgroundColor: "#ffffff",
  textColor: "#1f2937",
  position: "bottom-right",
  welcomeMessage: "Hi! How can I help you today?",
  placeholder: "Type a message...",
  poweredBy: true,
  quickReplies: [],
  leadCaptureEnabled: false,
  leadCaptureFields: ["name", "email"],
  gdprConsentEnabled: false,
  gdprConsentText: "",
  autoOpenDelay: null,
  persistConversation: false,
  customCss: undefined,
};
