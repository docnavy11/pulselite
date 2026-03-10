"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { api } from "@/lib/api";

interface Signal {
  id: string;
  signal_type: string;
  payload: Record<string, string>;
  created_at: string;
}

const SIGNAL_TYPES = [
  { key: "competitor_mention", label: "Competitor Mentions" },
  { key: "churn_risk", label: "Churn Risk" },
  { key: "expansion_opportunity", label: "Expansion Signals" },
];

export default function CompetitivePage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [signals, setSignals] = useState<Record<string, Signal[]>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("competitor_mention");
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    Promise.all(
      SIGNAL_TYPES.map((t) =>
        api
          .get<Signal[]>(`/api/v1/workspaces/${workspace.id}/intelligence-signals?signal_type=${t.key}`)
          .then((data) => [t.key, data] as [string, Signal[]])
      )
    )
      .then((results) => {
        const map: Record<string, Signal[]> = {};
        results.forEach(([key, data]) => { map[key] = data; });
        setSignals(map);
      })
      .catch(() => { setError(true); })
      .finally(() => setLoading(false));
  }, [workspace]);

  const grouped = (signals[activeTab] || []).reduce<Record<string, { count: number; latest: string }>>((acc, s) => {
    const key = s.payload.competitor ?? s.payload.signal ?? "Unknown";
    if (!acc[key]) acc[key] = { count: 0, latest: s.created_at };
    acc[key].count++;
    if (s.created_at > acc[key].latest) acc[key].latest = s.created_at;
    return acc;
  }, {});

  const sorted = Object.entries(grouped).sort((a, b) => b[1].count - a[1].count);

  if (error) {
    return (
      <div className="text-center py-20 text-sm text-red-500">
        Failed to load signals. Please refresh and try again.
      </div>
    );
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
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Competitive Intelligence</h1>
      <p className="text-sm text-gray-500 mb-6">
        Signals extracted automatically from customer conversations.
      </p>

      <div className="flex gap-2 mb-6">
        {SIGNAL_TYPES.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
              activeTab === t.key
                ? "bg-gray-900 text-white"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {t.label}
            <span className="ml-1.5 text-xs opacity-70">
              ({(signals[t.key] || []).length})
            </span>
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-gray-400 text-sm">
            No {SIGNAL_TYPES.find((t) => t.key === activeTab)?.label.toLowerCase()} detected yet.
            Signals appear after conversations are analyzed.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {sorted.map(([name, { count, latest }]) => (
            <Card key={name}>
              <CardContent className="py-4 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-900">{name}</span>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Last seen {new Date(latest).toLocaleDateString()}
                  </p>
                </div>
                <Badge variant={count >= 5 ? "danger" : count >= 2 ? "warning" : "default"}>
                  {count} {count === 1 ? "signal" : "signals"}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
