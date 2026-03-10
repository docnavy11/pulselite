import { streamChat } from "./api";
import { WidgetConfig } from "./config";
import { createChatWindow } from "./ui/chat-window";
import { createLauncher } from "./ui/launcher";
import { createMessage, FeedbackContext } from "./ui/message";
import { createStreamingDots } from "./ui/streaming";
import { getStyles } from "./ui/styles";
import { generateId, renderMarkdownLite, renderMarkdownWithSources, CitationSource } from "./utils";

const SESSION_KEY_PREFIX = "pulse_session_";
const CONV_KEY_PREFIX = "pulse_conv_";

export class Widget {
  private config: WidgetConfig;
  private shadowRoot: ShadowRoot;
  private isOpen = false;
  private isStreaming = false;
  private sessionId: string;
  private conversationId: string | null = null;
  private launcher!: ReturnType<typeof createLauncher>;
  private chatWindow!: ReturnType<typeof createChatWindow>;
  private hasShownWelcome = false;
  private leadFormSubmitted = false;
  private leadFormVisible = false;
  private consentGiven = false;

  constructor(config: WidgetConfig) {
    this.config = config;
    this.sessionId = this.getOrCreateSession();
    this.conversationId = this.config.persistConversation ? this.getStoredConversationId() : null;
    this.consentGiven = this.getStoredConsent();

    const host = document.createElement("div");
    host.id = "pulse-widget-host";
    document.body.appendChild(host);
    this.shadowRoot = host.attachShadow({ mode: "closed" });

    this.render();

    if (this.config.autoOpenDelay != null && this.config.autoOpenDelay >= 0) {
      setTimeout(() => {
        if (!this.isOpen) {
          this.toggle();
        }
      }, this.config.autoOpenDelay * 1000);
    }
  }

  private getOrCreateSession(): string {
    const key = SESSION_KEY_PREFIX + this.config.chatbotId;
    let id = localStorage.getItem(key);
    if (!id) {
      id = generateId();
      localStorage.setItem(key, id);
    }
    return id;
  }

  private getStoredConversationId(): string | null {
    const key = CONV_KEY_PREFIX + this.config.chatbotId;
    return localStorage.getItem(key);
  }

  private storeConversationId(id: string): void {
    const key = CONV_KEY_PREFIX + this.config.chatbotId;
    localStorage.setItem(key, id);
  }

  private getStoredConsent(): boolean {
    const key = "pulse_consent_" + this.config.chatbotId;
    return localStorage.getItem(key) === "1";
  }

  private storeConsent(): void {
    const key = "pulse_consent_" + this.config.chatbotId;
    localStorage.setItem(key, "1");
  }

  private render(): void {
    const style = document.createElement("style");
    style.textContent = getStyles(
      this.config.primaryColor,
      this.config.backgroundColor,
      this.config.textColor
    );
    this.shadowRoot.appendChild(style);

    if (this.config.customCss) {
      const customStyle = document.createElement("style");
      customStyle.textContent = this.config.customCss;
      this.shadowRoot.appendChild(customStyle);
    }

    const container = document.createElement("div");
    container.className = `pulse-container ${this.config.position}`;

    this.chatWindow = createChatWindow(
      this.config.displayName,
      this.config.avatarUrl,
      this.config.placeholder,
      this.config.poweredBy,
      () => this.toggle(),
      (message) => this.sendMessage(message)
    );

    this.launcher = createLauncher(() => this.toggle());

    container.appendChild(this.chatWindow.element);
    container.appendChild(this.launcher.element);
    this.shadowRoot.appendChild(container);

    if (!this.conversationId) {
      this.launcher.showUnread(true);
    }
  }

  private toggle(): void {
    this.isOpen = !this.isOpen;
    this.launcher.setOpen(this.isOpen);
    this.chatWindow.setOpen(this.isOpen);

    if (this.isOpen) {
      this.launcher.showUnread(false);

      // GDPR gate — show consent banner if not yet given
      if (this.config.gdprConsentEnabled && !this.consentGiven) {
        this.showConsentBanner();
        return;
      }

      if (!this.hasShownWelcome) {
        this.showWelcomeMessage();
        this.hasShownWelcome = true;
      }
      if (this.config.leadCaptureEnabled && !this.leadFormSubmitted) {
        this.showLeadForm();
        return;
      }
      setTimeout(() => this.chatWindow.focusInput(), 300);
    }
  }

