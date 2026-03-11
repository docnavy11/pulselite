"use client";

import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getCreditsBalance } from "@/lib/api-functions";
import { CreditBalance } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

export function CreditBalancePanel(_props: Record<string, unknown>) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [balance, setBalance] = useState<CreditBalance | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getCreditsBalance(workspace.id)
      .then(setBalance)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id]);

  if (loading)
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-5 w-5 text-primary-500" />
      </div>
    );
  if (!balance)
    return <p className="p-4 text-sm text-gray-400">Could not load credits.</p>;

  return (
    <div className="p-4">
      <div className="space-y-3">
        <div className="rounded-lg border border-[#f0ebe3] bg-white p-3">
          <div className="text-[10px] text-gray-400 mb-1">Balance</div>
          <div className="text-2xl font-black text-primary-500">
            {balance.balance.toLocaleString()}
          </div>
          <div className="text-xs text-gray-400">credits remaining</div>
        </div>
        <div className="rounded-lg border border-[#f0ebe3] bg-white p-3">
          <div className="text-[10px] text-gray-400 mb-1">Used this month</div>
          <div className="text-xl font-black text-gray-900">
            {balance.usage_this_month.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}
