"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  MessageSquare,
  CheckCircle,
  AlertTriangle,
  BookOpen,
  FileQuestion,
  Users,
  Zap,
  Flame,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { DashboardData } from "@/lib/types";
import { getDashboardData, getChatbots } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Chatbot } from "@/lib/types";

export default function DashboardPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [data, setData] = useState<DashboardData | null>(null);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [range, setRange] = useState("30d");
  const [chatbotId, setChatbotId] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getChatbots(workspace.id).then(setChatbots).catch(() => {});
  }, [workspace]);

  useEffect(() => {
    if (!workspace) return;
    setLoading(true);
    getDashboardData(workspace.id, range, chatbotId || undefined)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, range, chatbotId]);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  const rateColor =
    data.resolution_rate > 0.75
      ? "text-green-600"
      : data.resolution_rate > 0.5
        ? "text-amber-600"
        : "text-red-600";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex gap-3">
          <select
            value={chatbotId}
            onChange={(e) => setChatbotId(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All chatbots</option>
            {chatbots.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name || b.name}
              </option>
            ))}
          </select>
          <select
            value={range}
            onChange={(e) => setRange(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Resolution Rate Hero */}
      <Card className="mb-6">
        <CardContent className="py-8 text-center">
          <p className="text-sm font-medium text-gray-500 mb-1">
            Resolution Rate
          </p>
          <p className={`text-5xl font-bold ${rateColor}`}>
            {Math.round(data.resolution_rate * 100)}%
          </p>
          <div className="flex items-center justify-center gap-1 mt-2">
            {data.resolution_rate_trend >= 0 ? (
              <TrendingUp className="h-4 w-4 text-green-500" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-500" />
            )}
            <span
              className={`text-sm font-medium ${data.resolution_rate_trend >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              {data.resolution_rate_trend >= 0 ? "+" : ""}
              {Math.round(data.resolution_rate_trend * 100)}% vs last period
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Conversations", value: data.stats.total_conversations, icon: MessageSquare, color: "text-primary-500 bg-primary-50" },
          { label: "Auto-Resolved", value: data.stats.resolved, icon: CheckCircle, color: "text-green-600 bg-green-50" },
          { label: "Escalated", value: data.stats.escalated, icon: AlertTriangle, color: "text-amber-600 bg-amber-50" },
          { label: "New KB Articles", value: data.stats.new_articles, icon: BookOpen, color: "text-purple-600 bg-purple-50" },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="flex items-center gap-3 py-4">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${stat.color}`}>
                <stat.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-gray-500">{stat.label}</p>
                <p className="text-xl font-bold text-gray-900">{stat.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Knowledge Velocity */}
      {data.knowledge_velocity > 0 && (
        <Card className="mb-6">
          <CardContent className="py-4 flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-50 text-orange-600 shrink-0">
              <Flame className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <p className="text-xs text-gray-500">Knowledge Velocity</p>
              <p className="text-lg font-bold text-gray-900">
                {Math.round(data.knowledge_velocity * 100)}%
              </p>
            </div>
            <p className="text-xs text-gray-400 max-w-xs text-right">
              % of knowledge gaps resolved vs. discovered this period. Higher = your KB is improving faster than questions arise.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <Card>
          <CardContent className="pt-5 pb-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              Resolution Trend
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.resolution_trend.map((d) => ({ ...d, rate_pct: Math.round(d.rate * 100) }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="week_start" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" domain={[0, 100]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="rate_pct"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5 pb-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">
              Escalation Breakdown
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={Object.entries(data.escalation_breakdown).map(([reason, count]) => ({ reason, count }))}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis
                  dataKey="reason"
                  type="category"
                  tick={{ fontSize: 11 }}
                  stroke="#94a3b8"
                  width={120}
                />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Intelligence Highlights */}
      <div className="grid grid-cols-3 gap-4">
        <Link href="/intelligence/gaps">
          <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
            <CardContent className="flex items-center gap-3 py-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-600">
                <FileQuestion className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Doc Gaps</p>
                <p className="text-lg font-bold text-gray-900">
                  {data.intelligence.open_gaps}
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/intelligence/leads">
          <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
            <CardContent className="flex items-center gap-3 py-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Hot Leads</p>
                <p className="text-lg font-bold text-gray-900">
                  {data.intelligence.hot_leads}
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/intelligence/topics">
          <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
            <CardContent className="flex items-center gap-3 py-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <Zap className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Topic Anomalies</p>
                <p className="text-lg font-bold text-gray-900">
                  {data.intelligence.topic_anomalies}
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
