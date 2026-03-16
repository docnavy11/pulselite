import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import { MessageSquare, ChevronLeft, Search, Info, X } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { MarkdownMessage } from "@/components/ui/MarkdownMessage";
import { Chatbot, Conversation, Message } from "@/lib/types";
import {
  getChatbots,
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
    "from-cyan-400 to-blue-400",
  ];
  let hash = 0;
  for (const c of name) hash = c.charCodeAt(0) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(dateStr).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const STATUS_STYLES: Record<string, { dot: string; bg: string; text: string }> = {
  open: { dot: "bg-green-400", bg: "bg-green-50", text: "text-green-700" },
  resolved: { dot: "bg-gray-300", bg: "bg-gray-50", text: "text-gray-500" },
  escalated: { dot: "bg-amber-400", bg: "bg-amber-50", text: "text-amber-600" },
  pending: { dot: "bg-amber-300", bg: "bg-amber-50", text: "text-amber-600" },
  closed: { dot: "bg-gray-300", bg: "bg-gray-50", text: "text-gray-400" },
};

const FILTERS: { label: string; value: StatusFilter }[] = [
  { label: "Open", value: "open" },
  { label: "All", value: "all" },
  { label: "Resolved", value: "resolved" },
  { label: "Escalated", value: "escalated" },
];

