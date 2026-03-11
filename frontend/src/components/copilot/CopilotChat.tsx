import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useCopilot } from "./CopilotProvider";
import { streamCopilotChat, CopilotMessage } from "./api";

const CHIPS: Record<string, string[]> = {
  dashboard:     ["Show metrics", "Show my chatbots", "Check credits"],
  chatbots:      ["Show my chatbots", "Create a chatbot", "Check credits"],
  chatbot:       ["Show conversations", "Update persona", "Show documents", "Crawl a new URL"],
  conversations: ["Show escalated conversations", "Show metrics", "Show my chatbots"],
  intelligence:  ["Show metrics", "Show my chatbots"],
  settings:      ["Check credits", "Show my chatbots", "Show metrics"],
  default:       ["Show my chatbots", "Show metrics", "Check credits"],
};

function getChips(context: unknown): string[] {
  const page = (context as Record<string, unknown>)?.page as string | undefined;
  return CHIPS[page ?? ""] ?? CHIPS.default;
}

const MIN_WIDTH = 220;
const MAX_WIDTH = 520;
const STORAGE_KEY = "copilot_width";

function getStoredWidth(): number {
  if (typeof window === "undefined") return 280;
  return parseInt(localStorage.getItem(STORAGE_KEY) ?? "280", 10) || 280;
}

export function CopilotChat() {
  const { context, close, setActivePanel } = useCopilot();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const navigate = useNavigate();
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [width, setWidth] = useState<number>(getStoredWidth);
  const dragStartX = useRef<number | null>(null);
  const dragStartWidth = useRef<number>(width);

  function onDragStart(e: React.MouseEvent) {
    e.preventDefault();
    dragStartX.current = e.clientX;
    dragStartWidth.current = width;

    function onMove(ev: MouseEvent) {
      if (dragStartX.current === null) return;
      const delta = dragStartX.current - ev.clientX;
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, dragStartWidth.current + delta));
      setWidth(next);
    }

    function onUp() {
      setWidth((w) => {
        localStorage.setItem(STORAGE_KEY, String(w));
        return w;
      });
      dragStartX.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);


  function handleClear() {
    abortRef.current?.abort();
    setMessages([]);
    setStreaming(false);
    setInput("");
  }

  async function handleSend(override?: string) {
    const text = (override ?? input).trim();
    if (!text || streaming || !workspace) return;

    const userMsg: CopilotMessage = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setStreaming(true);

    const assistantMsg: CopilotMessage = { role: "assistant", content: "" };
    setMessages([...nextMessages, assistantMsg]);

    abortRef.current = new AbortController();

    try {
      await streamCopilotChat(
        workspace.id,
        nextMessages,
        context as unknown as Record<string, unknown>,
        {
          onToken(token) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + token,
                };
              }
              return updated;
            });
          },
          onAction(tool, args) {
            if (tool === "render_panel") {
              setActivePanel({
                component: args.component as string,
                props: (args.props as Record<string, unknown>) ?? {},
              });
            } else if (tool === "close_panel") {
              setActivePanel(null);
            } else if (tool === "navigate") {
              const route = args.route as string;
              if (route.startsWith("/") && !route.startsWith("//")) {
                navigate(route);
              }
            } else if (tool === "patch_store") {
              // patch_store is a no-op for now — optimistic UI updates are deferred
              console.debug("[copilot] patch_store:", args);
            }
          },
          onDone() {},
          onError(msg) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === "assistant" && last.content === "") {
                updated[updated.length - 1] = {
                  ...last,
                  content: `Error: ${msg}`,
                };
              }
              return updated;
            });
          },
        },
        abortRef.current.signal
      );
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex flex-shrink-0 flex-col border-l border-[#e8e2d9] bg-white relative" style={{ width }}>
      {/* Drag handle */}
      <div
        onMouseDown={onDragStart}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary-200 transition-colors z-10"
        title="Drag to resize"
      />
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#f0ebe3] px-3 py-2.5">
        <span className="text-[13px] font-bold text-primary-500">✦ Copilot</span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-400">⌘J</span>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="text-gray-400 hover:text-gray-600 transition-colors text-[10px] leading-none"
              aria-label="Clear chat"
              title="Clear chat"
            >
              Clear
            </button>
          )}
          <button
            onClick={close}
            className="text-gray-400 hover:text-gray-600 transition-colors text-sm leading-none"
            aria-label="Close copilot"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col-reverse gap-2">
        {messages.length === 0 && (
          <p className="text-xs text-gray-400 text-center mb-4">
            Ask me anything about this workspace.
          </p>
        )}
        {[...messages].reverse().map((msg, i) => {
          const isLastStreaming = streaming && i === 0;
          return (
            <div
              key={i}
              className={`rounded-lg px-3 py-2 text-xs leading-relaxed max-w-[95%] whitespace-pre-wrap ${
                msg.role === "user"
                  ? "ml-auto bg-primary-500 text-white"
                  : "bg-[#faf8f5] text-gray-700"
              }`}
            >
              {msg.role === "user" ? (
                msg.content
              ) : msg.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="[&>p]:mb-0">{children}</li>,
                    code: ({ children, className }) =>
                      className ? (
                        <pre className="bg-gray-100 rounded p-2 text-[10px] overflow-auto my-1"><code>{children}</code></pre>
                      ) : (
                        <code className="bg-gray-100 rounded px-1 text-[10px]">{children}</code>
                      ),
                    a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="underline text-primary-500">{children}</a>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : isLastStreaming ? "▍" : ""}
            </div>
          );
        })}
      </div>

      {/* Chips */}
      <div className="flex flex-wrap gap-1.5 px-2.5 pt-2 pb-0">
        {getChips(context).map((chip) => (
          <button
            key={chip}
            onClick={() => handleSend(chip)}
            disabled={streaming}
            className="rounded-full border border-[#e8e2d9] bg-[#faf8f5] px-2.5 py-1 text-[10px] text-gray-500 hover:border-primary-300 hover:text-primary-500 hover:bg-primary-50 disabled:opacity-40 transition-colors"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="border-t border-[#f0ebe3] p-2.5 mt-2">
        <div className="flex gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything…"
            disabled={streaming}
            className="flex-1 rounded-lg border border-gray-200 bg-[#faf8f5] px-3 py-1.5 text-xs placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-400 disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || streaming}
            className="rounded-lg bg-primary-500 px-2.5 py-1.5 text-xs text-white hover:bg-primary-600 disabled:opacity-40 transition-colors"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
