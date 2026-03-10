"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Conversation } from "@/lib/types";
import { getConversations, exportConversationsCSV } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const statusColors: Record<string, string> = {
  open: "bg-blue-100 text-blue-700",
  pending: "bg-amber-100 text-amber-700",
  resolved: "bg-green-100 text-green-700",
  escalated: "bg-red-100 text-red-700",
  closed: "bg-gray-100 text-gray-700",
};

const outcomeColors: Record<string, string> = {
  resolved: "bg-green-100 text-green-700",
  escalated: "bg-orange-100 text-orange-700",
  churned: "bg-red-100 text-red-700",
  upgraded: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-600",
};

function OutcomeBadge({ outcome }: { outcome?: string }) {
  const label = outcome || "pending";
  const colorClass = outcomeColors[label] ?? outcomeColors.pending;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

function ConfidenceIndicator({ value }: { value?: number }) {
  if (value == null) return <span className="text-gray-400">-</span>;
  const pct = Math.round(value * 100);
  const color =
    value > 0.75
      ? "text-green-600"
      : value > 0.5
        ? "text-amber-600"
        : "text-red-600";
  return <span className={`font-medium ${color}`}>{pct}%</span>;
}

export default function ConversationsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    if (!workspace) return;
    setExporting(true);
    try {
      await exportConversationsCSV(workspace.id);
    } catch {
      // ignore
    } finally {
      setExporting(false);
    }
  }

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getConversations(workspace.id, {
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    })
      .then(setConversations)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, statusFilter, dateFrom, dateTo]);

  const filteredConversations = useMemo(() => {
    if (!outcomeFilter) return conversations;
    return conversations.filter((c) => {
      if (outcomeFilter === "pending") return !c.outcome || c.outcome === "pending";
      return c.outcome === outcomeFilter;
    });
  }, [conversations, outcomeFilter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Conversations</h1>
        <div className="flex items-center gap-3">
          <Button variant="secondary" size="sm" onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Export CSV"}
          </Button>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            aria-label="From date"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            aria-label="To date"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="pending">Pending</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All outcomes</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
            <option value="churned">Churned</option>
            <option value="upgraded">Upgraded</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      {filteredConversations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-gray-400">
            <MessageSquare className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No conversations yet</p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-500">Contact</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Outcome</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Confidence</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Last Message</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Created</th>
              </tr>
            </thead>
            <tbody>
              {filteredConversations.map((conv) => (
                <tr
                  key={conv.id}
                  onClick={() => router.push(`/conversations/${conv.id}`)}
                  className="border-b border-gray-100 last:border-0 cursor-pointer hover:bg-gray-50 transition-all duration-200"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {conv.contact_name || conv.contact_email || "Anonymous"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[conv.status] || statusColors.open}`}
                    >
                      {conv.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <OutcomeBadge outcome={conv.outcome} />
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceIndicator value={conv.confidence} />
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">
                    {conv.last_message_preview || "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(conv.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