  private showWelcomeMessage(): void {
    if (this.config.welcomeMessage) {
      const msg = createMessage(
        this.config.welcomeMessage,
        "bot",
        this.config.avatarUrl
      );
      this.chatWindow.messagesContainer.appendChild(msg.element);
    }
  }

  private async sendMessage(text: string): Promise<void> {
    if (this.isStreaming) return;

    const userMsg = createMessage(text, "user");
    this.chatWindow.messagesContainer.appendChild(userMsg.element);
    this.scrollToBottom();

    this.isStreaming = true;
    this.chatWindow.setInputDisabled(true);

    const dots = createStreamingDots();
    const botMsgContainer = createMessage("", "bot", this.config.avatarUrl);
    botMsgContainer.element
      .querySelector(".pulse-msg-bubble")
      ?.appendChild(dots);
    this.chatWindow.messagesContainer.appendChild(botMsgContainer.element);
    this.scrollToBottom();

    let fullResponse = "";

    await streamChat(
      this.config.apiUrl,
      this.config.chatbotId,
      this.sessionId,
      text,
      this.conversationId,
      {
        onToken: (token: string) => {
          if (dots.parentNode) {
            dots.remove();
          }
          fullResponse += token;
          botMsgContainer.updateContent(renderMarkdownLite(fullResponse));
          this.scrollToBottom();
        },
        onDone: (data) => {
          if (dots.parentNode) {
            dots.remove();
          }
          if (data.conversationId) {
            this.conversationId = data.conversationId;
            if (this.config.persistConversation) {
              this.storeConversationId(data.conversationId);
            }
          }
          if (fullResponse) {
            const sources = (data.sources ?? []) as CitationSource[];
            const rendered = sources.length > 0
              ? renderMarkdownWithSources(fullResponse, sources)
              : renderMarkdownLite(fullResponse);
            botMsgContainer.updateContent(rendered);
          }
          if (data.messageId && data.conversationId && this.config.workspaceId) {
            const feedbackCtx: FeedbackContext = {
              apiUrl: this.config.apiUrl,
              workspaceId: this.config.workspaceId,
              conversationId: data.conversationId,
              messageId: data.messageId,
            };
            botMsgContainer.setFeedbackContext(feedbackCtx);
          }
          this.isStreaming = false;
          if (!this.leadFormVisible) {
            this.chatWindow.setInputDisabled(false);
            this.chatWindow.focusInput();
          }
          this.scrollToBottom();

          // Render quick reply chips
          const replies = this.config.quickReplies || [];
          if (replies.length > 0) {
            this.renderQuickReplies(replies);
          }
        },
        onAction: (actionData: { type: string; name: string; fields?: string[]; label?: string; url?: string }) => {
          if (actionData.type === "collect_lead") {
            this.showLeadForm(actionData.fields);
          } else if (actionData.type === "custom_button") {
            this.showCustomButton(actionData.label as string, actionData.url as string);
          } else if (actionData.type === "calendly" || actionData.type === "calcom") {
            this.showCustomButton(actionData.label as string, actionData.url as string);
          }
          // webhook and slack_message actions are silent from widget perspective
        },
        onError: (_error: string) => {
          if (dots.parentNode) {
            dots.remove();
          }
          botMsgContainer.updateContent(
            `<em style="color:#ef4444">Sorry, something went wrong. Please try again.</em>`
          );
          this.isStreaming = false;
          this.chatWindow.setInputDisabled(false);
          this.scrollToBottom();
        },
      }
    );
  }

  private showCustomButton(label: string, url: string): void {
    if (!url) return;
    const btn = document.createElement("a");
    btn.href = url;
    btn.target = "_blank";
    btn.rel = "noopener noreferrer";
    btn.className = "pulse-action-btn";
    btn.textContent = label || "Learn more";
    this.chatWindow.messagesContainer.appendChild(btn);
    this.scrollToBottom();
  }

