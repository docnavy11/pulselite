import { useState, useEffect, useRef, useCallback } from "react";
import { Check, AlertTriangle, Minus, ExternalLink, ChevronDown, ChevronRight } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getCrawlRunLogs, getDocumentLogs, getAnalysisRunLogs, getBackgroundTaskLogs, getWorkerHealth } from "@/lib/api-functions";
import type { CrawlRunLogItem, DocumentLogItem, IngestionStep, AnalysisRunLogItem, BackgroundTaskLogItem, WorkerHealth, WorkerHealthTaskPerf } from "@/lib/types";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

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

// ── Analysis Runs tab ────────────────────────────────────────────────────────

const SENTIMENT_BADGE: Record<string, string> = {
  positive: "bg-green-100 text-green-700",
  neutral:  "bg-gray-100 text-gray-600",
  negative: "bg-red-100 text-red-700",
  mixed:    "bg-yellow-100 text-yellow-700",
};

const OUTCOME_BADGE: Record<string, string> = {
  resolved:  "bg-green-100 text-green-700",
  unresolved: "bg-yellow-100 text-yellow-700",
  escalated: "bg-red-100 text-red-700",
  abandoned: "bg-gray-100 text-gray-600",
};

function AnalysisRunsTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<AnalysisRunLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    try {
      const data = await getAnalysisRunLogs(workspaceId, 50, currentOffset);
      setItems(prev => append ? [...prev, ...data.items] : data.items);
      setTotal(data.total);
      setError(null);
    } catch (_e) {
      setError("Failed to load analysis runs.");
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
  if (items.length === 0) return <p className="p-6 text-sm text-gray-400">No analysis runs yet.</p>;

  return (
    <div>
      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} analysis runs
      </div>
      <div className="divide-y divide-gray-100">
        {items.map(run => {
          const isOpen = expanded.has(run.id);
          return (
            <div key={run.id}>
              <button
                className="w-full text-left hover:bg-gray-50 transition-colors"
                onClick={() => toggleExpand(run.id)}
              >
                <div className="grid grid-cols-8 gap-2 px-4 py-2.5 text-sm items-center">
                  {/* Expand icon + chatbot */}
                  <div className="col-span-2 flex items-center gap-2 min-w-0">
                    {isOpen
                      ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
                      : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />}
                    <span className="truncate text-gray-800 font-medium">
                      {run.chatbot_name ?? "Unknown bot"}
                    </span>
                  </div>
                  {/* Contact */}
                  <div className="truncate text-gray-500 text-xs">
                    {run.contact_name ?? "Anonymous"}
                  </div>
                  {/* Sentiment */}
                  <div>
                    {run.sentiment_label ? (
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${SENTIMENT_BADGE[run.sentiment_label] ?? "bg-gray-100 text-gray-600"}`}>
                        {run.sentiment_label}
                        {run.sentiment_score != null && (
                          <span className="ml-1 opacity-70">
                            {run.sentiment_score > 0 ? "+" : ""}{run.sentiment_score.toFixed(2)}
                          </span>
                        )}
                      </span>
                    ) : <span className="text-xs text-gray-400">—</span>}
                  </div>
                  {/* Outcome */}
                  <div>
                    {run.outcome_category ? (
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${OUTCOME_BADGE[run.outcome_category] ?? "bg-gray-100 text-gray-600"}`}>
                        {run.outcome_category}
                      </span>
                    ) : <span className="text-xs text-gray-400">—</span>}
                  </div>
                  {/* Intent */}
                  <div className="truncate text-gray-600 text-xs">
                    {run.intent_primary ?? "—"}
                  </div>
                  {/* Processing time */}
                  <div className="text-gray-400 text-xs">
                    {run.processing_ms != null ? `${run.processing_ms}ms` : "—"}
                  </div>
                  {/* When */}
                  <div className="text-gray-400 text-xs whitespace-nowrap">
                    {formatRelative(run.created_at)}
                  </div>
                </div>
              </button>
              {isOpen && (
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 space-y-3">
                  {run.summary && (
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Summary</span>
                      <p className="text-sm text-gray-700 mt-1">{run.summary}</p>
                    </div>
                  )}
                  {run.topics && run.topics.length > 0 && (
                    <div>
                      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Topics</span>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {run.topics.map(t => (
                          <span key={t} className="px-2 py-0.5 bg-primary-50 text-primary-700 rounded-full text-xs font-medium">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="flex gap-6 text-xs text-gray-400">
                    <span>Model: {run.llm_model}</span>
                    <span>Conversation: {run.conversation_id.slice(0, 8)}…</span>
                  </div>
                </div>
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

// ── Task name display labels ──────────────────────────────────────────────────

const TASK_LABELS: Record<string, string> = {
  compute_sentiment: "Compute Sentiment",
  cluster_gaps: "Cluster Gaps",
  analyze_conversation: "Analyze Conversation",
  analyze_all: "Analyze All Conversations",
  sync_documents: "Sync Documents",
  purge_old_data: "Purge Old Data",
  weekly_digest: "Weekly Digest",
  auto_recharge: "Auto Recharge",
  gdpr_export: "GDPR Export",
  reindex_article: "Reindex Article",
  generate_qa: "Generate Q&A",
  test_qa_question: "Test Q&A Question",
  suggest_qa_answer: "Suggest Q&A Answer",
};

// ── Background Tasks tab ─────────────────────────────────────────────────────

function BackgroundTasksTab({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<BackgroundTaskLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterName, setFilterName] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");

  const fetchPage = useCallback(async (currentOffset: number, append = false) => {
    try {
      setLoading(true);
      const data = await getBackgroundTaskLogs(
        workspaceId, 50, currentOffset,
        filterName || undefined,
        filterStatus || undefined,
      );
      setItems(prev => append ? [...prev, ...data.items] : data.items);
      setTotal(data.total);
      setError(null);
    } catch (_e) {
      setError("Failed to load task logs.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, filterName, filterStatus]);

  useEffect(() => {
    setOffset(0);
    fetchPage(0);
  }, [fetchPage]);

  if (loading && items.length === 0) return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={() => fetchPage(0)}>Retry</button>
    </div>
  );

  return (
    <div>
      {/* Filters */}
      <div className="flex gap-3 px-4 py-3 border-b border-gray-100">
        <select
          value={filterName}
          onChange={(e) => setFilterName(e.target.value)}
          className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-primary-500"
        >
          <option value="">All tasks</option>
          {Object.entries(TASK_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-primary-500"
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div className="text-xs text-gray-400 px-4 py-2">
        Showing {items.length} of {total} task runs
      </div>

      {items.length === 0 ? (
        <p className="p-6 text-sm text-gray-400">No task logs match your filters.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Task", "Status", "Detail", "Error", "Started", "Duration"].map(h => (
                    <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map(log => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-700 font-medium">
                      {TASK_LABELS[log.task_name] ?? log.task_name}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[log.status] ?? "bg-gray-100 text-gray-600"}`}>
                        {log.status === "running" && (
                          <span className="inline-block h-2 w-2 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
                        )}
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs max-w-[250px] truncate">
                      {log.detail ?? "—"}
                    </td>
                    <td className="px-4 py-2 max-w-[400px]">
                      {log.error ? (
                        <details className="text-xs text-red-500">
                          <summary className="cursor-pointer truncate">
                            {log.error.split("\n")[0].slice(0, 80)}{log.error.split("\n")[0].length > 80 ? "…" : ""}
                          </summary>
                          <pre className="mt-1 whitespace-pre-wrap break-all text-[11px] bg-red-50 border border-red-200 rounded px-2 py-1.5 max-h-40 overflow-auto">
                            {log.error}
                          </pre>
                        </details>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                      {log.started_at ? formatRelative(log.started_at) : "—"}
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                      {log.duration_ms != null ? (
                        log.duration_ms < 1000 ? `${log.duration_ms}ms` : `${(log.duration_ms / 1000).toFixed(1)}s`
                      ) : "—"}
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
        </>
      )}
    </div>
  );
}

// ── Workers tab ───────────────────────────────────────────────────────────────

function formatDurationMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function WorkersTab({ workspaceId }: { workspaceId: string }) {
  const [data, setData] = useState<WorkerHealth | null>(null);
  const [window, setWindow] = useState<"1h" | "24h" | "7d">("24h");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortCol, setSortCol] = useState<keyof WorkerHealthTaskPerf>("count");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getWorkerHealth(workspaceId, window);
      setData(result);
    } catch (_e) {
      setError("Failed to load worker health data.");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, window]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSort = (col: keyof WorkerHealthTaskPerf) => {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
  };

  const sortedTasks = data
    ? [...data.performance.by_task].sort((a, b) => {
        const av = a[sortCol] ?? -Infinity;
        const bv = b[sortCol] ?? -Infinity;
        if (typeof av === "string" && typeof bv === "string") {
          return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
        }
        return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
      })
    : [];

  const weightedAvgDuration = data?.performance.by_task.length
    ? (() => {
        const tasks = data.performance.by_task.filter(t => t.avg_duration_ms != null && t.count > 0);
        const totalCount = tasks.reduce((s, t) => s + t.count, 0);
        if (totalCount === 0) return null;
        return tasks.reduce((s, t) => s + (t.avg_duration_ms! * t.count), 0) / totalCount;
      })()
    : null;

  if (loading) return <p className="p-6 text-sm text-gray-500">Loading…</p>;
  if (error) return (
    <div className="p-6 text-sm text-red-500">
      {error} <button className="underline ml-2" onClick={fetchData}>Retry</button>
    </div>
  );
  if (!data) return null;

  const SortIcon = ({ col }: { col: keyof WorkerHealthTaskPerf }) => (
    <span className="ml-1 text-gray-400">
      {sortCol === col ? (sortDir === "asc" ? "↑" : "↓") : "↕"}
    </span>
  );

  return (
    <div>
      {/* Window toggle */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className="text-xs text-gray-400">Worker health overview</span>
        <div className="flex gap-1">
          {(["1h", "24h", "7d"] as const).map(w => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-3 py-1 text-xs font-medium rounded ${
                window === w
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 px-4 py-4 border-b border-gray-100">
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500 mb-1">Queue depth</p>
          <p className="text-2xl font-semibold text-gray-900">
            {data.queue.pending + data.queue.running}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {data.queue.pending} pending · {data.queue.running} running
          </p>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500 mb-1">Throughput / hr</p>
          <p className="text-2xl font-semibold text-gray-900">
            {data.queue.throughput_per_hour.toLocaleString()}
          </p>
          <p className="text-xs text-gray-400 mt-1">tasks completed</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500 mb-1">Failure rate</p>
          <p className={`text-2xl font-semibold ${data.reliability.failure_rate_pct > 5 ? "text-red-600" : "text-gray-900"}`}>
            {data.reliability.failure_rate_pct.toFixed(1)}%
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {data.reliability.failed} of {data.reliability.total} failed
          </p>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500 mb-1">Avg duration</p>
          <p className="text-2xl font-semibold text-gray-900">
            {formatDurationMs(weightedAvgDuration)}
          </p>
          <p className="text-xs text-gray-400 mt-1">weighted across tasks</p>
        </div>
      </div>

      {/* Timeseries chart */}
      <div className="px-4 py-4 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
          Task throughput ({window})
        </p>
        {data.timeseries.length === 0 ? (
          <p className="text-sm text-gray-400">No data for this window.</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.timeseries} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                tickFormatter={(v: string) => {
                  try {
                    const d = new Date(v);
                    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:00`;
                  } catch (_) { return v; }
                }}
              />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #e5e7eb" }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="completed" name="Completed" fill="#22c55e" radius={[2, 2, 0, 0]} />
              <Bar dataKey="failed" name="Failed" fill="#ef4444" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Task performance table */}
      <div className="px-4 py-4 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
          Performance by task type
        </p>
        {sortedTasks.length === 0 ? (
          <p className="text-sm text-gray-400">No task data.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {([
                    ["task_name", "Task name"],
                    ["count", "Count"],
                    ["success_rate_pct", "Success rate"],
                    ["avg_duration_ms", "Avg duration"],
                    ["p95_duration_ms", "P95 duration"],
                    ["last_failure_at", "Last failure"],
                  ] as [keyof WorkerHealthTaskPerf, string][]).map(([col, label]) => (
                    <th
                      key={col}
                      className="px-4 py-2 text-left text-xs font-medium text-gray-500 cursor-pointer hover:bg-gray-100 select-none"
                      onClick={() => handleSort(col)}
                    >
                      {label}<SortIcon col={col} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sortedTasks.map(task => (
                  <tr key={task.task_name} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-800 font-medium font-mono text-xs">
                      {task.task_name}
                    </td>
                    <td className="px-4 py-2 text-gray-600">{task.count.toLocaleString()}</td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        task.success_rate_pct >= 95
                          ? "bg-green-100 text-green-700"
                          : task.success_rate_pct >= 80
                          ? "bg-yellow-100 text-yellow-700"
                          : "bg-red-100 text-red-700"
                      }`}>
                        {task.success_rate_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600">{formatDurationMs(task.avg_duration_ms)}</td>
                    <td className="px-4 py-2 text-gray-600">{formatDurationMs(task.p95_duration_ms)}</td>
                    <td className="px-4 py-2 text-gray-400 text-xs whitespace-nowrap">
                      {task.last_failure_at ? formatRelative(task.last_failure_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Top errors */}
      {data.reliability.top_errors.length > 0 && (
        <div className="px-4 py-4">
          <p className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
            Top errors
          </p>
          <div className="space-y-2">
            {data.reliability.top_errors.map((e, i) => (
              <div key={i} className="flex items-start gap-3 text-xs">
                <span className="flex-shrink-0 px-2 py-0.5 bg-red-100 text-red-700 rounded font-medium">
                  {e.count}x
                </span>
                <span className="text-gray-500 font-mono">{e.task_name}</span>
                <span className="text-gray-700 flex-1 min-w-0 truncate">{e.error}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LogsPage() {
  const workspace = useWorkspaceStore(s => s.currentWorkspace);
  const [tab, setTab] = useState<"crawl" | "documents" | "analysis" | "tasks" | "workers">("crawl");

  if (!workspace) return <p className="p-6 text-sm text-gray-400">Loading workspace…</p>;

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">Logs</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-gray-200 px-6">
        {(["crawl", "documents", "analysis", "tasks", "workers"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {{ crawl: "Crawl Runs", documents: "Documents", analysis: "Analysis Runs", tasks: "Background Tasks", workers: "Workers" }[t]}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        {tab === "crawl" && <CrawlRunsTab workspaceId={workspace.id} />}
        {tab === "documents" && <DocumentsTab workspaceId={workspace.id} />}
        {tab === "analysis" && <AnalysisRunsTab workspaceId={workspace.id} />}
        {tab === "tasks" && <BackgroundTasksTab workspaceId={workspace.id} />}
        {tab === "workers" && <WorkersTab workspaceId={workspace.id} />}
      </div>
    </div>
  );
}
