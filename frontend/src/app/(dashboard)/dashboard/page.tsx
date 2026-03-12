import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { getDashboardData, getChatbots, getSentimentTrends, getGapClusters } from "@/lib/api-functions";
import { DashboardData, Chatbot, SentimentData, GapCluster } from "@/lib/types";

function getGreeting(name: string): string {
  const hour = new Date().getHours();
  const time = hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  const firstName = name.split(" ")[0] || name;
  return `Good ${time}, ${firstName}`;
}

function KpiCard({
  label,
  value,
  trend,
  accent,
}: {
  label: string;
  value: string | number;
  trend?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`bg-white rounded-xl border p-5 ${
        accent
          ? "border-primary-200 ring-1 ring-primary-100"
          : "border-[#f0ebe3]"
      }`}
    >
      <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
        {label}
      </div>
      <div
        className={`text-3xl font-black tracking-tight ${
          accent ? "text-primary-500" : "text-gray-900"
        }`}
      >
        {value}
      </div>
      {trend && (
        <div className="text-[11px] text-gray-400 mt-1">{trend}</div>
      )}
    </div>
  );
}

function SentimentLabel({ score }: { score: number }) {
  if (score >= 0.3) return <span className="text-green-600 font-semibold">Positive</span>;
  if (score <= -0.3) return <span className="text-red-500 font-semibold">Negative</span>;
  return <span className="text-gray-500 font-semibold">Neutral</span>;
}