  private showLeadForm(actionFields?: string[]): void {
    this.leadFormVisible = true;
    this.chatWindow.setInputDisabled(true);

    const form = document.createElement("div");
    form.className = "pulse-lead-form";

    const fields = actionFields ?? this.config.leadCaptureFields;
    const inputs: Record<string, HTMLInputElement> = {};

    fields.forEach((field) => {
      const label = document.createElement("label");
      label.className = "pulse-lead-label";
      label.textContent = field.charAt(0).toUpperCase() + field.slice(1);
      const input = document.createElement("input");
      input.className = "pulse-lead-input";
      input.type = field === "email" ? "email" : "text";
      input.placeholder = field.charAt(0).toUpperCase() + field.slice(1);
      inputs[field] = input;
      form.appendChild(label);
      form.appendChild(input);
    });

    const btn = document.createElement("button");
    btn.className = "pulse-lead-btn";
    btn.textContent = "Start Chat";
    btn.onclick = async () => {
      const data: Record<string, string> = {};
      fields.forEach((f) => { data[f] = inputs[f]?.value || ""; });

      await fetch(`${this.config.apiUrl}/api/v1/public/chat/lead`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chatbot_id: this.config.chatbotId,
          session_id: this.sessionId,
          ...data,
        }),
      }).catch(() => {});

      form.remove();
      this.leadFormSubmitted = true;
      this.leadFormVisible = false;
      this.chatWindow.setInputDisabled(false);
      setTimeout(() => this.chatWindow.focusInput(), 100);
    };

    form.appendChild(btn);
    this.chatWindow.messagesContainer.appendChild(form);
    this.scrollToBottom();
  }

  private renderQuickReplies(replies: string[]): void {
    // Remove any existing chip row
    const existing = this.chatWindow.messagesContainer.querySelector(".pulse-chips");
    if (existing) existing.remove();

    const row = document.createElement("div");
    row.className = "pulse-chips";

    replies.forEach((text) => {
      const chip = document.createElement("button");
      chip.className = "pulse-chip";
      chip.textContent = text;
      chip.onclick = () => {
        row.remove();
        this.sendMessage(text);
      };
      row.appendChild(chip);
    });

    this.chatWindow.messagesContainer.appendChild(row);
    this.scrollToBottom();
  }

  private showConsentBanner(): void {
    // Prevent duplicate banners if widget is toggled while banner is visible
    if (this.chatWindow.element.querySelector(".pulse-consent-banner")) return;
    this.chatWindow.setInputDisabled(true);

    const banner = document.createElement("div");
    banner.className = "pulse-consent-banner";

    const text = document.createElement("p");
    text.textContent = this.config.gdprConsentText;
    banner.appendChild(text);

    const acceptBtn = document.createElement("button");
    acceptBtn.className = "pulse-consent-accept";
    acceptBtn.textContent = "Accept & Continue";
    acceptBtn.onclick = () => {
      this.consentGiven = true;
      this.storeConsent();
      banner.remove();
      this.chatWindow.setInputDisabled(false);
      if (!this.hasShownWelcome) {
        this.showWelcomeMessage();
        this.hasShownWelcome = true;
      }
      if (this.config.leadCaptureEnabled && !this.leadFormSubmitted) {
        this.showLeadForm();
        return;
      }
      setTimeout(() => this.chatWindow.focusInput(), 100);
    };
    banner.appendChild(acceptBtn);

    const declineBtn = document.createElement("button");
    declineBtn.className = "pulse-consent-decline";
    declineBtn.textContent = "No thanks";
    declineBtn.onclick = () => {
      this.isOpen = false;
      this.launcher.setOpen(false);
      this.chatWindow.setOpen(false);
      banner.remove();
      this.chatWindow.setInputDisabled(false);
    };
    banner.appendChild(declineBtn);

    this.chatWindow.element.appendChild(banner);
  }

  private scrollToBottom(): void {
    const container = this.chatWindow.messagesContainer;
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }

  destroy(): void {
    const host = document.getElementById("pulse-widget-host");
    if (host) host.remove();
  }
}
