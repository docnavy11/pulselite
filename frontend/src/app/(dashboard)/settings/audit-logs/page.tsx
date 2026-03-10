"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getAuditLogs } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { AuditLogEntry } from "@/lib/types";

const PAGE_SIZE = 50;

const ACTION_LABELS: Record<string, string> = {
  "chatbot.create": "Chatbot Created",
  "chatbot.update": "Chatbot Updated",
  "chatbot.delete": "Chatbot Deleted",
  "chatbot.duplicate": "Chatbot Duplicated",
  "knowledge_base.create": "Knowledge Base Created",
  "knowledge_base.delete": "Knowledge Base Deleted",
  "member.invite": "Member Invited",
  "member.remove": "Member Removed",
  "member.role_update": "Member Role Updated",
  "workspace.update": "Workspace Updated",
  "workspace.data_retention_update": "Data Retention Updated",
  "sso.update": "SSO Updated",
  "sso.delete": "SSO Disabled",
  "api_key.create": "API Key Created",
  "api_key.revoke": "API Key Revoked",
};

const ALL_ACTIONS = Object.keys(ACTION_LABELS);

function formatAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function AuditLogsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getAuditLogs(workspace.id, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        action: actionFilter || undefined,
      });
      setEntries(result.items);
      setTotal(result.total);
    } catch {
      setError("Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }, [workspace, page, actionFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function handleFilterChange(value: string) {
    setActionFilter(value);
    setPage(0);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
        <p className="mt-1 text-sm text-gray-500">
          A record of all admin actions taken in this workspace.
        </p>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <label htmlFor="action-filter" className="text-sm font-medium text-gray-700">
          Filter by action:
        </label>
        <select
          id="action-filter"
          value={actionFilter}
          onChange={(e) => handleFilterChange(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">All actions</option>
          {ALL_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {ACTION_LABELS[a]}
            </option>
          ))}
        </select>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Spinner className="h-8 w-8 text-primary-600" />
            </div>
          ) : error ? (
            <p className="py-10 text-center text-sm text-red-600">{error}</p>
          ) : entries.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-sm text-gray-500">No audit log entries found.</p>
              {actionFilter && (
                <p className="mt-1 text-xs text-gray-400">
                  Try clearing the action filter to see all logs.
                </p>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Timestamp</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Action</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Actor</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Resource</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">IP Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                        {formatDate(entry.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700">
                          {formatAction(entry.action)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {entry.actor_email ?? <span className="text-gray-400 italic">system</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {entry.resource_name ? (
                          <span>
                            <span className="font-medium">{entry.resource_name}</span>
                            {entry.resource_type && (
                              <span className="ml-1 text-xs text-gray-400">({entry.resource_type})</span>
                            )}
                          </span>
                        ) : entry.resource_type ? (
                          <span className="text-gray-500">{entry.resource_type}</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                        {entry.ip_address ?? <span className="text-gray-400">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {!loading && !error && total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total} entries
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
