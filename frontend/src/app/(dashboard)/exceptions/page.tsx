"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { PartyPopper, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Exception } from "@/lib/types";
import { getExceptions } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const reasonColors: Record<string, string> = {
  low_confidence: "bg-amber-100 text-amber-700",
  sentiment: "bg-red-100 text-red-700",
  account_value: "bg-purple-100 text-purple-700",
  explicit_request: "bg-blue-100 text-blue-700",
  complexity: "bg-orange-100 text-orange-700",
};

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ConfidenceIndicator({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value > 0.75
      ? "text-green-600"
      : value > 0.5
        ? "text-amber-600"
        : "text-red-600";
  return <span className={`text-xs font-semibold ${color}`}>{pct}%</span>;
}

export default function ExceptionsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [loading, setLoading] = useState(true);
  const [reasonFilter, setReasonFilter] = useState("");

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getExceptions(
      workspace.id,
      reasonFilter ? { escalation_reason: reasonFilter } : {},
    )
      .then(setExceptions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, reasonFilter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Exceptions Queue</h1>
        <select
          value={reasonFilter}
          onChange={(e) => setReasonFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">All reasons</option>
          <option value="low_confidence">Low Confidence</option>
          <option value="sentiment">Negative Sentiment</option>
          <option value="account_value">High Account Value</option>
          <option value="explicit_request">Explicit Request</option>
          <option value="complexity">High Complexity</option>
        </select>
      </div>

      {exceptions.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <PartyPopper className="h-12 w-12 mb-3 text-green-400" />
            <p className="text-sm font-medium text-gray-600">
              No exceptions - your AI is handling everything!
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {exceptions.map((exc) => (
            <Card
              key={exc.conversation.id}
              className="cursor-pointer hover:shadow-md transition-all duration-200"
              onClick={() =>
                router.push(`/exceptions/${exc.conversation.id}`)
              }
            >
              <CardContent className="py-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">
                      {exc.contact?.name ||
                        exc.conversation.contact_name ||
                        exc.conversation.contact_email ||
                        "Anonymous"}
                    </span>
                    <ConfidenceIndicator value={exc.confidence_avg} />
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-gray-400">
                    <Clock className="h-3 w-3" />
                    {timeAgo(exc.conversation.updated_at)}
                  </div>
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${reasonColors[exc.escalation_reason] || "bg-gray-100 text-gray-600"}`}
                  >
                    {exc.escalation_reason.replace(/_/g, " ")}
                  </span>
                  <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
                    {exc.chatbot_name}
                  </span>
                </div>

                <p className="text-sm text-gray-500 line-clamp-2">
                  {exc.conversation.last_message_preview || "No messages"}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
