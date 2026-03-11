import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getDashboardData } from "@/lib/api-functions";
import { DashboardData } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  period?: string;
}

export function MetricsDashboardPanel({ period = "30d" }: Props) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getDashboardData(workspace.id, period)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id, period]);

  if (loading)
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-5 w-5 text-primary-500" />
      </div>
    );
  if (!data) return <p className="p-4 text-sm text-gray-400">No data.</p>;

  const metrics = [
    { label: "Total Conversations", value: data.stats.total_conversations },
    { label: "Resolved", value: `${Math.round(data.resolution_rate * 100)}%` },
    { label: "Escalated", value: data.stats.escalated },
    {
      label: "Resolution Trend",
      value: `${Math.round((data.resolution_rate_trend ?? 0) * 100)}%`,
    },
  ];

  return (
    <div className="p-4">
      <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-3">
        Last {period}
      </p>
      <div className="grid grid-cols-2 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-lg border border-[#f0ebe3] bg-white p-3">
            <div className="text-[10px] text-gray-400 mb-1">{m.label}</div>
            <div className="text-xl font-black text-gray-900">{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
