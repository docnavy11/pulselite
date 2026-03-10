"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useAuthStore } from "@/stores/auth-store";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { getDashboardData, getChatbots } from "@/lib/api-functions";
import { DashboardData, Chatbot } from "@/lib/types";

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

export default function DashboardPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const user = useAuthStore((s) => s.user);
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);

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
    getDashboardData(workspace.id, "30d")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id]);

  const hasChatbots = chatbots.length > 0;

  const resolutionRatePct = data
    ? Math.round(data.resolution_rate * 100)
    : 0;

  const trendData = data?.resolution_trend.map((d) => ({
    week: d.week_start,
    rate: Math.round(d.rate * 100),
  }));

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
              onClick={() => router.push("/chatbots/new")}
              className="flex items-center gap-2 px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-xl text-[13px] font-semibold transition-colors"
            >
              + New chatbot
            </button>
            <button
              onClick={() => router.push("/conversations")}
              className="px-4 py-2.5 bg-white border border-[#f0ebe3] text-gray-600 rounded-xl text-[13px] font-medium hover:bg-[#faf8f5] transition-colors"
            >
              View conversations
            </button>
            <button
              onClick={() => router.push("/knowledge")}
              className="px-4 py-2.5 bg-white border border-[#f0ebe3] text-gray-600 rounded-xl text-[13px] font-medium hover:bg-[#faf8f5] transition-colors"
            >
              Add knowledge
            </button>
          </div>
        )}

        {/* Chatbot filter chips — shown when chatbots exist */}
        {hasChatbots && !loading && (
          <div className="flex gap-2 mb-7 flex-wrap">
            {chatbots.map((b) => (
              <span
                key={b.id}
                className="px-3 py-1 bg-white border border-[#f0ebe3] text-gray-600 rounded-full text-[12px] font-medium"
              >
                {b.display_name || b.name}
              </span>
            ))}
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-3 gap-4 mb-6">
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
              onClick={() => router.push("/chatbots/new")}
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