export default function DashboardPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const { register } = useCopilot();
  const [data, setData] = useState<DashboardData | null>(null);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [selectedChatbotId, setSelectedChatbotId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [topics, setTopics] = useState<GapCluster[]>([]);

  const userName = user?.name || user?.email || "there";
  const greeting = getGreeting(userName);

  useEffect(() => {
    if (!workspace?.id) return;
    getChatbots(workspace.id)
      .then(setChatbots)
      .catch(() => {});
  }, [workspace?.id]);

  useEffect(() => {
    if (!workspace?.id) return;
    setLoading(true);
    Promise.all([
      getDashboardData(workspace.id, "30d", selectedChatbotId ?? undefined),
      getSentimentTrends(workspace.id, "30d"),
      getGapClusters(workspace.id, { status: "open" }),
    ])
      .then(([dash, sent, gaps]) => {
        setData(dash);
        setSentiment(sent);
        setTopics(gaps.slice(0, 5));
        register({
          page: "dashboard",
          data: {
            metrics: dash,
          },
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id, selectedChatbotId, register]);

  const hasChatbots = chatbots.length > 0;

  const resolutionRatePct = data
    ? Math.round(data.resolution_rate * 100)
    : 0;

  const trendData = data?.resolution_trend.map((d) => ({
    week: d.week_start,
    rate: Math.round(d.rate * 100),
  }));

  const sentimentPoints = sentiment?.data_points.map((d) => ({
    date: d.date.slice(5), // MM-DD
    score: parseFloat((d.score * 100).toFixed(1)),
  })) ?? [];

  const totalFeedback = (data?.feedback.thumbs_up ?? 0) + (data?.feedback.thumbs_down ?? 0);
  const satisfactionPct = totalFeedback > 0
    ? Math.round((data!.feedback.thumbs_up / totalFeedback) * 100)
    : null;

  return (
    <div className="flex-1 overflow-y-auto bg-[#faf8f5]">
      <div className="max-w-5xl mx-auto px-6 py-7">
        {/* Greeting */}
        <div className="mb-7">
          <h1 className="text-2xl font-black tracking-tight text-gray-900 mb-1">
            {greeting}
          </h1>
          <p className="text-[13px] text-gray-400">
            {hasChatbots
              ? `${chatbots.filter((b) => b.is_active).length} bots active · ${
                  data?.stats.total_conversations ?? 0
                } total conversations`
              : "Create your first chatbot to get started"}
          </p>
        </div>

        {/* Quick actions — shown when no chatbots and not loading */}
        {!hasChatbots && !loading && (
          <div className="flex gap-3 mb-7">
            <button
              onClick={() => navigate("/chatbots/new")}
              className="flex items-center gap-2 px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-xl text-[13px] font-semibold transition-colors"
            >
              + New chatbot
            </button>
            <button
              onClick={() => navigate("/conversations")}
              className="px-4 py-2.5 bg-white border border-[#f0ebe3] text-gray-600 rounded-xl text-[13px] font-medium hover:bg-[#faf8f5] transition-colors"
            >
              View conversations
            </button>
            <button
              onClick={() => navigate("/chatbots")}
              className="px-4 py-2.5 bg-white border border-[#f0ebe3] text-gray-600 rounded-xl text-[13px] font-medium hover:bg-[#faf8f5] transition-colors"
            >
              Add knowledge
            </button>
          </div>
        )}

        {/* Chatbot filter chips — only shown when there are multiple bots */}
        {hasChatbots && chatbots.length > 1 && !loading && (
          <div className="flex gap-2 mb-7 flex-wrap">
            <button
              onClick={() => setSelectedChatbotId(null)}
              className={`px-3 py-1 rounded-full text-[12px] font-medium transition-colors ${
                selectedChatbotId === null
                  ? "bg-primary-500 text-white"
                  : "bg-white border border-[#f0ebe3] text-gray-500 hover:border-primary-300 hover:text-primary-500"
              }`}
            >
              All
            </button>
            {chatbots.map((b) => (
              <button
                key={b.id}
                onClick={() => setSelectedChatbotId(b.id === selectedChatbotId ? null : b.id)}
                className={`px-3 py-1 rounded-full text-[12px] font-medium transition-colors ${
                  selectedChatbotId === b.id
                    ? "bg-primary-500 text-white"
                    : "bg-white border border-[#f0ebe3] text-gray-500 hover:border-primary-300 hover:text-primary-500"
                }`}
              >
                {b.display_name || b.name}
              </button>
            ))}
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
          {loading ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : (
            <>
              <KpiCard
                label="Auto-resolution rate"
                value={`${resolutionRatePct}%`}
                trend="Last 30 days"
                accent
              />
              <KpiCard
                label="Total conversations"
                value={data?.stats.total_conversations ?? 0}
                trend="All time"
              />
              <KpiCard
                label="Escalated"
                value={data?.stats.escalated ?? 0}
                trend="Last 30 days"
              />
            </>
          )}
        </div>

        {/* Satisfaction + Sentiment row */}
        {!loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {/* Satisfaction */}
            <div className="bg-white border border-[#f0ebe3] rounded-xl p-5">
              <h2 className="text-[12px] font-semibold text-gray-500 uppercase tracking-wide mb-4">
                User satisfaction — last 30 days
              </h2>
              {totalFeedback === 0 ? (
                <div className="flex flex-col items-center justify-center py-4 text-center">
                  <div className="flex gap-3 mb-3 opacity-25">
                    <span className="text-3xl">👍</span>
                    <span className="text-3xl">👎</span>
                  </div>
                  <p className="text-[13px] font-medium text-gray-500 mb-1">No ratings yet</p>
                  <p className="text-[11px] text-gray-400 max-w-[180px]">
                    Ratings appear once users rate responses in your chat widget.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[13px] text-gray-700">
                      <span className="text-xl">👍</span> Helpful
                    </div>
                    <span className="font-bold text-gray-900">{data!.feedback.thumbs_up}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-[13px] text-gray-700">
                      <span className="text-xl">👎</span> Not helpful
                    </div>
                    <span className="font-bold text-gray-900">{data!.feedback.thumbs_down}</span>
                  </div>
                  <div className="mt-3">
                    <div className="h-2 rounded-full bg-[#f0ebe3] overflow-hidden">
                      <div
                        className="h-full bg-green-400 rounded-full transition-all"
                        style={{ width: `${satisfactionPct}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-gray-400 mt-1">
                      {satisfactionPct}% satisfaction rate
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Sentiment */}
            <div className="bg-white border border-[#f0ebe3] rounded-xl p-5">
              <h2 className="text-[12px] font-semibold text-gray-500 uppercase tracking-wide mb-4">
                Sentiment — last 30 days
              </h2>
              {sentiment && sentiment.data_points.length > 0 ? (
                <>
                  <div className="flex items-baseline gap-2 mb-3">
                    <span className="text-2xl font-black text-gray-900">
                      {sentiment.positive_pct.toFixed(0)}%
                    </span>
                    <SentimentLabel score={sentiment.avg_sentiment} />
                    <span className="text-[11px] text-gray-400 ml-auto">
                      {sentiment.negative_pct.toFixed(0)}% negative
                    </span>
                  </div>
                  <ResponsiveContainer width="100%" height={80}>
                    <LineChart data={sentimentPoints}>
                      <XAxis dataKey="date" hide />
                      <YAxis hide domain={[-100, 100]} />
                      <Tooltip
                        contentStyle={{
                          fontSize: 11,
                          border: "1px solid #f0ebe3",
                          borderRadius: 8,
                        }}
                        formatter={(v) => [`${v}`, "Score"]}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#ff6b35"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-4 text-center">
                  <svg className="mb-3 opacity-20" width="48" height="32" viewBox="0 0 48 32" fill="none">
                    <path d="M2 28 Q8 4 14 16 Q20 28 26 12 Q32 -4 38 16 Q44 28 46 20" stroke="#52525b" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
                  </svg>
                  <p className="text-[13px] font-medium text-gray-500 mb-1">No sentiment data yet</p>
                  <p className="text-[11px] text-gray-400 max-w-[180px]">
                    Sentiment is analysed automatically as conversations close.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Resolution trend chart */}
        {!loading && trendData && trendData.length > 0 && (
          <div className="bg-white border border-[#f0ebe3] rounded-xl p-5 mb-6">
            <h2 className="text-[12px] font-semibold text-gray-500 uppercase tracking-wide mb-4">
              Resolution trend — last 12 weeks
            </h2>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={trendData} barSize={12}>
                <XAxis
                  dataKey="week"
                  tick={{ fontSize: 10, fill: "#aaa" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis hide />
                <Tooltip
                  contentStyle={{
                    fontSize: 11,
                    border: "1px solid #f0ebe3",
                    borderRadius: 8,
                  }}
                  cursor={{ fill: "#faf8f5" }}
                />
                <Bar dataKey="rate" fill="#ff6b35" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Topics row: answered + unanswered */}
        {!loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {/* Top answered topics */}
            <div className="bg-white border border-[#f0ebe3] rounded-xl p-5">
              <h2 className="text-[12px] font-semibold text-gray-500 uppercase tracking-wide mb-4">
                Top answered topics
              </h2>
              {data?.top_topics && data.top_topics.length > 0 ? (
                <ul className="space-y-2">
                  {data.top_topics.map((t) => (
                    <li key={t.topic} className="flex items-center justify-between gap-3">
                      <span className="text-[13px] text-gray-800 truncate">{t.topic}</span>
                      <span className="shrink-0 text-[11px] font-semibold bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
                        {t.count}×
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex items-center gap-4 py-2">
                  <div className="shrink-0 w-9 h-9 rounded-full bg-green-50 flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="6.5" stroke="#16a34a" strokeWidth="1.5"/>
                      <path d="M5 8l2 2 4-4" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-700 mb-0.5">No answered topics yet</p>
                    <p className="text-[11px] text-gray-400">
                      Topics are extracted from resolved conversations once your bot starts answering questions.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Top unanswered topics */}
            <div className="bg-white border border-[#f0ebe3] rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[12px] font-semibold text-gray-500 uppercase tracking-wide">
                  Top unanswered topics
                </h2>
                {topics.length > 0 && (
                  <button
                    onClick={() => navigate("/intelligence/gaps")}
                    className="text-[11px] text-primary-500 hover:text-primary-700 font-medium"
                  >
                    View all →
                  </button>
                )}
              </div>
              {topics.length === 0 ? (
                <div className="flex items-center gap-4 py-2">
                  <div className="shrink-0 w-9 h-9 rounded-full bg-[#fff3ee] flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="6.5" stroke="#ff6b35" strokeWidth="1.5"/>
                      <path d="M8 5v3.5M8 10.5v.5" stroke="#ff6b35" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div>
                    <p className="text-[13px] font-medium text-gray-700 mb-0.5">No gaps detected yet</p>
                    <p className="text-[11px] text-gray-400">
                      When the bot can&apos;t answer confidently, the question is logged here so you know what to add.
                    </p>
                  </div>
                </div>
              ) : (
                <ul className="space-y-2">
                  {topics.map((t) => (
                    <li key={t.id} className="flex items-center justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <span className="text-[13px] font-medium text-gray-800 truncate block">
                          {t.topic_label}
                        </span>
                        <span className="text-[11px] text-gray-400 truncate block">
                          e.g. &ldquo;{t.representative_query}&rdquo;
                        </span>
                      </div>
                      <span className="shrink-0 text-[11px] font-semibold bg-primary-50 text-primary-600 px-2 py-0.5 rounded-full">
                        {t.gap_count}×
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Empty state — no chatbots, not loading */}
        {!loading && !hasChatbots && (
          <div className="bg-white border border-[#f0ebe3] rounded-2xl p-10 text-center">
            <div className="flex justify-center mb-4">
              <svg width="64" height="32" viewBox="0 0 64 32" fill="none">
                <path
                  d="M4 16 L14 16 L20 4 L26 28 L32 8 L38 16 L44 16 L50 10 L56 16 L60 16"
                  stroke="#ff6b35"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <h3 className="text-[15px] font-bold text-gray-800 mb-2">
              Your first chatbot is one URL away
            </h3>
            <p className="text-[13px] text-gray-400 mb-5">
              Paste a URL, we crawl it and auto-configure your bot in minutes.
            </p>
            <button
              onClick={() => navigate("/chatbots/new")}
              className="px-5 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-xl text-[13px] font-semibold transition-colors"
            >
              Create my first chatbot
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
