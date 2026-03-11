import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import { Send, MessageCircle } from "lucide-react";
import { clsx } from "clsx";
import { Spinner } from "@/components/ui/Spinner";
import { MarkdownMessage } from "@/components/ui/MarkdownMessage";
import { streamChat } from "@/lib/sse";
import { WidgetConfig, Message } from "@/lib/types";
import { getPublicWidgetConfig } from "@/lib/api-functions";

function getSessionId(chatbotId: string): string {
  if (typeof window === "undefined") return "";
  const key = `pulse_session_${chatbotId}`;
  let sid = localStorage.getItem(key);
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem(key, sid);
  }
  return sid;
}

function getPersistedConversationId(chatbotId: string): string | undefined {
  if (typeof window === "undefined") return undefined;
  return localStorage.getItem(`pulse_conv_${chatbotId}`) ?? undefined;
}

function setPersistedConversationId(chatbotId: string, id: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(`pulse_conv_${chatbotId}`, id);
}

export default function PublicChatPage() {
  const params = useParams();
  const chatbotId = params.chatbotId as string;
  const [config, setConfig] = useState<(WidgetConfig & { display_name?: string }) | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [conversationId, setConversationId] = useState<string | undefined>();
  // GDPR consent state
  const [gdprAccepted, setGdprAccepted] = useState(false);
  // Lead capture state
  const [leadSubmitted, setLeadSubmitted] = useState(false);
  const [leadFields, setLeadFields] = useState<Record<string, string>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionId = useRef(getSessionId(chatbotId));

  useEffect(() => {
    getPublicWidgetConfig(chatbotId)
      .then((cfg) => {
        setConfig(cfg);
        // Restore persisted conversation if enabled
        if (cfg?.persist_conversation) {
          const saved = getPersistedConversationId(chatbotId);
          if (saved) setConversationId(saved);
        }
        // If no GDPR required, mark as accepted
        if (!cfg?.gdpr_consent_enabled) setGdprAccepted(true);
        // If no lead capture required, mark as submitted
        if (!cfg?.lead_capture_enabled) setLeadSubmitted(true);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [chatbotId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || streaming) return;
    setInput("");

    const userMsg: Message = {
      id: crypto.randomUUID(),
      conversation_id: conversationId || "",
      role: "user",
      content: msg,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const botMsgId = crypto.randomUUID();
    const botMsg: Message = {
      id: botMsgId,
      conversation_id: conversationId || "",
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, botMsg]);

    setStreaming(true);
    abortControllerRef.current = new AbortController();
    try {
      for await (const event of streamChat(chatbotId, msg, {
        conversationId,
        sessionId: sessionId.current,
        isPublic: true,
      }, abortControllerRef.current.signal)) {
        if (event.type === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId ? { ...m, content: m.content + event.data } : m,
            ),
          );
        } else if (event.type === "done") {
          if (event.conversation_id) {
            setConversationId(event.conversation_id);
            if (config?.persist_conversation) {
              setPersistedConversationId(chatbotId, event.conversation_id);
            }
          }
        } else if (event.type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? { ...m, content: "Sorry, something went wrong." }
                : m,
            ),
          );
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsgId
            ? { ...m, content: "Failed to connect. Please try again." }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <Spinner className="h-8 w-8 text-gray-400" />
      </div>
    );
  }

  const primaryColor = config?.primary_color || "#4f46e5";
  const displayName = config?.display_name || "Chat";
  const chips = config?.quick_replies ?? [];

  // GDPR consent gate
  if (!gdprAccepted && config?.gdpr_consent_enabled) {
    return (
      <div className="flex flex-col h-screen bg-gray-50">
        <header
          className="flex items-center gap-3 px-6 py-4 text-white shadow-sm"
          style={{ backgroundColor: primaryColor }}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20">
            <MessageCircle className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold">{displayName}</h1>
            <p className="text-xs opacity-80">Powered by Pulse</p>
          </div>
        </header>
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-sm border border-gray-100 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">Before we start</h2>
            <p className="text-sm text-gray-600 leading-relaxed">
              {config.gdpr_consent_text || "By continuing, you agree to our Privacy Policy and consent to this chat being stored for support purposes."}
            </p>
            <button
              onClick={() => setGdprAccepted(true)}
              className="w-full rounded-lg py-2.5 text-sm font-medium text-white transition-all duration-200 hover:brightness-110"
              style={{ backgroundColor: primaryColor }}
            >
              I agree — Start chat
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Lead capture gate
  const leadFieldNames = config?.lead_capture_fields ?? ["name", "email"];
  if (!leadSubmitted && config?.lead_capture_enabled) {
    return (
      <div className="flex flex-col h-screen bg-gray-50">
        <header
          className="flex items-center gap-3 px-6 py-4 text-white shadow-sm"
          style={{ backgroundColor: primaryColor }}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20">
            <MessageCircle className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold">{displayName}</h1>
            <p className="text-xs opacity-80">Powered by Pulse</p>
          </div>
        </header>
        <div className="flex flex-1 items-center justify-center px-6">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-sm border border-gray-100 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">Tell us a little about yourself</h2>
            <div className="space-y-3">
              {leadFieldNames.map((field) => (
                <div key={field}>
                  <label className="block text-xs font-medium text-gray-700 mb-1 capitalize">{field}</label>
                  <input
                    type={field === "email" ? "email" : field === "phone" ? "tel" : "text"}
                    value={leadFields[field] ?? ""}
                    onChange={(e) => setLeadFields((prev) => ({ ...prev, [field]: e.target.value }))}
                    placeholder={field === "email" ? "you@example.com" : field === "phone" ? "+1 555 000 0000" : "Your name"}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:border-transparent"
                    style={{ "--tw-ring-color": primaryColor } as React.CSSProperties}
                  />
                </div>
              ))}
            </div>
            <button
              onClick={() => setLeadSubmitted(true)}
              disabled={leadFieldNames.some((f) => !(leadFields[f]?.trim()))}
              className="w-full rounded-lg py-2.5 text-sm font-medium text-white transition-all duration-200 hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: primaryColor }}
            >
              Start chat
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header
        className="flex items-center gap-3 px-6 py-4 text-white shadow-sm"
        style={{ backgroundColor: primaryColor }}
      >
        {config?.avatar_url ? (
          <img
            src={config.avatar_url}
            alt="Avatar"
            className="h-9 w-9 rounded-full object-cover"
          />
        ) : (
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20">
            <MessageCircle className="h-5 w-5" />
          </div>
        )}
        <div>
          <h1 className="text-base font-semibold">{displayName}</h1>
          <p className="text-xs opacity-80">Powered by Pulse</p>
        </div>
      </header>

      <div className="flex-1 overflow-auto px-4 py-6 space-y-4">
        {messages.length === 0 && config?.welcome_message && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg bg-white px-4 py-2.5 text-sm text-gray-900 shadow-sm border border-gray-100">
              {config.welcome_message}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={clsx(
              "flex",
              msg.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={clsx(
                "max-w-[80%] rounded-lg px-4 py-2.5 text-sm shadow-sm",
                msg.role === "user"
                  ? "text-white"
                  : "bg-white text-gray-900 border border-gray-100",
              )}
              style={
                msg.role === "user"
                  ? { backgroundColor: primaryColor }
                  : undefined
              }
            >
              {msg.role === "assistant" ? (
                <MarkdownMessage content={msg.content} className="text-sm" />
              ) : (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              )}
              {msg.role === "assistant" &&
                streaming &&
                msg === messages[messages.length - 1] &&
                !msg.content && (
                  <span className="inline-flex gap-1 py-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
                  </span>
                )}
            </div>
          </div>
        ))}

        {/* Quick reply chips — shown after last bot message finishes */}
        {!streaming &&
          messages.length > 0 &&
          messages[messages.length - 1].role === "assistant" &&
          chips.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {chips.map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleSend(chip)}
                  className="rounded-full border px-3 py-1.5 text-xs font-medium bg-white transition-all duration-200 hover:opacity-80"
                  style={{ borderColor: primaryColor, color: primaryColor }}
                >
                  {chip}
                </button>
              ))}
            </div>
          )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message..."
            className="flex-1 rounded-full border border-gray-300 px-5 py-2.5 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200"
            style={
              {
                "--tw-ring-color": primaryColor,
              } as React.CSSProperties
            }
            disabled={streaming}
          />
          <button
            onClick={() => handleSend()}
            disabled={streaming || !input.trim()}
            className="flex items-center justify-center rounded-full h-10 w-10 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 hover:brightness-110"
            style={{ backgroundColor: primaryColor }}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