export default function ConversationsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const selectedId = searchParams.get("id");
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const { register } = useCopilot();

  const topicParam = searchParams.get("topic");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [chatbotFilter, setChatbotFilter] = useState<string>("all");
  const [timeFilter, setTimeFilter] = useState<string>("30d");
  const [searchQuery, setSearchQuery] = useState("");
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showMeta, setShowMeta] = useState(true);

  // Chatbot lookup map
  const chatbotMap = useMemo(
    () => new Map(chatbots.map((b) => [b.id, b])),
    [chatbots],
  );

  // Load chatbots
  useEffect(() => {
    if (!workspace?.id) return;
    getChatbots(workspace.id).then(setChatbots).catch(() => {});
  }, [workspace?.id]);

  // Compute date_from from time filter
  const dateFrom = useMemo(() => {
    if (timeFilter === "all") return undefined;
    const d = new Date();
    if (timeFilter === "today") d.setHours(0, 0, 0, 0);
    else if (timeFilter === "7d") d.setDate(d.getDate() - 7);
    else if (timeFilter === "30d") d.setDate(d.getDate() - 30);
    else if (timeFilter === "90d") d.setDate(d.getDate() - 90);
    return d.toISOString().split("T")[0];
  }, [timeFilter]);

  // Load conversation list
  useEffect(() => {
    if (!workspace?.id) return;
    setLoadingList(true);
    getConversations(workspace.id, {
      ...(statusFilter !== "all" ? { status: statusFilter } : {}),
      ...(chatbotFilter !== "all" ? { chatbot_id: chatbotFilter } : {}),
      ...(topicParam ? { topic: topicParam } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
    })
      .then((data) => {
        setConversations(data);
        register({ page: "conversations", data: { status_filter: statusFilter } });
      })
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, [workspace?.id, statusFilter, chatbotFilter, topicParam, dateFrom]); // eslint-disable-line react-hooks/exhaustive-deps

  // Filter: hide deleted-bot conversations + local search
  const visibleConversations = useMemo(() => {
    let filtered = chatbots.length > 0
      ? conversations.filter((c) => c.chatbot_id && chatbotMap.has(c.chatbot_id))
      : conversations;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          (c.contact_name ?? "").toLowerCase().includes(q) ||
          (c.contact_email ?? "").toLowerCase().includes(q) ||
          (c.last_message_preview ?? "").toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [conversations, chatbots.length, chatbotMap, searchQuery]);

  // Load selected conversation
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
      .then(([conv, msgs]) => setSelected({ ...conv, messages: msgs }))
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

  const deselectConversation = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("id");
    navigate(`/conversations?${params.toString()}`, { replace: true });
  }, [navigate, searchParams]);

  const handleStatusChange = useCallback(
    async (newStatus: string) => {
      if (!selected || !workspace?.id) return;
      try {
        const updated = await updateConversationStatus(workspace.id, selected.id, newStatus);
        setSelected((prev) => (prev ? { ...prev, ...updated } : null));
        setConversations((prev) =>
          prev.map((c) => (c.id === updated.id ? { ...c, ...updated } : c)),
        );
      } catch (err) {
        console.error("Failed to update conversation status:", err);
      }
    },
    [selected, workspace?.id],
  );

  return (
    <div className="flex flex-1 overflow-hidden bg-[#faf8f5]">
      {/* ── Left panel: conversation list ── */}
      <div
        className={clsx(
          "flex-col bg-white border-r border-[#f0ebe3]",
          "xl:w-[320px] xl:flex-shrink-0",
          selectedId ? "hidden xl:flex" : "flex w-full",
        )}
      >
        {/* Header */}
        <div className="px-4 pt-4 pb-3 space-y-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-8 py-2 text-xs rounded-lg border border-[#f0ebe3] bg-[#faf8f5] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-300 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Status filters */}
          <div className="flex gap-1">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={clsx(
                  "px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all",
                  statusFilter === f.value
                    ? "bg-gray-900 text-white shadow-sm"
                    : "text-gray-500 hover:bg-[#f0ebe3] hover:text-gray-700",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Bot filter */}
          {chatbots.length > 1 && (
            <select
              value={chatbotFilter}
              onChange={(e) => setChatbotFilter(e.target.value)}
              className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-[#f0ebe3] bg-[#faf8f5] text-gray-600 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-400/40"
            >
              <option value="all">All bots</option>
              {chatbots.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          )}

          {/* Time filter */}
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-[#f0ebe3] bg-[#faf8f5] text-gray-600 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-400/40"
          >
            <option value="today">Today</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="all">All time</option>
          </select>

          {/* Topic filter badge */}
          {topicParam && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-primary-50 border border-primary-200 text-primary-700">
              <span className="text-[11px] font-medium truncate">
                Topic: {topicParam}
              </span>
              <button
                onClick={() => navigate("/conversations", { replace: true })}
                className="shrink-0 hover:text-primary-900"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loadingList ? (
            <div className="px-3 py-2 space-y-1">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-3 rounded-lg">
                  <div className="w-9 h-9 rounded-full bg-[#f0ebe3] animate-pulse flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-[#f0ebe3] rounded-md animate-pulse w-2/3" />
                    <div className="h-2.5 bg-[#f5f0ea] rounded-md animate-pulse w-full" />
                  </div>
                </div>
              ))}
            </div>
          ) : visibleConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full py-16 px-6 text-center">
              <div className="w-12 h-12 rounded-full bg-[#f0ebe3] flex items-center justify-center mb-4">
                <MessageSquare className="h-5 w-5 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-500 mb-1">No conversations</p>
              <p className="text-xs text-gray-400">
                {searchQuery
                  ? "Try a different search term"
                  : "Conversations will appear here when visitors chat with your bots"}
              </p>
            </div>
          ) : (
            <div className="px-2 py-1">
              {visibleConversations.map((conv) => {
                const isActive = conv.id === selectedId;
                const contactName =
                  conv.contact_name ?? conv.contact_email?.split("@")[0] ?? "Anonymous";
                const bot = chatbotMap.get(conv.chatbot_id);
                const colorClass = nameToColor(contactName);
                const initial = contactName[0]?.toUpperCase() ?? "?";
                const preview = conv.last_message_preview ?? "";
                const time = conv.updated_at ?? conv.created_at ?? "";
                const status = conv.status ?? "open";
                const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.closed;

                return (
                  <button
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={clsx(
                      "w-full flex items-start gap-3 px-3 py-3 rounded-xl text-left transition-all mb-0.5",
                      isActive
                        ? "bg-primary-50 ring-1 ring-primary-200"
                        : "hover:bg-[#faf8f5]",
                    )}
                  >
                    {/* Avatar */}
                    <div
                      className={`w-9 h-9 rounded-full bg-gradient-to-br ${colorClass} flex items-center justify-center text-white text-xs font-bold flex-shrink-0 shadow-sm`}
                    >
                      {initial}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-semibold text-gray-800 truncate">
                          {contactName}
                        </span>
                        <span className="text-[10px] text-gray-400 flex-shrink-0 tabular-nums">
                          {time ? relativeTime(time) : ""}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 truncate mt-0.5 leading-relaxed">
                        {preview || "No messages yet"}
                      </p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span
                          className={clsx(
                            "inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md",
                            statusStyle.bg,
                            statusStyle.text,
                          )}
                        >
                          <span className={clsx("w-1.5 h-1.5 rounded-full", statusStyle.dot)} />
                          {status}
                        </span>
                        {bot && chatbots.length > 1 && (
                          <span className="text-[10px] text-gray-400 truncate">
                            {bot.name}
                          </span>
                        )}
                      </div>
                      {conv.topics && conv.topics.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {conv.topics.slice(0, 3).map((t) => (
                            <span
                              key={t}
                              className="text-[9px] font-medium px-1.5 py-0.5 rounded-md bg-primary-50 text-primary-600 border border-primary-100"
                            >
                              {t}
                            </span>
                          ))}
                          {conv.topics.length > 3 && (
                            <span className="text-[9px] text-gray-400">
                              +{conv.topics.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: detail ── */}
      <div
        className={clsx(
          "overflow-hidden",
          selectedId ? "flex flex-1" : "hidden xl:flex xl:flex-1",
        )}
      >
        {!selectedId ? (
          <div className="flex-1 flex flex-col items-center justify-center bg-[#faf8f5]">
            <div className="w-16 h-16 rounded-2xl bg-white border border-[#f0ebe3] flex items-center justify-center mb-5 shadow-sm">
              <MessageSquare className="h-7 w-7 text-gray-300" />
            </div>
            <p className="text-sm font-medium text-gray-500 mb-1">Select a conversation</p>
            <p className="text-xs text-gray-400">Choose from the list to view messages</p>
          </div>
        ) : loadingDetail ? (
          <div className="flex-1 flex flex-col bg-[#faf8f5] p-6">
            <div className="flex items-center gap-3 pb-4">
              <div className="w-9 h-9 rounded-full bg-[#f0ebe3] animate-pulse" />
              <div className="space-y-2 flex-1">
                <div className="h-3.5 bg-[#f0ebe3] rounded-md animate-pulse w-32" />
                <div className="h-2.5 bg-[#f5f0ea] rounded-md animate-pulse w-20" />
              </div>
            </div>
            <div className="flex-1 space-y-4 pt-4">
              <div className="flex justify-start"><div className="h-16 bg-white border border-[#f0ebe3] rounded-2xl animate-pulse w-64" /></div>
              <div className="flex justify-end"><div className="h-12 bg-primary-100 rounded-2xl animate-pulse w-48" /></div>
              <div className="flex justify-start"><div className="h-20 bg-white border border-[#f0ebe3] rounded-2xl animate-pulse w-72" /></div>
            </div>
          </div>
        ) : selected ? (
          <>
            {/* Chat area */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Header */}
              <div className="flex items-center gap-3 px-5 py-3 border-b border-[#f0ebe3] bg-white">
                <button
                  onClick={deselectConversation}
                  className="xl:hidden flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 mr-1 flex-shrink-0"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <div
                  className={`w-9 h-9 rounded-full bg-gradient-to-br ${nameToColor(
                    selected.contact_name ?? selected.contact_email?.split("@")[0] ?? "?",
                  )} flex items-center justify-center text-white text-xs font-bold shadow-sm`}
                >
                  {((selected.contact_name ?? selected.contact_email ?? "?")[0] ?? "?").toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-gray-800">
                    {selected.contact_name ?? selected.contact_email ?? "Anonymous"}
                  </div>
                  {chatbotMap.get(selected.chatbot_id) && (
                    <div className="text-[11px] text-gray-400">
                      {chatbotMap.get(selected.chatbot_id)!.name}
                    </div>
                  )}
                </div>
                <select
                  value={selected.status ?? "open"}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className={clsx(
                    "text-[11px] font-medium px-3 py-1.5 rounded-lg border cursor-pointer transition-colors",
                    "border-[#f0ebe3] bg-[#faf8f5] text-gray-600",
                    "focus:outline-none focus:ring-2 focus:ring-primary-400/40",
                  )}
                >
                  <option value="open">Open</option>
                  <option value="pending">Pending</option>
                  <option value="resolved">Resolved</option>
                  <option value="escalated">Escalated</option>
                  <option value="closed">Closed</option>
                </select>
                <button
                  onClick={() => setShowMeta((s) => !s)}
                  className={clsx(
                    "hidden xl:flex items-center justify-center w-8 h-8 rounded-lg transition-colors",
                    showMeta
                      ? "bg-gray-100 text-gray-600"
                      : "text-gray-400 hover:bg-[#faf8f5] hover:text-gray-600",
                  )}
                  title={showMeta ? "Hide details" : "Show details"}
                >
                  <Info className="h-4 w-4" />
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 bg-[#faf8f5]">
                {selected.messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full">
                    <p className="text-xs text-gray-400">No messages in this conversation</p>
                  </div>
                ) : (
                  selected.messages.map((msg, i) => {
                    const isBot = msg.role === "assistant";
                    const showTimestamp =
                      i === 0 ||
                      new Date(msg.created_at).getTime() -
                        new Date(selected.messages[i - 1].created_at).getTime() >
                        300000; // 5 min gap

                    return (
                      <div key={msg.id}>
                        {showTimestamp && (
                          <div className="flex justify-center mb-3">
                            <span className="text-[10px] text-gray-400 bg-[#f0ebe3]/60 px-2.5 py-1 rounded-full">
                              {new Date(msg.created_at).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "numeric",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                        )}
                        <div className={`flex ${isBot ? "justify-start" : "justify-end"}`}>
                          <div
                            className={clsx(
                              "max-w-[75%] px-4 py-3 text-[13px] leading-relaxed",
                              isBot
                                ? "bg-white border border-[#f0ebe3] text-gray-700 rounded-2xl rounded-tl-md shadow-sm"
                                : "bg-gray-900 text-white rounded-2xl rounded-tr-md shadow-sm",
                            )}
                          >
                            {isBot ? (
                              <MarkdownMessage content={msg.content} className="text-[13px] leading-relaxed" />
                            ) : (
                              msg.content
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Metadata sidebar */}
            {showMeta && (
              <div className="hidden xl:flex flex-col w-[220px] flex-shrink-0 border-l border-[#f0ebe3] bg-white overflow-y-auto">
                <div className="px-4 py-4 border-b border-[#f0ebe3]">
                  <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                    Details
                  </h3>
                </div>
                <div className="px-4 py-4 space-y-5">
                  {/* Bot */}
                  {selected.chatbot_id && chatbotMap.get(selected.chatbot_id) && (
                    <MetaField label="Bot">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded-md flex items-center justify-center text-[9px] font-bold text-white"
                          style={{ backgroundColor: chatbotMap.get(selected.chatbot_id)?.brand_color ?? "#6b7280" }}
                        >
                          {chatbotMap.get(selected.chatbot_id)!.name[0]?.toUpperCase()}
                        </div>
                        <span className="text-xs text-gray-700 truncate">
                          {chatbotMap.get(selected.chatbot_id)!.name}
                        </span>
                      </div>
                    </MetaField>
                  )}

                  {/* Contact */}
                  <MetaField label="Contact">
                    <div className="text-xs text-gray-700">
                      {selected.contact_name ?? "Anonymous"}
                    </div>
                    {selected.contact_email && (
                      <div className="text-[11px] text-gray-400 mt-0.5 break-all">
                        {selected.contact_email}
                      </div>
                    )}
                  </MetaField>

                  {/* Status */}
                  <MetaField label="Status">
                    {(() => {
                      const s = STATUS_STYLES[selected.status] ?? STATUS_STYLES.closed;
                      return (
                        <span
                          className={clsx(
                            "inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-1 rounded-md",
                            s.bg,
                            s.text,
                          )}
                        >
                          <span className={clsx("w-1.5 h-1.5 rounded-full", s.dot)} />
                          {selected.status}
                        </span>
                      );
                    })()}
                  </MetaField>

                  {/* Confidence */}
                  {selected.confidence != null && (
                    <MetaField label="Confidence">
                      <div className="flex items-center gap-2.5">
                        <div className="flex-1 h-1.5 bg-[#f0ebe3] rounded-full overflow-hidden">
                          <div
                            className={clsx(
                              "h-full rounded-full transition-all",
                              selected.confidence >= 0.7
                                ? "bg-green-400"
                                : selected.confidence >= 0.4
                                  ? "bg-amber-400"
                                  : "bg-red-400",
                            )}
                            style={{ width: `${Math.round(selected.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-gray-600 tabular-nums">
                          {Math.round(selected.confidence * 100)}%
                        </span>
                      </div>
                    </MetaField>
                  )}

                  {/* Outcome */}
                  {selected.outcome && (
                    <MetaField label="Outcome">
                      <span className="text-xs text-gray-600">{selected.outcome}</span>
                    </MetaField>
                  )}

                  {/* Timeline */}
                  <MetaField label="Created">
                    <span className="text-xs text-gray-600 tabular-nums">
                      {new Date(selected.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                  </MetaField>

                  {/* Messages count */}
                  <MetaField label="Messages">
                    <span className="text-xs text-gray-600 tabular-nums">
                      {selected.messages.length}
                    </span>
                  </MetaField>
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
        {label}
      </div>
      {children}
    </div>
  );
}
