import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { Conversation, Message } from "@/lib/types";
import {
  getConversations,
  getConversation,
  getMessages,
  updateConversationStatus,
} from "@/lib/api-functions";

type StatusFilter = "open" | "all" | "resolved" | "escalated";

interface ConversationDetail extends Conversation {
  messages: Message[];
}

function nameToColor(name: string): string {
  const colors = [
    "from-orange-400 to-rose-400",
    "from-blue-400 to-indigo-400",
    "from-green-400 to-teal-400",
    "from-purple-400 to-pink-400",
    "from-amber-400 to-orange-400",
  ];
  let hash = 0;
  for (const c of name) hash = c.charCodeAt(0) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const STATUS_DOT: Record<string, string> = {
  open: "bg-green-400",
  resolved: "bg-gray-300",
  escalated: "bg-red-400",
  pending: "bg-amber-400",
  closed: "bg-gray-300",
};

export default function ConversationsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const selectedId = searchParams.get("id");
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const { register } = useCopilot();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showMeta, setShowMeta] = useState(true);

  // Load conversation list
  useEffect(() => {
    if (!workspace?.id) return;
    setLoadingList(true);
    getConversations(workspace.id, {
      ...(statusFilter !== "all" ? { status: statusFilter } : {}),
    })
      .then((data) => {
        setConversations(data);
        register({ page: "conversations", data: { status_filter: statusFilter } });
      })
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, [workspace?.id, statusFilter]);

  // Load selected conversation detail + messages
  useEffect(() => {
    if (!selectedId || !workspace?.id) {
      setSelected(null);
      return;
    }
    setLoadingDetail(true);
    Promise.all([
      getConversation(workspace.id, selectedId),
      getMessages(workspace.id, selectedId),
    ])
      .then(([conv, msgs]) => {
        setSelected({ ...conv, messages: msgs });
      })
      .catch(() => setSelected(null))
      .finally(() => setLoadingDetail(false));
  }, [selectedId, workspace?.id]);

  const selectConversation = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("id", id);
      navigate(`/conversations?${params.toString()}`, { replace: true });
    },
    [navigate, searchParams],
  );

  const handleStatusChange = useCallback(
    async (newStatus: string) => {
      if (!selected || !workspace?.id) return;
      try {
        const updated = await updateConversationStatus(workspace.id, selected.id, newStatus);
        setSelected((prev) => (prev ? { ...prev, ...updated } : null));
        setConversations((prev) =>
          prev.map((c) => (c.id === updated.id ? { ...c, ...updated } : c)),
        );
      } catch {
        // ignore
      }
    },
    [selected, workspace?.id],
  );

  const filters: { label: string; value: StatusFilter }[] = [
    { label: "Open", value: "open" },
    { label: "All", value: "all" },
    { label: "Resolved", value: "resolved" },
    { label: "Escalated", value: "escalated" },
  ];

  return (
    <div className="flex flex-1 overflow-hidden bg-[#faf8f5]">
      {/* Left: conversation list */}
      <div className={clsx(
        "flex-col bg-white border-r border-[#f0ebe3]",
        "xl:w-[280px] xl:flex-shrink-0 xl:flex",
        selectedId ? "hidden xl:flex" : "flex w-full",
      )}>
        {/* Filter chips */}
        <div className="flex gap-1.5 px-3 py-2.5 border-b border-[#f0ebe3] overflow-x-auto">
          {filters.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={clsx(
                "px-2.5 py-1 rounded-full text-[11px] font-medium whitespace-nowrap transition-colors",
                statusFilter === f.value
                  ? "bg-primary-500 text-white"
                  : "bg-[#faf8f5] text-gray-500 hover:bg-[#f0ebe3]",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loadingList ? (
            <div className="space-y-0">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2.5 px-3 py-3 border-b border-[#faf8f5]"
                >
                  <div className="w-8 h-8 rounded-full bg-[#f5f0ea] animate-pulse flex-shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-2.5 bg-[#f5f0ea] rounded animate-pulse w-3/4" />
                    <div className="h-2 bg-[#f5f0ea] rounded animate-pulse w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-12 px-4 text-center">
              <div className="text-3xl mb-3 opacity-40">💬</div>
              <p className="text-[12px] text-gray-400">No conversations yet</p>
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === selectedId;
              const contactName =
                conv.contact_name ?? conv.contact_email?.split("@")[0] ?? "Anonymous";
              const colorClass = nameToColor(contactName);
              const initial = contactName[0]?.toUpperCase() ?? "?";
              const preview = conv.last_message_preview ?? "";
              const time = conv.updated_at ?? conv.created_at ?? "";
              const status = conv.status ?? "open";

              return (
                <button
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={clsx(
                    "w-full flex items-start gap-2.5 px-3 py-3 border-b border-[#faf8f5] text-left transition-all",
                    isActive
                      ? "bg-primary-50 border-l-2 border-l-primary-500 pl-2.5"
                      : "hover:bg-[#faf8f5]",
                  )}
                >
                  {/* Avatar */}
                  <div
                    className={`w-8 h-8 rounded-full bg-gradient-to-br ${colorClass} flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0 mt-0.5`}
                  >
                    {initial}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[12px] font-semibold text-gray-800 truncate">
                        {contactName}
                      </span>
                      <span className="text-[10px] text-gray-400 flex-shrink-0">
                        {time ? relativeTime(time) : ""}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-400 truncate mt-0.5">{preview}</p>
                  </div>
                  <div
                    className={`w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0 ${STATUS_DOT[status] ?? "bg-gray-300"}`}
                  />
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Right: detail panel */}
      <div className={clsx(
        "overflow-hidden",
        selectedId ? "flex flex-1" : "hidden xl:flex xl:flex-1",
      )}>
        {!selectedId ? (
          <div className="flex-1 flex items-center justify-center bg-[#faf8f5]">
            <div className="text-center">
              <div className="text-4xl mb-3 opacity-30">👈</div>
              <p className="text-[13px] text-gray-400">Select a conversation</p>
            </div>
          </div>
        ) : loadingDetail ? (
          <div className="flex-1 p-6 space-y-3">
            <div className="h-4 bg-[#f5f0ea] rounded animate-pulse w-48" />
            <div className="h-16 bg-[#f5f0ea] rounded animate-pulse" />
            <div className="h-16 bg-[#f5f0ea] rounded animate-pulse w-3/4 ml-auto" />
          </div>
        ) : selected ? (
          <>
            {/* Chat area */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Header */}
              <div className="flex items-center gap-3 px-5 py-3 border-b border-[#f0ebe3] bg-white">
                {/* Back button — mobile only */}
                <button
                  onClick={() => navigate("/conversations", { replace: true })}
                  className="xl:hidden flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-700 mr-1 flex-shrink-0"
                >
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M8 2L4 6l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Back
                </button>
                <div
                  className={`w-8 h-8 rounded-full bg-gradient-to-br ${nameToColor(selected.contact_name ?? selected.contact_email?.split("@")[0] ?? "?")} flex items-center justify-center text-white text-[11px] font-bold`}
                >
                  {(
                    (selected.contact_name ?? selected.contact_email ?? "?")[0] ?? "?"
                  ).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-gray-800">
                    {selected.contact_name ?? selected.contact_email ?? "Anonymous"}
                  </div>
                </div>
                {/* Inline status dropdown */}
                <select
                  value={selected.status ?? "open"}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="text-[11px] font-medium px-2.5 py-1 rounded-full border border-[#f0ebe3] bg-[#faf8f5] text-gray-600 cursor-pointer"
                >
                  <option value="open">Open</option>
                  <option value="pending">Pending</option>
                  <option value="resolved">Resolved</option>
                  <option value="escalated">Escalated</option>
                  <option value="closed">Closed</option>
                </select>
                <button
                  onClick={() => setShowMeta((s) => !s)}
                  className="hidden xl:inline text-[11px] text-gray-400 hover:text-gray-600"
                >
                  {showMeta ? "Hide info" : "Show info"}
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 bg-[#faf8f5]">
                {selected.messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-[12px] text-gray-400">No messages in this conversation</p>
                  </div>
                ) : (
                  selected.messages.map((msg) => {
                    const isBot = msg.role === "assistant";
                    return (
                      <div key={msg.id} className={`flex ${isBot ? "justify-start" : "justify-end"}`}>
                        <div
                          className={clsx(
                            "max-w-[70%] px-3.5 py-2.5 rounded-2xl text-[12px] leading-relaxed",
                            isBot
                              ? "bg-white border border-[#f0ebe3] text-gray-700 rounded-tl-sm"
                              : "bg-primary-500 text-white rounded-tr-sm",
                          )}
                        >
                          {msg.content}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Metadata sidebar */}
            {showMeta && (
              <div className="hidden xl:block w-[180px] flex-shrink-0 border-l border-[#f0ebe3] bg-white overflow-y-auto px-4 py-4 space-y-4">
                <div>
                  <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
                    Contact
                  </div>
                  <div className="text-[11px] text-gray-600">
                    {selected.contact_name ?? "Anonymous"}
                  </div>
                  {selected.contact_email && (
                    <div className="text-[10px] text-gray-400 mt-0.5 break-all">
                      {selected.contact_email}
                    </div>
                  )}
                </div>
                {selected.confidence != null && (
                  <div>
                    <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                      Confidence
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-[#f0ebe3] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary-500 rounded-full"
                          style={{ width: `${Math.round(selected.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500">
                        {Math.round(selected.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                )}
                {selected.outcome && (
                  <div>
                    <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
                      Outcome
                    </div>
                    <span className="text-[10px] text-gray-600">{selected.outcome}</span>
                  </div>
                )}
                {selected.status && (
                  <div>
                    <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
                      Status
                    </div>
                    <span
                      className={clsx(
                        "text-[10px] font-medium px-2 py-0.5 rounded-full",
                        selected.status === "open"
                          ? "bg-green-50 text-green-600"
                          : selected.status === "escalated"
                            ? "bg-red-50 text-red-500"
                            : selected.status === "pending"
                              ? "bg-amber-50 text-amber-600"
                              : "bg-gray-100 text-gray-500",
                      )}
                    >
                      {selected.status}
                    </span>
                  </div>
                )}
                <div>
                  <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
                    Created
                  </div>
                  <span className="text-[10px] text-gray-500">
                    {new Date(selected.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
