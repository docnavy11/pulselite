import { useState, useEffect, useRef, useCallback } from "react";
import { Check, AlertTriangle, Minus, ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getCrawlRunLogs, getDocumentLogs } from "@/lib/api-functions";
import type { CrawlRunLogItem, DocumentLogItem, IngestionStep } from "@/lib/types";

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

function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return "—";
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime();
  if (ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function truncateUrl(url: string, max = 40): string {
  try {
    const { hostname, pathname } = new URL(url);
    const full = hostname + pathname;
    return full.length > max ? full.slice(0, max) + "…" : full;
  } catch (_e) {
    return url.length > max ? url.slice(0, max) + "…" : url;
  }
}

const STATUS_BADGE: Record<string, string> = {
  pending:    "bg-gray-100 text-gray-600",
  running:    "bg-blue-100 text-blue-700",
  processing: "bg-blue-100 text-blue-700",
  completed:  "bg-green-100 text-green-700",
  indexed:    "bg-green-100 text-green-700",
  failed:     "bg-red-100 text-red-700",
  skipped:    "bg-yellow-100 text-yellow-700",
};

const STEP_LABELS: Record<string, string> = {
  extract:         "Extract content",
  budget_check:    "Character budget",
  chunk:           "Chunk text",
  embed:           "Generate embeddings",
  index:           "Store vectors",
  extract_sources: "Discover sources",
  fan_out:         "Queue child documents",
};

// ── Step timeline ─────────────────────────────────────────────────────────────

function StepTimeline({ steps, errorMessage, status }: {
  steps: IngestionStep[] | null;
  errorMessage: string | null;
  status: string;
}) {
  if (!steps) {
    return (
      <p className="text-xs text-gray-400 italic px-3 py-2">
        No step data recorded for this document.
      </p>
    );
  }
  return (
    <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
      {status === "failed" && errorMessage && (
        <div className="mb-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {errorMessage}
        </div>
      )}
      <div className="space-y-0">
        {steps.map((s, i) => (
          <div key={i} className="flex items-start gap-3 py-1.5">
            <div className="flex-shrink-0 mt-0.5">
              {s.status === "ok" && (
                <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center">
                  <Check className="h-3 w-3 text-green-600" />
                </div>
              )}
              {s.status === "failed" && (
                <AlertTriangle className="h-4 w-4 text-red-500" />
              )}
              {s.status === "skipped" && (
                <div className="h-5 w-5 rounded-full bg-yellow-100 flex items-center justify-center">
                  <Minus className="h-3 w-3 text-yellow-600" />
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-gray-700">
                  {STEP_LABELS[s.step] ?? s.step}
                </span>
                <span className="text-xs text-gray-400">{s.duration_ms}ms</span>
              </div>
              {s.detail && <p className="text-xs text-gray-500 mt-0.5">{s.detail}</p>}
              {s.error && <p className="text-xs text-red-500 mt-0.5">{s.error}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Crawl Runs tab ────────────────────────────────────────────────────────────

function CrawlRunsTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<CrawlRunLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasActive = (rows: CrawlRunLogItem[]) =>
    rows.some(r => r.status === "running" || r.status === "pending");

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const data = await getCrawlRunLogs(workspaceId, 50, currentOffset);
      if (ctrl.signal.aborted) return;
      setItems(prev => {
        const newItems = append ? [...prev, ...data.items] : data.items;
        // Manage polling based on updated items
        if (hasActive(newItems) && !intervalRef.current) {
          intervalRef.current = setInterval(() => fetchPage(0), 5000);
        } else if (!hasActive(newItems) && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        return newItems;
      });
      setTotal(data.total);
      setError(null);
    } catch (_e) {
      if (!ctrl.signal.aborted) setError("Failed to load crawl runs.");
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    setLoading(true);
    fetchPage(0);
    return () => {
      abortRef.current?.abort();
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    };
  }, [fetchPage]);

  if (loading) return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={() => fetchPage(0)}>Retry</button>
    </div>
  );
  if (items.length === 0) return <p className="p-6 text-sm text-gray-400">No crawl runs yet.</p>;

  return (
    <div>
      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} runs
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {["Chatbot","URL","Status","Pages","Failed","Indexed (KB)","Error","Started","Duration"].map(h => (
                <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map(job => (
              <tr key={job.job_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-gray-700">{job.chatbot_name ?? "—"}</td>
                <td className="px-4 py-2">
                  <a href={job.root_url} target="_blank" rel="noreferrer"
                     className="text-blue-600 hover:underline flex items-center gap-1">
                    {truncateUrl(job.root_url)}
                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                  </a>
                </td>
                <td className="px-4 py-2">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[job.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {(job.status === "running" || job.status === "processing") && (
                      <span className="inline-block h-2 w-2 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                    )}
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {job.pages_queued}/{job.pages_discovered}
                </td>
                <td className="px-4 py-2">
                  {job.pages_failed > 0
                    ? <span className="text-red-600">{job.pages_failed}</span>
                    : "—"}
                </td>
                <td className="px-4 py-2 text-gray-600">{job.docs_indexed}</td>
                <td className="px-4 py-2 text-gray-500 max-w-[200px]">
                  {job.error_message ? (
                    <span title={job.error_message} className="text-red-500 cursor-help">
                      {job.error_message.slice(0, 60)}{job.error_message.length > 60 ? "…" : ""}
                    </span>
                  ) : "—"}
                </td>
                <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                  {formatRelative(job.started_at ?? job.created_at)}
                </td>
                <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                  {formatDuration(job.started_at, job.completed_at)}
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

// ── Documents tab ─────────────────────────────────────────────────────────────

function DocumentsTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<DocumentLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    try {
      const data = await getDocumentLogs(workspaceId, 50, currentOffset);
      setItems(prev => append ? [...prev, ...data.items] : data.items);
      setTotal(data.total);
      setError(null);
    } catch (_e) {
      setError("Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { fetchPage(0); }, [fetchPage]);

  const toggleExpand = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  if (loading) return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={() => fetchPage(0)}>Retry</button>
    </div>
  );
  if (items.length === 0) return <p className="p-6 text-sm text-gray-400">No documents yet.</p>;

  return (
    <div>
      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} documents
      </div>
      <div className="divide-y divide-gray-100">
        {items.map(doc => {
          const isOpen = expanded.has(doc.id);
          const displayTitle = doc.title || (doc.source_url ? truncateUrl(doc.source_url) : doc.id);
          return (
            <div key={doc.id}>
              <button
                className="w-full text-left hover:bg-gray-50 transition-colors"
                onClick={() => toggleExpand(doc.id)}
              >
                <div className="grid grid-cols-9 gap-2 px-4 py-2.5 text-sm items-center">
                  <div className="col-span-2 flex items-center gap-2 min-w-0">
                    {isOpen
                      ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
                      : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />}
                    <span className="truncate text-gray-800">{displayTitle}</span>
                  </div>
                  <div>
                    {doc.source_url ? (
                      <a href={doc.source_url} target="_blank" rel="noreferrer"
                         className="text-blue-600 hover:underline flex items-center gap-0.5 text-xs truncate"
                         onClick={e => e.stopPropagation()}>
                        {truncateUrl(doc.source_url, 24)}
                        <ExternalLink className="h-3 w-3 flex-shrink-0" />
                      </a>
                    ) : "—"}
                  </div>
                  <div>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                      {doc.source_type}
                    </span>
                  </div>
                  <div className="truncate text-gray-500 text-xs">{doc.knowledge_base_name}</div>
                  <div className="truncate text-gray-500 text-xs">{doc.chatbot_name ?? "—"}</div>
                  <div>
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[doc.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {doc.status}
                    </span>
                  </div>
                  <div className="text-gray-500 text-xs">{doc.chunk_count}</div>
                  <div className="text-gray-400 text-xs whitespace-nowrap">
                    {doc.last_indexed_at ? formatRelative(doc.last_indexed_at) : "—"}
                  </div>
                </div>
              </button>
              {isOpen && (
                <StepTimeline steps={doc.ingestion_steps} errorMessage={doc.error_message} status={doc.status} />
              )}
            </div>
          );
        })}
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LogsPage() {
  const workspace = useWorkspaceStore(s => s.currentWorkspace);
  const [tab, setTab] = useState<"crawl" | "documents">("crawl");

  if (!workspace) return <p className="p-6 text-sm text-gray-400">Loading workspace…</p>;

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Logs</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-200 px-6">
        {(["crawl", "documents"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "crawl" ? "Crawl Runs" : "Documents"}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        {tab === "crawl"
          ? <CrawlRunsTab workspaceId={workspace.id} />
          : <DocumentsTab workspaceId={workspace.id} />
        }
      </div>
    </div>
  );
}
