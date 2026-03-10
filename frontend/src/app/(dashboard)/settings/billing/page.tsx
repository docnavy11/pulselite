"use client";

import { useState, useEffect } from "react";
import { Check } from "lucide-react";
import { clsx } from "clsx";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { BillingPlan, CreditBalance, UsageBreakdown } from "@/lib/types";
import {
  getBillingPlans,
  createCheckoutSession,
  createPortalSession,
  getCreditsBalance,
  getAutoRecharge,
  updateAutoRecharge,
  getUsageBreakdown,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function BillingPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [credits, setCredits] = useState<CreditBalance | null>(null);
  const [usage, setUsage] = useState<UsageBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [interval, setInterval] = useState<"monthly" | "annual">("monthly");
  const [autoRecharge, setAutoRecharge] = useState({
    enabled: false, threshold: 200, amount: 1000,
  });
  const [savingAutoRecharge, setSavingAutoRecharge] = useState(false);
  useEffect(() => {
    const promises: Promise<unknown>[] = [
      getBillingPlans().then(setPlans),
    ];
    if (workspace) {
      promises.push(getCreditsBalance(workspace.id).then(setCredits));
      promises.push(getUsageBreakdown(workspace.id).then(setUsage).catch(() => {}));
    }
    Promise.all(promises)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  useEffect(() => {
    if (!workspace) return;
    getAutoRecharge(workspace.id).then((data) => {
      setAutoRecharge({
        enabled: data.auto_recharge_enabled,
        threshold: data.auto_recharge_threshold,
        amount: data.auto_recharge_amount,
      });
    }).catch(() => {});
  }, [workspace]);

  async function handleUpgrade(planId: string) {
    if (!workspace) return;
    try {
      const { url } = await createCheckoutSession(workspace.id, planId, interval);
      if (url && (url.startsWith('https://checkout.stripe.com') || url.startsWith('https://billing.stripe.com'))) {
        window.location.href = url;
      } else {
        console.error('Invalid redirect URL');
      }
    } catch {
      // handle error
    }
  }

  async function handleSaveAutoRecharge() {
    if (!workspace) return;
    setSavingAutoRecharge(true);
    try {
      await updateAutoRecharge(workspace.id, {
        auto_recharge_enabled: autoRecharge.enabled,
        auto_recharge_threshold: autoRecharge.threshold,
        auto_recharge_amount: autoRecharge.amount,
      });
    } finally {
      setSavingAutoRecharge(false);
    }
  }

  async function handleManage() {
    if (!workspace) return;
    try {
      const { url } = await createPortalSession(workspace.id);
      if (url && (url.startsWith('https://checkout.stripe.com') || url.startsWith('https://billing.stripe.com'))) {
        window.location.href = url;
      } else {
        console.error('Invalid redirect URL');
      }
    } catch {
      // handle error
    }
  }

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
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        <Button variant="secondary" onClick={handleManage}>
          Manage Subscription
        </Button>
      </div>

      {/* Current plan */}
      <Card className="mb-8">
        <CardContent className="py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Current Plan</p>
              <p className="text-xl font-bold text-gray-900 capitalize">
                {workspace?.plan || "Free"}
              </p>
            </div>
            {credits && (
              <div className="text-right">
                <p className="text-sm text-gray-500">Credits Balance</p>
                <p className="text-xl font-bold text-gray-900">
                  {credits.balance.toLocaleString()}
                </p>
                <p className="text-xs text-gray-400">
                  {credits.usage_this_month.toLocaleString()} used this month
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Billing interval toggle */}
      <div className="flex justify-center mb-6">
        <div className="flex items-center gap-1 rounded-xl bg-gray-100 p-1">
          <button
            onClick={() => setInterval("monthly")}
            className={clsx(
              "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200",
              interval === "monthly"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700",
            )}
          >
            Monthly
          </button>
          <button
            onClick={() => setInterval("annual")}
            className={clsx(
              "px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2",
              interval === "annual"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700",
            )}
          >
            Annual
            <span className="rounded-full bg-green-100 text-green-700 text-[10px] font-semibold px-1.5 py-0.5">
              20% off
            </span>
          </button>
        </div>
      </div>

      {/* Plans grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => {
          const displayPrice = interval === "annual" && plan.price > 0
            ? Math.round(plan.price * 0.8)
            : plan.price;
          return (
            <Card
              key={plan.id}
              className={clsx(
                "relative",
                plan.is_popular && "ring-2 ring-primary-500",
              )}
            >
              {plan.is_popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary-500 px-3 py-0.5 text-[11px] font-medium text-white">
                  Most Popular
                </div>
              )}
              <CardContent className="pt-8 pb-6">
                <h3 className="text-lg font-semibold text-gray-900">
                  {plan.name}
                </h3>
                <div className="mt-2 mb-4">
                  <span className="text-3xl font-bold text-gray-900">
                    ${displayPrice}
                  </span>
                  <span className="text-sm text-gray-500">/mo</span>
                  {interval === "annual" && plan.price > 0 && (
                    <p className="text-xs text-green-600 font-medium mt-0.5">
                      ${Math.round(plan.price * 0.8 * 12)}/yr · save ${Math.round(plan.price * 0.2 * 12)}
                    </p>
                  )}
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-2 text-sm text-gray-600"
                    >
                      <Check className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Button
                  className="w-full"
                  variant={plan.is_popular ? "primary" : "secondary"}
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={workspace?.plan === plan.name.toLowerCase()}
                >
                  {workspace?.plan === plan.name.toLowerCase()
                    ? "Current Plan"
                    : "Upgrade"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Usage & Costs */}
      {usage && (
        <Card className="mt-8">
          <CardContent className="pt-6">
            <h3 className="text-base font-semibold text-gray-900 mb-1">Usage &amp; Costs</h3>
            <p className="text-sm text-gray-500 mb-5">
              Last 30 days — token estimates based on AI response length.
            </p>

            {/* Summary stats */}
            <div className="flex gap-8 mb-6">
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Total Tokens</p>
                <p className="text-2xl font-bold text-gray-900">
                  {usage.total_tokens.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Estimated Cost</p>
                <p className="text-2xl font-bold text-gray-900">
                  ${usage.total_cost_usd.toFixed(4)}
                </p>
              </div>
            </div>

            {/* Daily bar chart */}
            {usage.daily.length > 0 && (
              <div className="mb-6">
                <p className="text-xs font-medium text-gray-500 mb-2">Daily Token Usage</p>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={usage.daily} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(v) => {
                        const d = new Date(v);
                        return `${d.getMonth() + 1}/${d.getDate()}`;
                      }}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 10 }} width={40} />
                    <Tooltip
                      formatter={(value) => [
                        `${Number(value).toLocaleString()} tokens`,
                        "Tokens",
                      ]}
                      labelFormatter={(label) => `Date: ${label}`}
                    />
                    <Bar dataKey="tokens" fill="#6366f1" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Breakdown table */}
            {usage.breakdown.length > 0 ? (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-2">Model Breakdown</p>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Model</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Provider</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Tokens</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Est. Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {usage.breakdown.map((row) => (
                        <tr key={row.model} className="hover:bg-gray-50">
                          <td className="px-4 py-2 font-mono text-xs text-gray-800">{row.model}</td>
                          <td className="px-4 py-2 text-gray-600 capitalize">{row.provider}</td>
                          <td className="px-4 py-2 text-right text-gray-800">{row.tokens.toLocaleString()}</td>
                          <td className="px-4 py-2 text-right text-gray-800">${row.cost_usd.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic">No AI usage recorded in this period.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Auto-recharge */}
      <Card className="mt-8">
        <CardContent className="pt-6">
          <h3 className="text-base font-semibold text-gray-900 mb-4">Auto-recharge Credits</h3>
          <p className="text-sm text-gray-500 mb-4">
            Automatically top up your credits when your balance falls below a threshold.
            Requires an active paid subscription.
          </p>
          <div className="space-y-4">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRecharge.enabled}
                onChange={(e) => setAutoRecharge(prev => ({ ...prev, enabled: e.target.checked }))}
                className="h-4 w-4 rounded border-gray-300 text-primary-500"
              />
              <span className="text-sm font-medium text-gray-700">Enable auto-recharge</span>
            </label>
            {autoRecharge.enabled && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Recharge when balance drops below (credits)
                  </label>
                  <input
                    type="number"
                    min="50"
                    step="50"
                    value={autoRecharge.threshold}
                    onChange={(e) => setAutoRecharge(prev => ({ ...prev, threshold: Number(e.target.value) }))}
                    className="w-40 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Add this many credits ($0.04/credit)
                  </label>
                  <select
                    value={autoRecharge.amount}
                    onChange={(e) => setAutoRecharge(prev => ({ ...prev, amount: Number(e.target.value) }))}
                    className="w-40 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value={500}>500 credits — $20</option>
                    <option value={1000}>1,000 credits — $40</option>
                    <option value={2500}>2,500 credits — $100</option>
                    <option value={5000}>5,000 credits — $200</option>
                  </select>
                </div>
              </>
            )}
            <Button onClick={handleSaveAutoRecharge} loading={savingAutoRecharge} size="sm">
              Save settings
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
