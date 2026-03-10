"use client";

import { useState, useEffect } from "react";
import { Lightbulb, TrendingUp, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { FeatureRequestCluster } from "@/lib/types";
import { getFeatureRequests, pushFeatureRequest } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const pushStatusBadge: Record<string, "default" | "success" | "warning"> = {
  not_pushed: "default",
  pushed: "success",
  pending: "warning",
};

export default function FeaturesPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [features, setFeatures] = useState<FeatureRequestCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [pushingId, setPushingId] = useState<string | null>(null);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    getFeatureRequests(workspace.id)
      .then(setFeatures)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  async function handlePush(clusterId: string, target: string) {
    if (!workspace) return;
    setPushingId(clusterId);
    try {
      await pushFeatureRequest(workspace.id, clusterId, target);
      setFeatures((prev) =>
        prev.map((f) =>
          f.id === clusterId ? { ...f, pm_push_status: "pushed" } : f,
        ),
      );
    } catch {
      // handle error
    } finally {
      setPushingId(null);
    }
  }

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
        Feature Requests
      </h1>
      <p className="text-sm text-gray-500 mb-6">
        Clustered feature requests extracted from conversations
      </p>

      {features.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <Lightbulb className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">
              No feature requests detected yet
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.id}>
              <CardContent className="py-5">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-900">
                    {feature.feature_name}
                  </h3>
                  {feature.pm_push_status && (
                    <Badge
                      variant={
                        pushStatusBadge[feature.pm_push_status] || "default"
                      }
                    >
                      {feature.pm_push_status.replace(/_/g, " ")}
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-3 mb-3">
                  <span className="text-xs text-gray-500">
                    {feature.request_count} requests
                  </span>
                  <div className="flex items-center gap-1 text-xs">
                    {feature.trend > 0 ? (
                      <TrendingUp className="h-3 w-3 text-green-500" />
                    ) : null}
                    {feature.trend > 0 && (
                      <span className="text-green-600">
                        +{Math.round(feature.trend * 100)}%
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-sm text-gray-500 italic line-clamp-2 mb-3">
                  &ldquo;{feature.example_quote}&rdquo;
                </p>

                {feature.pm_push_status !== "pushed" && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handlePush(feature.id, "linear")}
                    loading={pushingId === feature.id}
                  >
                    <ExternalLink className="h-3.5 w-3.5 mr-1" />
                    Push to Linear
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
