"use client";

import { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import { Globe } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { CountryDataPoint } from "@/lib/types";
import { getChatsByCountry } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

function countryFlag(countryCode: string): string {
  return String.fromCodePoint(
    ...[...countryCode.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65),
  );
}

const BAR_COLOR = "#4f46e5";

export default function GeographyPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [data, setData] = useState<CountryDataPoint[]>([]);
  const [range, setRange] = useState("30d");
  const [loading, setLoading] = useState(true);

  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getChatsByCountry(workspace.id, days)
      .then((r) => setData(r.data ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [workspace, days]);

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
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chats by Country</h1>
          <p className="text-sm text-gray-500 mt-1">
            Where your users are coming from
          </p>
        </div>
        <select
          value={range}
          onChange={(e) => setRange(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
        </select>
      </div>

      {data.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <Globe className="h-10 w-10 mb-3 text-gray-300" />
            <p className="text-sm font-medium text-gray-600">No geography data yet</p>
            <p className="text-xs mt-1">
              Country data is collected when visitors start a chat. Private / local IPs are excluded.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Bar Chart */}
          <Card className="mb-6">
            <CardContent className="pt-5 pb-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-4">
                Top Countries
              </h2>
              <ResponsiveContainer
                width="100%"
                height={Math.max(200, data.length * 48)}
              >
                <BarChart
                  data={data}
                  layout="vertical"
                  margin={{ top: 4, right: 60, left: 8, bottom: 4 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    stroke="#94a3b8"
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="country_name"
                    width={160}
                    tick={{ fontSize: 12 }}
                    stroke="#94a3b8"
                  />
                  <Tooltip
                    formatter={(value) => [value, "Conversations"]}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {data.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={BAR_COLOR} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Table */}
          <Card>
            <CardContent className="pt-5 pb-2">
              <h2 className="text-sm font-semibold text-gray-900 mb-4">
                Breakdown
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Flag
                    </th>
                    <th className="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Country
                    </th>
                    <th className="text-right py-2 px-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Conversations
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => (
                    <tr
                      key={row.country_code}
                      className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      <td className="py-2.5 px-2 text-lg">
                        {countryFlag(row.country_code)}
                      </td>
                      <td className="py-2.5 px-2 text-gray-900 font-medium">
                        {row.country_name}
                        <span className="ml-2 text-xs text-gray-400 font-normal">
                          ({row.country_code})
                        </span>
                      </td>
                      <td className="py-2.5 px-2 text-right tabular-nums font-semibold text-gray-900">
                        {row.count.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
