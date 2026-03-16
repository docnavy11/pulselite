import { useState, useRef, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Send, Plus, MessageCircle, X, Monitor, Layers } from "lucide-react";
import { clsx } from "clsx";
import { Badge } from "@/components/ui/Badge";
import { MarkdownMessage } from "@/components/ui/MarkdownMessage";
import { streamChat } from "@/lib/sse";
import { Message } from "@/lib/types";
import { getPublicWidgetConfig } from "@/lib/api-functions";

function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (confidence == null) return null;
  const variant =
    confidence > 0.75 ? "success" : confidence > 0.5 ? "warning" : "danger";
  return (
    <Badge variant={variant} className="text-[10px] ml-2">
      {Math.round(confidence * 100)}%
    </Badge>
  );
}

export default function TestChatPage() {
  const { id: chatbotId } = useParams() as { id: string };
  const [mode, setMode] = useState<"inline" | "bubble">("inline");
  const [bubbleOpen, setBubbleOpen] = useState(false);
  const [primaryColor, setPrimaryColor] = useState("#4f46e5");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getPublicWidgetConfig(chatbotId)
      .then((cfg) => { if (cfg?.primary_color) setPrimaryColor(cfg.primary_color); })
      .catch(() => {});
  }, [chatbotId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);

  async function handleSend() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");

    const userMsg: Message = {
      id: (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36)),
      conversation_id: conversationId || "",
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const botMsgId = (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
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
      for await (const event of streamChat(chatbotId, text, {
        conversationId,
      }, abortControllerRef.current.signal)) {
        if (event.type === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId ? { ...m, content: m.content + event.data } : m,
            ),
          );
        } else if (event.type === "done") {
          if (event.conversation_id) setConversationId(event.conversation_id);
          if (event.confidence != null) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === botMsgId ? { ...m, confidence: event.confidence } : m,
              ),
            );
          }
        } else if (event.type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? { ...m, content: `Error: ${event.data}` }
                : m,
            ),
          );
        }
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsgId
            ? { ...m, content: "Failed to get response" }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
    }
  }

  function handleNewConversation() {
    setMessages([]);
    setConversationId(undefined);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-18rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-gray-900">Test Chat</h1>
        <div className="flex items-center gap-2">
          {/* Mode toggle */}
          <div className="flex items-center rounded-lg border border-gray-200 p-0.5 bg-gray-50 text-sm">
            <button
              onClick={() => setMode("inline")}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all duration-200",
                mode === "inline"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              <Layers className="h-3.5 w-3.5" />
              Inline
            </button>
            <button
              onClick={() => { setMode("bubble"); setBubbleOpen(false); }}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-all duration-200",
                mode === "bubble"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              <Monitor className="h-3.5 w-3.5" />
              Chat Bubble
            </button>
          </div>

          {mode === "inline" && (
            <button
              onClick={handleNewConversation}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all duration-200"
            >
              <Plus className="h-4 w-4" />
              New conversation
            </button>
          )}
        </div>
      </div>

      {mode === "inline" ? (
        <>
          <div className="flex-1 overflow-auto rounded-lg border border-gray-200 bg-white p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Send a message to start testing
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
                    "max-w-[70%] rounded-lg px-4 py-2.5 text-sm",
                    msg.role === "user"
                      ? "bg-primary-500 text-white"
                      : "bg-gray-100 text-gray-900",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <MarkdownMessage content={msg.content} className="text-sm prose-sm" />
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                  {msg.role === "assistant" && streaming && msg === messages[messages.length - 1] && !msg.content && (
                    <span className="inline-flex gap-1 py-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
                    </span>
                  )}
                  {msg.role === "assistant" && msg.confidence != null && (
                    <div className="mt-1">
                      <ConfidenceBadge confidence={msg.confidence} />
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="mt-4 flex gap-2">
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
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200"
              disabled={streaming}
            />
            <button
              onClick={handleSend}
              disabled={streaming || !input.trim()}
              className="flex items-center justify-center rounded-lg bg-primary-500 px-4 py-2.5 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </>
      ) : (
        /* Chat Bubble preview */
        <div className="flex-1 relative rounded-lg overflow-hidden border border-gray-200">
          {/* Mock webpage background */}
          <div className="absolute inset-0 bg-gray-100">
            {/* Fake browser chrome */}
            <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-yellow-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
              </div>
              <div className="flex-1 bg-gray-100 rounded-md px-3 py-1 text-xs text-gray-400 mx-4">
                https://yourwebsite.com
              </div>
            </div>
            {/* Fake page content */}
            <div className="p-8 space-y-3 opacity-30 pointer-events-none select-none">
              <div className="h-6 w-48 bg-gray-400 rounded" />
              <div className="h-3 w-full bg-gray-300 rounded" />
              <div className="h-3 w-5/6 bg-gray-300 rounded" />
              <div className="h-3 w-4/6 bg-gray-300 rounded" />
              <div className="mt-6 h-3 w-full bg-gray-300 rounded" />
              <div className="h-3 w-3/4 bg-gray-300 rounded" />
              <div className="h-3 w-5/6 bg-gray-300 rounded" />
            </div>
          </div>

          {/* Chat panel iframe */}
          {bubbleOpen && (
            <div
              className="absolute bottom-20 right-6 rounded-2xl shadow-2xl overflow-hidden border border-gray-200"
              style={{ width: 380, height: 560 }}
            >
              <iframe
                src={`/chat/${chatbotId}`}
                className="w-full h-full"
                title="Chat preview"
              />
            </div>
          )}

          {/* Floating bubble button */}
          <button
            onClick={() => setBubbleOpen((o) => !o)}
            className="absolute bottom-6 right-6 flex items-center justify-center rounded-full shadow-lg transition-all duration-200 hover:scale-105 active:scale-95"
            style={{ backgroundColor: primaryColor, width: 56, height: 56 }}
            title={bubbleOpen ? "Close chat" : "Open chat"}
          >
            {bubbleOpen ? (
              <X className="h-6 w-6 text-white" />
            ) : (
              <MessageCircle className="h-6 w-6 text-white" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}
