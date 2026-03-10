"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Check, X, FileText, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { GapClusterDetail } from "@/lib/types";
import {
  getGapClusterDetail,
  approveGapCluster,
  dismissGapCluster,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const statusVariant: Record<string, "default" | "success" | "warning" | "danger"> = {
  open: "danger",
  draft_ready: "warning",
  ai_draft_pending: "warning",
  approved: "success",
  dismissed: "default",
};

export default function GapClusterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clusterId = params.id as string;
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [cluster, setCluster] = useState<GapClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [editingDraft, setEditingDraft] = useState(false);
  const [draftBody, setDraftBody] = useState("");

  useEffect(() => {
    if (!workspace) return;
    getGapClusterDetail(workspace.id, clusterId)
      .then((c) => {
        setCluster(c);
        if (c.draft_article?.body) setDraftBody(c.draft_article.body);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, clusterId]);

  async function handleApprove() {
    if (!workspace) return;
    setApproving(true);
    try {
      await approveGapCluster(workspace.id, clusterId);
      router.push("/intelligence/gaps");
    } catch {
      // handle error
    } finally {
      setApproving(false);
    }
  }

  async function handleDismiss() {
    if (!workspace) return;
    setDismissing(true);
    try {
      await dismissGapCluster(workspace.id, clusterId);
      router.push("/intelligence/gaps");
    } catch {
      // handle error
    } finally {
      setDismissing(false);
    }
  }

  if (loading || !cluster) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {cluster.topic_label}
        </h1>
        <Badge variant={statusVariant[cluster.status] || "default"}>
          {cluster.status.replace(/_/g, " ")}
        </Badge>
        <span className="text-sm text-gray-500">
          {cluster.gap_count} question{cluster.gap_count !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Keywords */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Keywords</h2>
        <div className="flex flex-wrap gap-2">
          {cluster.keywords.map((kw) => (
            <span
              key={kw}
              className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700 border border-gray-200"
            >
              {kw}
            </span>
          ))}
        </div>
      </div>

      {/* Example queries */}
      <Card className="mb-6">
        <CardContent className="pt-5 pb-5">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="h-4 w-4 text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-900">
              Example Queries
            </h2>
          </div>
          {cluster.example_queries.length > 0 ? (
            <ul className="space-y-2">
              {cluster.example_queries.map((query, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-gray-700"
                >
                  <span className="text-gray-400 shrink-0 mt-0.5">
                    {i + 1}.
                  </span>
                  <span className="italic">&ldquo;{query}&rdquo;</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">No example queries</p>
          )}
        </CardContent>
      </Card>

      {/* Draft article */}
      {(cluster.status === "draft_ready" ||
        cluster.status === "ai_draft_pending") &&
      cluster.draft_article ? (
        <Card className="mb-6">
          <CardContent className="pt-5 pb-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-gray-400" />
                <h2 className="text-sm font-semibold text-gray-900">
                  Draft Article
                </h2>
              </div>
              {!editingDraft && (
                <button
                  onClick={() => setEditingDraft(true)}
                  className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Edit Draft
                </button>
              )}
            </div>

            <h3 className="text-base font-semibold text-gray-900 mb-3">
              {cluster.draft_article.title}
            </h3>

            {editingDraft ? (
              <textarea
                value={draftBody}
                onChange={(e) => setDraftBody(e.target.value)}
                rows={12}
                className="block w-full rounded-lg border border-gray-300 px-4 py-3 text-sm font-mono leading-relaxed placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200 mb-3"
              />
            ) : (
              <div className="rounded-lg bg-gray-50 p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {cluster.draft_article.body || "No content yet"}
              </div>
            )}

            <div className="flex gap-3 mt-4">
              <Button
                onClick={handleApprove}
                loading={approving}
                size="sm"
              >
                <Check className="h-4 w-4 mr-1" />
                Approve & Publish
              </Button>
              <Button
                variant="secondary"
                onClick={handleDismiss}
                loading={dismissing}
                size="sm"
              >
                <X className="h-4 w-4 mr-1" />
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : cluster.status === "open" ? (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center justify-center py-10 text-gray-400">
            <FileText className="h-8 w-8 mb-2" />
            <p className="text-sm font-medium">No draft article yet</p>
            {cluster.gap_count >= 3 && (
              <p className="text-xs mt-1 text-gray-500">
                A draft will be auto-generated once enough data is collected
              </p>
            )}
            <div className="flex gap-3 mt-4">
              <Button
                variant="secondary"
                onClick={handleDismiss}
                loading={dismissing}
                size="sm"
              >
                <X className="h-4 w-4 mr-1" />
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
