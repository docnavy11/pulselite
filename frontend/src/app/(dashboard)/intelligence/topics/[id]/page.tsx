"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { TopicClusterDetail } from "@/lib/types";
import { getTopicDetail } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function TopicDetailPage() {
  const params = useParams();
  const topicId = params.id as string;
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [topic, setTopic] = useState<TopicClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getTopicDetail(workspace.id, topicId)
      .then(setTopic)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, topicId]);

  function exportCSV() {
    if (!topic) return;
    const rows = [
      ["Date", "Count"],
      ...topic.trend_data.map((d) => [d.date, String(d.count)]),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `topic-${topic.topic_name.replace(/\s+/g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading || !topic) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {topic.topic_name}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {topic.conversation_count} conversations
          </p>
        </div>
        <Button variant="secondary" onClick={exportCSV} size="sm">
          <Download className="h-4 w-4 mr-1" />
          Export CSV
        </Button>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-5 pb-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Trend</h2>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={topic.trend_data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#4f46e5"
                fill="#eef2ff"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardContent className="pt-5 pb-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">
              Keywords
            </h2>
            <div className="flex flex-wrap gap-2">
              {topic.keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700 border border-gray-200"
                >
                  {kw}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5 pb-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">
              Example Questions
            </h2>
            <ul className="space-y-2">
              {topic.example_questions.map((q, i) => (
                <li key={i} className="text-sm text-gray-600 italic">
                  &ldquo;{q}&rdquo;
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
