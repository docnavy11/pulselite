import { useState, useEffect, useCallback, useRef } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getSystemHealth, getServerLogs, getAuditLogs, getRetrievalLogs } from "@/lib/api-functions";

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function truncate(str: string, max = 80): string {
  return str.length > max ? str.slice(0, max) + "\u2026" : str;
}

// ── System Health tab ────────────────────────────────────────────────────────

/* eslint-disable @typescript-eslint/no-explicit-any */

function SystemHealthTab({ workspaceId }: { workspaceId: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await getSystemHealth(workspaceId);
      setData(result);
      setError(null);
    } catch (_e) {
      setError("Failed to load system health.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    setLoading(true);
    fetchData();
    intervalRef.current = setInterval(fetchData, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  if (loading) return <p className="p-6 text-sm text-gray-500">Loading...</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={fetchData}>Retry</button>
    </div>
  );
  if (!data) return null;

  const db = data.database ?? {};
  const redis = data.redis ?? {};
  const system = data.system ?? {};
  const storage = data.storage ?? {};

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">Auto-refreshes every 30 seconds</span>
        <button
          onClick={fetchData}
          className="text-xs text-blue-600 hover:underline"
        >
          Refresh now
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Database */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${db.connected ? "bg-green-500" : "bg-red-500"}`} />
            <h3 className="text-sm font-medium text-gray-700">Database</h3>
          </div>
          <div className="space-y-1.5 text-xs text-gray-600">
            <div className="flex justify-between"><span>Status</span><span className="font-medium">{db.connected ? "Connected" : "Disconnected"}</span></div>
            {db.pool_size != null && <div className="flex justify-between"><span>Pool size</span><span>{db.pool_size}</span></div>}
            {db.pool_checked_in != null && <div className="flex justify-between"><span>Checked in</span><span>{db.pool_checked_in}</span></div>}
            {db.pool_checked_out != null && <div className="flex justify-between"><span>Checked out</span><span>{db.pool_checked_out}</span></div>}
            {db.pool_overflow != null && <div className="flex justify-between"><span>Overflow</span><span>{db.pool_overflow}</span></div>}
          </div>
        </div>

        {/* Redis */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${redis.connected ? "bg-green-500" : "bg-red-500"}`} />
            <h3 className="text-sm font-medium text-gray-700">Redis</h3>
          </div>
          <div className="space-y-1.5 text-xs text-gray-600">
            <div className="flex justify-between"><span>Status</span><span className="font-medium">{redis.connected ? "Connected" : "Disconnected"}</span></div>
            {redis.used_memory_human && <div className="flex justify-between"><span>Memory</span><span>{redis.used_memory_human}</span></div>}
            {redis.connected_clients != null && <div className="flex justify-between"><span>Clients</span><span>{redis.connected_clients}</span></div>}
            {redis.uptime_in_seconds != null && <div className="flex justify-between"><span>Uptime</span><span>{Math.floor(redis.uptime_in_seconds / 3600)}h</span></div>}
          </div>
        </div>

        {/* System */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
            <h3 className="text-sm font-medium text-gray-700">System</h3>
          </div>
          <div className="space-y-1.5 text-xs text-gray-600">
            {system.python_version && <div className="flex justify-between"><span>Python</span><span>{system.python_version}</span></div>}
            {system.uptime && <div className="flex justify-between"><span>Uptime</span><span>{system.uptime}</span></div>}
            {system.hostname && <div className="flex justify-between"><span>Host</span><span className="truncate max-w-[200px]">{system.hostname}</span></div>}
            {system.pid != null && <div className="flex justify-between"><span>PID</span><span>{system.pid}</span></div>}
          </div>
        </div>

        {/* Storage */}
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" />
            <h3 className="text-sm font-medium text-gray-700">Storage</h3>
          </div>
          <div className="space-y-1.5 text-xs text-gray-600">
            {storage.documents != null && <div className="flex justify-between"><span>Documents</span><span>{storage.documents.toLocaleString()}</span></div>}
            {storage.chunks != null && <div className="flex justify-between"><span>Chunks</span><span>{storage.chunks.toLocaleString()}</span></div>}
            {storage.conversations != null && <div className="flex justify-between"><span>Conversations</span><span>{storage.conversations.toLocaleString()}</span></div>}
            {storage.chatbots != null && <div className="flex justify-between"><span>Chatbots</span><span>{storage.chatbots}</span></div>}
            {storage.knowledge_bases != null && <div className="flex justify-between"><span>Knowledge bases</span><span>{storage.knowledge_bases}</span></div>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Server Logs tab ──────────────────────────────────────────────────────────

const LOG_LEVEL_COLORS: Record<string, string> = {
  ERROR:   "text-red-600 bg-red-50",
  WARNING: "text-yellow-700 bg-yellow-50",
  INFO:    "text-blue-600 bg-blue-50",
  DEBUG:   "text-gray-500 bg-gray-50",
};

function ServerLogsTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string>("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getServerLogs(workspaceId, 100, levelFilter || undefined);
      setItems(Array.isArray(result) ? result : (result as any).items ?? []);
      setError(null);
    } catch (_e) {
      setError("Failed to load server logs.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, levelFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-primary-500"
        >
          <option value="">All levels</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
        <button
          onClick={fetchData}
          className="text-xs text-blue-600 hover:underline"
        >
          Refresh
        </button>
      </div>

      {loading && items.length === 0 && <p className="p-6 text-sm text-gray-500">Loading...</p>}
      {error && (
        <div className="p-6 text-sm text-red-500">
          {error} <button className="underline ml-2" onClick={fetchData}>Retry</button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="p-6 text-sm text-gray-400">No log entries found.</p>
      )}

      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {["Timestamp", "Level", "Logger", "Message"].map(h => (
                  <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((log: any, i: number) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap font-mono">
                    {log.timestamp ? formatTimestamp(log.timestamp) : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${LOG_LEVEL_COLORS[log.level] ?? "text-gray-600 bg-gray-50"}`}>
                      {log.level}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-500 text-xs font-mono max-w-[200px] truncate">
                    {log.logger ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-gray-700 text-xs font-mono max-w-[500px]">
                    {log.message ? (
                      <span title={log.message} className="cursor-help">
                        {truncate(log.message, 120)}
                      </span>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Audit Trail tab ──────────────────────────────────────────────────────────

function AuditTrailTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    try {
      setLoading(true);
      const result = await getAuditLogs(workspaceId, 50, currentOffset);
      const data = result as any;
      const newItems = Array.isArray(data) ? data : (data.items ?? []);
      const newTotal = data.total ?? newItems.length;
      setItems(prev => append ? [...prev, ...newItems] : newItems);
      setTotal(newTotal);
      setError(null);
    } catch (_e) {
      setError("Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { fetchPage(0); }, [fetchPage]);

  if (loading && items.length === 0) return <p className="p-6 text-sm text-gray-500">Loading...</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={() => fetchPage(0)}>Retry</button>
    </div>
  );
  if (items.length === 0) return <p className="p-6 text-sm text-gray-400">No audit entries yet.</p>;

  return (
    <div>
      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} entries
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Timestamp", "User", "Action", "Resource Type", "Resource ID", "IP Address"].map(h => (
                <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((entry: any, i: number) => (
              <tr key={entry.id ?? i} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                  {entry.timestamp ? formatTimestamp(entry.timestamp) : entry.created_at ? formatRelative(entry.created_at) : "—"}
                </td>
                <td className="px-4 py-2 text-gray-700 text-xs">
                  {entry.user_email ?? entry.user ?? "—"}
                </td>
                <td className="px-4 py-2">
                  <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                    {entry.action ?? "—"}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-600 text-xs">
                  {entry.resource_type ?? "—"}
                </td>
                <td className="px-4 py-2 text-gray-500 text-xs font-mono">
                  {entry.resource_id ? truncate(entry.resource_id, 20) : "—"}
                </td>
                <td className="px-4 py-2 text-gray-400 text-xs">
                  {entry.ip_address ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length < total && (
        <div className="px-4 py-3">
          <button
            className="text-sm text-blue-600 hover:underline"
            onClick={() => {
              const next = offset + 50;
              setOffset(next);
              fetchPage(next, true);
            }}
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

// ── Retrieval Logs tab ───────────────────────────────────────────────────────

function RetrievalLogsTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    try {
      setLoading(true);
      const result = await getRetrievalLogs(workspaceId, 50, currentOffset);
      const data = result as any;
      const newItems = Array.isArray(data) ? data : (data.items ?? []);
      const newTotal = data.total ?? newItems.length;
      setItems(prev => append ? [...prev, ...newItems] : newItems);
      setTotal(newTotal);
      setError(null);
    } catch (_e) {
      setError("Failed to load retrieval logs.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { fetchPage(0); }, [fetchPage]);

  if (loading && items.length === 0) return <p className="p-6 text-sm text-gray-500">Loading...</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={() => fetchPage(0)}>Retry</button>
    </div>
  );
  if (items.length === 0) return <p className="p-6 text-sm text-gray-400">No retrieval logs yet.</p>;

  return (
    <div>
      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} entries
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Timestamp", "Chatbot", "Query", "Confidence", "Chunks", "Escalated", "Duration"].map(h => (
                <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((entry: any, i: number) => (
              <tr key={entry.id ?? i} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                  {entry.timestamp ? formatTimestamp(entry.timestamp) : entry.created_at ? formatRelative(entry.created_at) : "—"}
                </td>
                <td className="px-4 py-2 text-gray-700 text-xs">
                  {entry.chatbot_name ?? entry.chatbot_id ?? "—"}
                </td>
                <td className="px-4 py-2 text-gray-600 text-xs max-w-[250px]">
                  {entry.query ? (
                    <span title={entry.query} className="cursor-help">
                      {truncate(entry.query, 60)}
                    </span>
                  ) : "—"}
                </td>
                <td className="px-4 py-2">
                  {entry.confidence_score != null ? (
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      entry.confidence_score >= 0.7
                        ? "bg-green-100 text-green-700"
                        : entry.confidence_score >= 0.4
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-red-100 text-red-700"
                    }`}>
                      {entry.confidence_score.toFixed(2)}
                    </span>
                  ) : <span className="text-xs text-gray-400">—</span>}
                </td>
                <td className="px-4 py-2 text-gray-600 text-xs">
                  {entry.chunks_used ?? entry.chunk_count ?? "—"}
                </td>
                <td className="px-4 py-2">
                  {entry.escalated != null ? (
                    entry.escalated ? (
                      <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Yes</span>
                    ) : (
                      <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">No</span>
                    )
                  ) : <span className="text-xs text-gray-400">—</span>}
                </td>
                <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                  {entry.duration_ms != null
                    ? entry.duration_ms < 1000
                      ? `${entry.duration_ms}ms`
                      : `${(entry.duration_ms / 1000).toFixed(1)}s`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length < total && (
        <div className="px-4 py-3">
          <button
            className="text-sm text-blue-600 hover:underline"
            onClick={() => {
              const next = offset + 50;
              setOffset(next);
              fetchPage(next, true);
            }}
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

/* eslint-enable @typescript-eslint/no-explicit-any */

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const workspace = useWorkspaceStore(s => s.currentWorkspace);
  const [tab, setTab] = useState<"health" | "server-logs" | "audit" | "retrievals">("health");
  const [accessError, setAccessError] = useState(false);

  // Try loading system health to check access — if 403, show access denied
  useEffect(() => {
    if (!workspace) return;
    getSystemHealth(workspace.id).catch((e: any) => {
      if (e?.status === 403) setAccessError(true);
    });
  }, [workspace]);

  if (!workspace) return <p className="p-6 text-sm text-gray-400">Loading workspace...</p>;

  if (accessError) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-6 py-4 border-b border-gray-200">
          <h1 className="text-xl font-semibold text-gray-900">Admin</h1>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-gray-400 mb-2">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0110 0v4" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-gray-700 mb-1">Admin access required</h2>
            <p className="text-sm text-gray-500">You need admin privileges to view this page.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Admin</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-200 px-6">
        {(["health", "server-logs", "audit", "retrievals"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {{ health: "System Health", "server-logs": "Server Logs", audit: "Audit Trail", retrievals: "Retrieval Logs" }[t]}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        {tab === "health" && <SystemHealthTab workspaceId={workspace.id} />}
        {tab === "server-logs" && <ServerLogsTab workspaceId={workspace.id} />}
        {tab === "audit" && <AuditTrailTab workspaceId={workspace.id} />}
        {tab === "retrievals" && <RetrievalLogsTab workspaceId={workspace.id} />}
      </div>
    </div>
  );
}
