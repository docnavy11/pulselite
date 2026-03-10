"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  SortingState,
} from "@tanstack/react-table";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Contact } from "@/lib/types";
import { getLeads } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const tierColors: Record<string, string> = {
  hot: "bg-red-100 text-red-700",
  warm: "bg-amber-100 text-amber-700",
  cold: "bg-blue-100 text-blue-700",
};

const columnHelper = createColumnHelper<Contact>();

export default function LeadsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [leads, setLeads] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [tierFilter, setTierFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "lead_score", desc: true },
  ]);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getLeads(workspace.id, tierFilter ? { tier: tierFilter } : {})
      .then(setLeads)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, tierFilter]);

  const columns = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Contact",
        cell: (info) => (
          <div>
            <p className="font-medium text-gray-900">
              {info.getValue() || "Anonymous"}
            </p>
            <p className="text-xs text-gray-500">
              {info.row.original.email || ""}
            </p>
          </div>
        ),
      }),
      columnHelper.accessor("lead_score", {
        header: "Score",
        cell: (info) => {
          const score = info.getValue();
          const pct = Math.min(score, 100);
          const color =
            score >= 70
              ? "bg-red-500"
              : score >= 40
                ? "bg-amber-500"
                : "bg-blue-500";
          return (
            <div className="flex items-center gap-2">
              <div className="w-16 h-2 rounded-full bg-gray-200">
                <div
                  className={`h-2 rounded-full ${color}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-sm font-semibold">{score}</span>
            </div>
          );
        },
      }),
      columnHelper.accessor("lead_tier", {
        header: "Tier",
        cell: (info) => {
          const tier = info.getValue();
          if (!tier) return <span className="text-gray-400">-</span>;
          return (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${tierColors[tier] || "bg-gray-100 text-gray-600"}`}
            >
              {tier}
            </span>
          );
        },
      }),
      columnHelper.accessor("contact_type", {
        header: "Type",
        cell: (info) => (
          <span className="text-sm text-gray-500 capitalize">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("created_at", {
        header: "Since",
        cell: (info) => (
          <span className="text-sm text-gray-500">
            {new Date(info.getValue()).toLocaleDateString()}
          </span>
        ),
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: leads,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

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
        <h1 className="text-2xl font-bold text-gray-900">Lead Feed</h1>
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">All tiers</option>
          <option value="hot">Hot</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </select>
      </div>

      {leads.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-gray-400">
            <Users className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No leads scored yet</p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr
                  key={hg.id}
                  className="border-b border-gray-200 bg-gray-50"
                >
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="text-left px-4 py-3 font-medium text-gray-500 cursor-pointer select-none hover:text-gray-700"
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {header.column.getIsSorted() === "asc" && " ↑"}
                        {header.column.getIsSorted() === "desc" && " ↓"}
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() =>
                    router.push(
                      `/intelligence/leads/${row.original.id}`,
                    )
                  }
                  className="border-b border-gray-100 last:border-0 cursor-pointer hover:bg-gray-50 transition-all duration-200"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
