"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ExternalLink, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { LeadDetail } from "@/lib/types";
import { getLeadDetail, pushLeadToCRM } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const tierColors: Record<string, "default" | "success" | "warning" | "danger"> = {
  hot: "danger",
  warm: "warning",
  cold: "default",
};

export default function LeadDetailPage() {
  const params = useParams();
  const contactId = params.id as string;
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [pushing, setPushing] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getLeadDetail(workspace.id, contactId)
      .then(setLead)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, contactId]);

  async function handlePushCRM() {
    if (!workspace) return;
    setPushing(true);
    try {
      await pushLeadToCRM(workspace.id, contactId);
    } catch {
      // handle error
    } finally {
      setPushing(false);
    }
  }

  if (loading || !lead) {
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
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              {lead.name || "Anonymous"}
            </h1>
            {lead.lead_tier && (
              <Badge variant={tierColors[lead.lead_tier] || "default"}>
                {lead.lead_tier}
              </Badge>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">{lead.email}</p>
        </div>
        <Button onClick={handlePushCRM} loading={pushing} variant="secondary">
          <ExternalLink className="h-4 w-4 mr-2" />
          Push to CRM
        </Button>
      </div>

      {/* Score breakdown */}
      <Card className="mb-6">
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-900">
              Score Breakdown
            </h2>
            <span className="text-2xl font-bold text-gray-900">
              {lead.lead_score}
            </span>
          </div>
          <div className="space-y-2">
            {lead.signals.map((signal, i) => (
              <div key={i} className="rounded-lg bg-gray-50 px-4 py-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-700 capitalize">
                    {signal.signal_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm font-semibold text-primary-600">
                    +{signal.points}
                  </span>
                </div>
                {signal.quote && (
                  <p className="text-xs text-gray-500 italic">
                    &ldquo;{signal.quote}&rdquo;
                  </p>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Conversations */}
      <Card>
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center gap-2 mb-4">
            <MessageSquare className="h-4 w-4 text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-900">
              Conversations ({lead.conversations.length})
            </h2>
          </div>
          {lead.conversations.length === 0 ? (
            <p className="text-sm text-gray-400">No conversations</p>
          ) : (
            <div className="space-y-2">
              {lead.conversations.map((conv) => (
                <div
                  key={conv.id}
                  className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3"
                >
                  <p className="text-sm text-gray-700 truncate flex-1 mr-4">
                    {conv.last_message_preview || "No messages"}
                  </p>
                  <span className="text-xs text-gray-400 shrink-0">
                    {new Date(conv.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
