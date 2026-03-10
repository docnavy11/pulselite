"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { MessageSquareText, Zap } from "lucide-react";
import { ResponsiveContainer, LineChart, Line } from "recharts";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { TopicCluster } from "@/lib/types";
import { getTopics } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function TopicsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [topics, setTopics] = useState<TopicCluster[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    getTopics(workspace.id)
      .then(setTopics)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">
        Topic Intelligence
      </h1>
      <p className="text-sm text-gray-500 mb-6">
        What customers are asking about
      </p>

      {topics.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <MessageSquareText className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No topics detected yet</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((topic) => {
            const sparkData = topic.trend.map((v, i) => ({
              i,
              v,
            }));
            return (
              <Card
                key={topic.id}
                className="cursor-pointer hover:shadow-md transition-all duration-200"
                onClick={() =>
                  router.push(`/intelligence/topics/${topic.id}`)
                }
              >
                <CardContent className="py-5">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      {topic.topic_name}
                    </h3>
                    {topic.is_anomaly && (
                      <Badge variant="warning">
                        <Zap className="h-3 w-3 mr-0.5" />
                        Anomaly
                      </Badge>
                    )}
                  </div>

                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-xs text-gray-500">
                      {topic.conversation_count} conversations
                    </span>
                    <div className="w-20 h-6">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={sparkData}>
                          <Line
                            type="monotone"
                            dataKey="v"
                            stroke="#6366f1"
                            strokeWidth={1.5}
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <p className="text-sm text-gray-500 line-clamp-2 italic">
                    &ldquo;
                    {topic.example_questions[0] || "No examples"}
                    &rdquo;
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
