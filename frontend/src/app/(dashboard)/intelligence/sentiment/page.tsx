import { useState, useEffect, useCallback } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  ReferenceArea,
  BarChart,
  Bar,
  Cell,
  LabelList,
} from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { SentimentData, SegmentSentimentItem } from "@/lib/types";
import { getSentimentTrends, getSentimentBySegment } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

function sentimentColor(score: number): string {
  if (score > 0.6) return "#22c55e";
  if (score >= 0.4) return "#f97316";
  return "#ef4444";
}

export default function SentimentPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [data, setData] = useState<SentimentData | null>(null);
  const [range, setRange] = useState("30d");
  const [loading, setLoading] = useState(true);

  const [segment, setSegment] = useState<"chatbot" | "contact">("chatbot");
  const [segmentData, setSegmentData] = useState<SegmentSentimentItem[]>([]);
  const [segmentLoading, setSegmentLoading] = useState(false);

  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getSentimentTrends(workspace.id, range)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, range]);

  const fetchSegment = useCallback(async () => {
    if (!workspace) return;
    setSegmentLoading(true);
    try {
      const items = await getSentimentBySegment(workspace.id, segment, days);
      setSegmentData(items);
    } catch {
      // silently ignore
    } finally {
      setSegmentLoading(false);
    }
  }, [workspace, days, segment]);

  useEffect(() => {
    fetchSegment();
  }, [fetchSegment]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Sentiment Trends</h1>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <p className="text-sm font-medium text-gray-600">No sentiment data yet</p>
            <p className="text-xs mt-1">Sentiment is analysed as conversations are resolved</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Sentiment Trends
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Customer satisfaction over time
          </p>
        </div>
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

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500">Avg Sentiment</p>
            <p className="text-xl font-bold text-gray-900">
              {data.avg_sentiment.toFixed(2)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500">Positive</p>
            <p className="text-xl font-bold text-green-600">
              {Math.round(data.positive_pct)}%
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500">Negative</p>
            <p className="text-xl font-bold text-red-600">
              {Math.round(data.negative_pct)}%
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <p className="text-xs text-gray-500">Trend</p>
            <div className="flex items-center justify-center gap-1">
              {data.trend >= 0 ? (
                <TrendingUp className="h-4 w-4 text-green-500" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-500" />
              )}
              <span
                className={`text-xl font-bold ${data.trend >= 0 ? "text-green-600" : "text-red-600"}`}
              >
                {data.trend >= 0 ? "+" : ""}
                {data.trend.toFixed(2)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      <Card className="mb-6">
        <CardContent className="pt-5 pb-5">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.data_points}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis
                domain={[-1, 1]}
                tick={{ fontSize: 11 }}
                stroke="#94a3b8"
              />
              <Tooltip />
              <ReferenceArea y1={0.3} y2={1} fill="#dcfce7" fillOpacity={0.3} />
              <ReferenceArea
                y1={-0.3}
                y2={0.3}
                fill="#fef3c7"
                fillOpacity={0.3}
              />
              <ReferenceArea
                y1={-1}
                y2={-0.3}
                fill="#fee2e2"
                fillOpacity={0.3}
              />
              <ReferenceLine
                y={-0.3}
                stroke="#ef4444"
                strokeDasharray="5 5"
                label={{ value: "Alert", fontSize: 10, fill: "#ef4444" }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Sentiment by Segment */}
      <Card className="mb-6">
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-900">
              Sentiment by Segment
            </h2>
            <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              <button
                onClick={() => setSegment("chatbot")}
                className={`px-4 py-1.5 transition-colors ${
                  segment === "chatbot"
                    ? "bg-primary-500 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                By Chatbot
              </button>
              <button
                onClick={() => setSegment("contact")}
                className={`px-4 py-1.5 transition-colors border-l border-gray-200 ${
                  segment === "contact"
                    ? "bg-primary-500 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                By Contact
              </button>
            </div>
          </div>

          {segmentLoading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="h-6 w-6 text-primary-500" />
            </div>
          ) : segmentData.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <p className="text-sm">No data available for this period</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(200, segmentData.length * 52)}>
              <BarChart
                data={segmentData}
                layout="vertical"
                margin={{ top: 4, right: 80, left: 8, bottom: 4 }}
              >
                <XAxis
                  type="number"
                  domain={[-1, 1]}
                  tick={{ fontSize: 11 }}
                  stroke="#94a3b8"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={140}
                  tick={{ fontSize: 12 }}
                  stroke="#94a3b8"
                />
                <Tooltip
                  formatter={(value) => [Number(value).toFixed(3), "Avg Sentiment"]}
                />
                <Bar dataKey="avg_sentiment" radius={[0, 4, 4, 0]}>
                  {segmentData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={sentimentColor(entry.avg_sentiment)}
                    />
                  ))}
                  <LabelList
                    dataKey="avg_sentiment"
                    position="right"
                    formatter={(v) => Number(v).toFixed(2)}
                    style={{ fontSize: 11, fill: "#374151" }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
