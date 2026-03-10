"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { FileQuestion } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { GapCluster } from "@/lib/types";
import { getGapClusters } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const statusBorder: Record<string, string> = {
  open: "border-l-red-500",
  draft_ready: "border-l-amber-500",
  ai_draft_pending: "border-l-amber-400",
  approved: "border-l-green-500",
  dismissed: "border-l-gray-400",
};

const statusBadge: Record<string, string> = {
  open: "bg-red-100 text-red-700",
  draft_ready: "bg-amber-100 text-amber-700",
  ai_draft_pending: "bg-amber-100 text-amber-600",
  approved: "bg-green-100 text-green-700",
  dismissed: "bg-gray-100 text-gray-500",
};

export default function GapsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [clusters, setClusters] = useState<GapCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getGapClusters(
      workspace.id,
      statusFilter ? { status: statusFilter } : {},
    )
      .then(setClusters)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, statusFilter]);

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
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Documentation Gaps
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Topics your knowledge base doesn&apos;t cover well
          </p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="draft_ready">Draft Ready</option>
          <option value="approved">Approved</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {clusters.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <FileQuestion className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No documentation gaps found</p>
            <p className="text-xs mt-1">
              Gaps are detected as customers ask unanswered questions
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clusters.map((cluster) => (
            <Card
              key={cluster.id}
              className={`cursor-pointer hover:shadow-md transition-all duration-200 border-l-4 ${statusBorder[cluster.status] || "border-l-gray-300"}`}
              onClick={() =>
                router.push(`/intelligence/gaps/${cluster.id}`)
              }
            >
              <CardContent className="py-5">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-900">
                    {cluster.topic_label}
                  </h3>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${statusBadge[cluster.status] || "bg-gray-100 text-gray-600"}`}
                  >
                    {cluster.status.replace(/_/g, " ")}
                  </span>
                </div>

                <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 mb-2">
                  {cluster.gap_count} unanswered question
                  {cluster.gap_count !== 1 ? "s" : ""}
                </span>

                <p className="text-sm text-gray-500 italic line-clamp-2 mb-3">
                  &ldquo;{cluster.representative_query}&rdquo;
                </p>

                <div className="flex flex-wrap gap-1">
                  {cluster.keywords.slice(0, 4).map((kw) => (
                    <span
                      key={kw}
                      className="rounded bg-gray-50 px-1.5 py-0.5 text-[10px] text-gray-500 border border-gray-200"
                    >
                      {kw}
                    </span>
                  ))}
                  {cluster.keywords.length > 4 && (
                    <span className="text-[10px] text-gray-400">
                      +{cluster.keywords.length - 4}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
