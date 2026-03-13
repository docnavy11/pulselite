import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import {
  getDashboardData,
  getSentimentTrends,
  getGapClusters,
  getConversations,
  getActions,
  getKnowledgeBases,
  updateAction,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChatbotStore } from "@/stores/chatbot-store";
import type {
  DashboardData,
  SentimentData,
  GapCluster,
  Conversation,
  Action,
  KnowledgeBase,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helper functions (exported for testing)
// ---------------------------------------------------------------------------

export function formatDelta(
  current: number,
  previous: number,
  type: "percent" | "absolute" = "absolute",
): { text: string; color: string } {
  const diff = current - previous;
  if (Math.abs(diff) < 0.001) return { text: "No change", color: "text-gray-400" };
  const arrow = diff > 0 ? "\u2191" : "\u2193";
  const color = diff > 0 ? "text-green-500" : "text-red-500";
  if (type === "percent")
    return { text: `${arrow} ${Math.abs(diff * 100).toFixed(1)}pp`, color };
  return { text: `${arrow} ${Math.abs(diff).toFixed(1)}`, color };
}

export function resolutionBadgeColor(rate: number): string {
  if (rate >= 0.7) return "bg-green-100 text-green-700";
  if (rate >= 0.4) return "bg-yellow-100 text-yellow-700";
  return "bg-red-100 text-red-700";
}

export function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

// ---------------------------------------------------------------------------
// Range pill selector
// ---------------------------------------------------------------------------

const RANGES = ["7d", "30d", "90d"] as const;

function RangeSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
            value === r
              ? "bg-primary-500 text-white"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {r}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function ChatbotDashboardPage() {
  const { id: chatbotId } = useParams() as { id: string };
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbot = useChatbotStore((s) => s.currentChatbot);

  const [range, setRange] = useState<string>("30d");
  const [loading, setLoading] = useState(true);
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [gaps, setGaps] = useState<GapCluster[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);

  useEffect(() => {
    if (!workspace || !chatbotId) return;
    setLoading(true);
    Promise.all([
      getDashboardData(workspace.id, range, chatbotId),
      getSentimentTrends(workspace.id, range, chatbotId),
      getGapClusters(workspace.id, { status: "open", chatbot_id: chatbotId }),
      getConversations(workspace.id, { chatbot_id: chatbotId, limit: 5 }),
      getActions(workspace.id, chatbotId),
      getKnowledgeBases(workspace.id, chatbotId),
    ])
      .then(([dash, sent, gapsList, convs, acts, kbs]) => {
        setDashData(dash);
        setSentiment(sent);
        setGaps(gapsList);
        setConversations(convs);
        setActions(acts);
        setKnowledgeBases(kbs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId, range]);

  async function handleToggleAction(action: Action) {
    if (!workspace) return;
    try {
      const updated = await updateAction(workspace.id, chatbotId, action.id, {
        is_enabled: !action.is_enabled,
      });
      setActions((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  if (!dashData || !sentiment) {
    return (
      <div className="py-8 text-center text-gray-500">
        Failed to load dashboard data.
      </div>
    );
  }

  const { stats, feedback, top_topics, recent_negative_feedback } = dashData;
  const totalFeedback = feedback.thumbs_up + feedback.thumbs_down;
  const positivePct = totalFeedback > 0 ? Math.round((feedback.thumbs_up / totalFeedback) * 100) : 0;
  const resolutionDelta = formatDelta(dashData.resolution_rate, dashData.resolution_rate - dashData.resolution_rate_trend, "percent");
  const sentimentDelta = formatDelta(sentiment.avg_sentiment, sentiment.avg_sentiment - sentiment.trend);
  const unresolved = stats.total_conversations - stats.resolved - stats.escalated;

  return (
    <div className="space-y-6">
      {/* Range selector */}
      <div className="flex justify-end">
        <RangeSelector value={range} onChange={setRange} />
      </div>

      {/* Section 1: KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Conversations */}
        <Link to={`/logs?chatbot_id=${chatbotId}`} className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardContent className="py-5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                Conversations
              </p>
              <p className="text-[26px] font-bold text-gray-900 leading-tight">
                {stats.total_conversations}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {stats.resolved} resolved &middot; {stats.escalated} escalated
              </p>
            </CardContent>
          </Card>
        </Link>

        {/* Resolution Rate */}
        <Link to={`/logs?chatbot_id=${chatbotId}`} className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardContent className="py-5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                Resolution Rate
              </p>
              <p className="text-[26px] font-bold text-gray-900 leading-tight">
                {Math.round(dashData.resolution_rate * 100)}%
              </p>
              <p className={`text-xs mt-1 ${resolutionDelta.color}`}>
                {resolutionDelta.text}
              </p>
            </CardContent>
          </Card>
        </Link>

        {/* Avg Sentiment */}
        <Link to="/intelligence/sentiment" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardContent className="py-5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                Avg Sentiment
              </p>
              <p className="text-[26px] font-bold text-gray-900 leading-tight">
                {sentiment.avg_sentiment.toFixed(1)}
              </p>
              <p className={`text-xs mt-1 ${sentimentDelta.color}`}>
                {sentimentDelta.text}
              </p>
            </CardContent>
          </Card>
        </Link>

        {/* Positive Feedback */}
        <Link to="/intelligence/sentiment" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardContent className="py-5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                Positive Feedback
              </p>
              <p className="text-[26px] font-bold text-gray-900 leading-tight">
                {positivePct}%
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {feedback.thumbs_up} {"👍"} &middot; {feedback.thumbs_down} {"👎"}
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Section 2: Confidence & Resolution */}
      <Card>
        <CardContent className="py-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">
            Conversation Outcomes
          </h3>
          <div className="flex items-center gap-6">
            {/* Stacked bar */}
            <div className="flex-1">
              <div className="h-5 flex rounded-full overflow-hidden bg-gray-100">
                {stats.total_conversations > 0 ? (
                  <>
                    {stats.resolved > 0 && (
                      <div
                        className="bg-green-500 transition-all"
                        style={{
                          width: `${(stats.resolved / stats.total_conversations) * 100}%`,
                        }}
                      />
                    )}
                    {stats.escalated > 0 && (
                      <div
                        className="bg-yellow-400 transition-all"
                        style={{
                          width: `${(stats.escalated / stats.total_conversations) * 100}%`,
                        }}
                      />
                    )}
                    {unresolved > 0 && (
                      <div
                        className="bg-red-400 transition-all"
                        style={{
                          width: `${(unresolved / stats.total_conversations) * 100}%`,
                        }}
                      />
                    )}
                  </>
                ) : (
                  <div className="w-full bg-gray-200" />
                )}
              </div>
            </div>

            {/* Legend numbers */}
            <div className="flex gap-6 text-sm shrink-0">
              <div className="text-center">
                <p className="font-bold text-green-600">{stats.resolved}</p>
                <p className="text-[10px] text-gray-400">Resolved</p>
              </div>
              <div className="text-center">
                <p className="font-bold text-yellow-500">{stats.escalated}</p>
                <p className="text-[10px] text-gray-400">Escalated</p>
              </div>
              <div className="text-center">
                <p className="font-bold text-gray-400">{unresolved}</p>
                <p className="text-[10px] text-gray-400">Unresolved</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 3: Topics + Gaps */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Topics */}
        <Card>
          <CardContent className="py-5">
            <Link
              to={`/logs?chatbot_id=${chatbotId}`}
              className="text-sm font-semibold text-gray-700 mb-3 flex items-center justify-between group"
            >
              <span>Top Topics</span>
              <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
                View logs &rarr;
              </span>
            </Link>
            {top_topics.length === 0 ? (
              <p className="text-sm text-gray-400">No topics yet</p>
            ) : (
              <ul className="space-y-2">
                {top_topics.slice(0, 5).map((t) => (
                  <li
                    key={t.topic}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-700 truncate mr-2">
                      {t.topic}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${resolutionBadgeColor(t.resolution_rate)}`}
                    >
                      {Math.round(t.resolution_rate * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Knowledge Gaps */}
        <Card>
          <CardContent className="py-5">
            <Link
              to="/intelligence/gaps"
              className="text-sm font-semibold text-gray-700 mb-3 flex items-center justify-between group"
            >
              <span>Knowledge Gaps</span>
              <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
                View all &rarr;
              </span>
            </Link>
            {gaps.length === 0 ? (
              <p className="text-sm text-gray-400">
                No knowledge gaps detected
              </p>
            ) : (
              <>
                <ul className="space-y-2">
                  {gaps.slice(0, 5).map((g) => (
                    <li key={g.id}>
                      <Link
                        to={`/intelligence/gaps/${g.id}`}
                        className="flex items-center justify-between text-sm hover:bg-gray-50 -mx-2 px-2 py-1 rounded-lg transition-colors"
                      >
                        <span className="text-gray-700 truncate mr-2">
                          {g.representative_query}
                        </span>
                        <span className="text-xs text-gray-400 shrink-0">
                          &times;{g.gap_count}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
                <Link
                  to="/intelligence/gaps"
                  className="inline-block mt-3 text-xs text-primary-500 hover:text-primary-600 font-medium"
                >
                  View all &rarr;
                </Link>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Section 4: Recent Conversations */}
      <Card>
        <CardContent className="py-5">
          <Link
            to={`/logs?chatbot_id=${chatbotId}`}
            className="text-sm font-semibold text-gray-700 mb-3 flex items-center justify-between group"
          >
            <span>Recent Conversations</span>
            <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
              View all &rarr;
            </span>
          </Link>
          {conversations.length === 0 ? (
            <p className="text-sm text-gray-400">No conversations yet</p>
          ) : (
            <>
              <ul className="divide-y divide-gray-100">
                {conversations.slice(0, 5).map((c) => {
                  let badgeVariant: "success" | "warning" | "default" = "default";
                  let badgeLabel = "Unresolved";
                  if (c.outcome === "resolved") {
                    badgeVariant = "success";
                    badgeLabel = "Resolved";
                  } else if (c.outcome === "escalated") {
                    badgeVariant = "warning";
                    badgeLabel = "Escalated";
                  }

                  return (
                    <li key={c.id}>
                      <Link
                        to={`/conversations/${c.id}`}
                        className="flex items-center justify-between py-2.5 gap-4 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
                      >
                        <p className="text-sm text-gray-700 truncate flex-1">
                          {c.last_message_preview || "No messages"}
                        </p>
                        <div className="flex items-center gap-3 shrink-0">
                          <Badge variant={badgeVariant}>{badgeLabel}</Badge>
                          <span className="text-xs text-gray-400 w-16 text-right">
                            {formatRelativeTime(c.created_at)}
                          </span>
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
              <Link
                to={`/logs?chatbot_id=${chatbotId}`}
                className="inline-block mt-3 text-xs text-primary-500 hover:text-primary-600 font-medium"
              >
                View all &rarr;
              </Link>
            </>
          )}
        </CardContent>
      </Card>

      {/* Section 5: Crawl Health + Feedback */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Knowledge Sources */}
        <Card>
          <CardContent className="py-5">
            <Link
              to={`/chatbots/${chatbotId}/sources`}
              className="text-sm font-semibold text-gray-700 mb-3 flex items-center justify-between group"
            >
              <span>Knowledge Sources</span>
              <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
                View &rarr;
              </span>
            </Link>
            {knowledgeBases.length === 0 ? (
              <p className="text-sm text-gray-400">
                No knowledge base yet.{" "}
                <Link
                  to={`/chatbots/${chatbotId}/sources`}
                  className="text-primary-500 hover:text-primary-600 font-medium"
                >
                  Add one &rarr;
                </Link>
              </p>
            ) : (
              <>
                <p className="text-sm text-gray-500 mb-2">
                  {knowledgeBases.length} knowledge base{knowledgeBases.length !== 1 ? "s" : ""}
                </p>
                <ul className="space-y-1.5">
                  {knowledgeBases.map((kb) => (
                    <li
                      key={kb.id}
                      className="text-sm text-gray-700 flex items-center gap-2"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shrink-0" />
                      {kb.name}
                    </li>
                  ))}
                </ul>
                <Link
                  to={`/chatbots/${chatbotId}/sources`}
                  className="inline-block mt-3 text-xs text-primary-500 hover:text-primary-600 font-medium"
                >
                  Manage sources &rarr;
                </Link>
              </>
            )}
          </CardContent>
        </Card>

        {/* Feedback */}
        <Card>
          <CardContent className="py-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              User Feedback
            </h3>
            <div className="flex gap-6 mb-4">
              <div className="text-center">
                <p className="text-lg font-bold text-green-600">
                  {"👍"} {feedback.thumbs_up}
                </p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-red-500">
                  {"👎"} {feedback.thumbs_down}
                </p>
              </div>
            </div>
            {recent_negative_feedback.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                  Recent Negative
                </p>
                {recent_negative_feedback.slice(0, 3).map((fb) => (
                  <div
                    key={fb.id}
                    className="rounded-md bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-700"
                  >
                    {fb.comment || fb.message_content}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Section 6: Configuration */}
      <Card>
        <CardContent className="py-5">
          <Link
            to={`/chatbots/${chatbotId}/settings`}
            className="text-sm font-semibold text-gray-700 mb-4 flex items-center justify-between group"
          >
            <span>Configuration</span>
            <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity">
              Edit &rarr;
            </span>
          </Link>

          {/* Model row */}
          {chatbot && (
            <Link
              to={`/chatbots/${chatbotId}/settings`}
              className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-sm hover:bg-gray-50 -mx-2 px-2 py-2 rounded-lg transition-colors"
            >
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                  Model
                </p>
                <p className="text-gray-700">
                  {chatbot.llm_model?.split("/").pop()}
                </p>
                <p className="text-xs text-gray-400">
                  temp {chatbot.temperature} &middot; {chatbot.max_tokens} tokens
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                  Retrieval
                </p>
                <p className="text-gray-700">
                  top-{chatbot.retrieval_top_k}
                  {chatbot.use_reranking && " + reranking"}
                </p>
                <p className="text-xs text-gray-400">
                  threshold {chatbot.confidence_threshold}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1">
                  Tone
                </p>
                <p className="text-gray-700 capitalize">{chatbot.tone}</p>
              </div>
            </Link>
          )}

          {/* Actions */}
          <div className="mb-4">
            <Link
              to={`/chatbots/${chatbotId}/actions`}
              className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2 flex items-center justify-between group"
            >
              <span>Actions</span>
              <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity normal-case tracking-normal">
                Manage &rarr;
              </span>
            </Link>
            {actions.length === 0 ? (
              <p className="text-sm text-gray-400">
                No actions linked.{" "}
                <Link
                  to={`/chatbots/${chatbotId}/actions`}
                  className="text-primary-500 hover:text-primary-600 font-medium"
                >
                  Go to Actions tab &rarr;
                </Link>
              </p>
            ) : (
              <ul className="space-y-2">
                {actions.map((action) => (
                  <li
                    key={action.id}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="min-w-0">
                      <p className="text-gray-700 font-medium truncate">
                        {action.name}
                      </p>
                      <p className="text-xs text-gray-400 truncate">
                        {action.trigger_description}
                      </p>
                    </div>
                    <button
                      onClick={() => handleToggleAction(action)}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${
                        action.is_enabled ? "bg-primary-500" : "bg-gray-200"
                      }`}
                      role="switch"
                      aria-checked={action.is_enabled}
                    >
                      <span
                        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
                          action.is_enabled ? "translate-x-4" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Knowledge sources */}
          <div>
            <Link
              to={`/chatbots/${chatbotId}/sources`}
              className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2 flex items-center justify-between group"
            >
              <span>Knowledge Sources</span>
              <span className="text-xs text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity normal-case tracking-normal">
                Manage &rarr;
              </span>
            </Link>
            {knowledgeBases.length === 0 ? (
              <p className="text-sm text-gray-400">
                No knowledge base yet.{" "}
                <Link
                  to={`/chatbots/${chatbotId}/sources`}
                  className="text-primary-500 hover:text-primary-600 font-medium"
                >
                  Add one &rarr;
                </Link>
              </p>
            ) : (
              <Link
                to={`/chatbots/${chatbotId}/sources`}
                className="flex flex-wrap gap-2 hover:opacity-80 transition-opacity"
              >
                {knowledgeBases.map((kb) => (
                  <Badge key={kb.id}>{kb.name}</Badge>
                ))}
              </Link>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
