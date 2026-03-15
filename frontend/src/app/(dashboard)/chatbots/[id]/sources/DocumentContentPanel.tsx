import { useState, useEffect } from "react";
import { ExternalLink, Copy, Check, RefreshCw, Clock, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { Spinner } from "@/components/ui/Spinner";
import { Badge } from "@/components/ui/Badge";
import { getDocumentContent } from "@/lib/api-functions";
import type { DocumentContentResponse } from "@/lib/types";

const statusVariant: Record<string, "default" | "success" | "warning" | "danger"> = {
  pending: "default",
  processing: "warning",
  indexed: "success",
  skipped: "warning",
  failed: "danger",
};

const stepStatusIcon: Record<string, typeof CheckCircle> = {
  ok: CheckCircle,
  skipped: Clock,
  failed: AlertCircle,
};

const stepStatusColor: Record<string, string> = {
  ok: "text-green-500",
  skipped: "text-gray-400",
  failed: "text-red-500",
};

interface Props {
  workspaceId: string;
  documentId: string;
  /** Incremented externally to force a refetch (e.g. after reindex). */
  refreshKey?: number;
}

export function DocumentContentPanel({ workspaceId, documentId, refreshKey }: Props) {
  const [data, setData] = useState<DocumentContentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState<"content" | "chunks" | "log">("content");
  const [copied, setCopied] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set());

  function fetchContent() {
    setLoading(true);
    setError(false);
    getDocumentContent(workspaceId, documentId)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    fetchContent();
  }, [workspaceId, documentId, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCopy() {
    if (!data?.raw_content) return;
    await navigator.clipboard.writeText(data.raw_content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function toggleChunk(index: number) {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner className="h-5 w-5 text-primary-500" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2">
        <p className="text-sm text-gray-500">Failed to load content</p>
        <button
          onClick={fetchContent}
          className="flex items-center gap-1.5 text-xs text-primary-500 hover:text-primary-600 font-medium"
        >
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      </div>
    );
  }

  // Pending / processing: show prominent status
  if (data.status === "pending" || data.status === "processing") {
    return (
      <div className="px-4 py-6 flex flex-col items-center gap-2">
        <Loader className="h-5 w-5 text-primary-400 animate-spin" />
        <p className="text-sm font-medium text-gray-600">
          {data.status === "pending" ? "Queued for processing…" : "Processing…"}
        </p>
        <p className="text-xs text-gray-400">Content will appear here once indexing completes.</p>
      </div>
    );
  }

  // Skipped documents: explain why
  if (data.status === "skipped") {
    return (
      <div className="px-4 py-4">
        <div className="rounded-md bg-amber-50 border border-amber-100 px-4 py-3 text-sm text-amber-700">
          <p className="font-medium mb-1">Not indexed — character limit reached</p>
          <p className="text-xs">This document was skipped because your workspace has reached its plan&apos;s character limit. Upgrade your plan or remove other sources to free up space.</p>
        </div>
        {data.ingestion_steps && data.ingestion_steps.length > 0 && (
          <div className="mt-3">
            <IngestionLog steps={data.ingestion_steps} />
          </div>
        )}
      </div>
    );
  }

  // Failed documents: show error, no tabs
  if (data.status === "failed") {
    return (
      <div className="px-4 py-4">
        <div className="rounded-md bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700">
          <p className="font-medium mb-1">Indexing failed</p>
          <p className="text-xs">{data.error_message || "Unknown error"}</p>
        </div>
        {data.ingestion_steps && data.ingestion_steps.length > 0 && (
          <div className="mt-3">
            <IngestionLog steps={data.ingestion_steps} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="px-4 py-4 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap text-sm">
        <span className="font-medium text-gray-800 truncate max-w-xs">
          {data.title || "Untitled"}
        </span>
        {data.source_url && (
          <a
            href={data.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-500 hover:text-primary-600 flex items-center gap-1 text-xs"
          >
            <ExternalLink className="h-3 w-3" /> Open
          </a>
        )}
        <Badge variant={statusVariant[data.status] || "default"}>
          {data.status}
        </Badge>
        <span className="text-xs text-gray-400">
          {data.char_count.toLocaleString()} chars &middot; {data.chunk_count} chunks
        </span>
        {data.last_indexed_at && (
          <span className="text-xs text-gray-400">
            &middot; indexed {new Date(data.last_indexed_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-100">
        {(["content", "chunks", "log"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-primary-500 text-primary-500"
                : "border-transparent text-gray-400 hover:text-gray-600"
            }`}
          >
            {t === "content" ? "Content" : t === "chunks" ? `Chunks (${data.chunks.length})` : "Log"}
          </button>
        ))}
      </div>

      {/* Content tab */}
      {tab === "content" && (
        data.raw_content ? (
          <div className="relative">
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 bg-white border border-gray-200 rounded px-2 py-1"
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <pre className="bg-gray-50 border border-gray-100 rounded-lg p-4 text-xs text-gray-700 overflow-auto max-h-[400px] whitespace-pre-wrap">
              {data.raw_content}
            </pre>
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4">
            Content not available for this source type
          </p>
        )
      )}

      {/* Chunks tab */}
      {tab === "chunks" && (
        data.chunks.length > 0 ? (
          <div className="space-y-2">
            {data.chunks.map((chunk) => {
              const isExpanded = expandedChunks.has(chunk.chunk_index);
              const needsTruncation = chunk.content.length > 200;
              const displayContent = isExpanded || !needsTruncation
                ? chunk.content
                : chunk.content.slice(0, 200) + "…";
              return (
                <div
                  key={chunk.id}
                  className="border border-gray-100 rounded-lg px-3 py-2.5"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-bold text-gray-400 bg-gray-100 rounded px-1.5 py-0.5">
                      #{chunk.chunk_index}
                    </span>
                    {chunk.heading_path && (
                      <span className="text-[11px] text-gray-400 truncate">
                        {chunk.heading_path}
                      </span>
                    )}
                    {chunk.token_count != null && (
                      <span className="text-[10px] text-gray-300 ml-auto shrink-0">
                        {chunk.token_count} tokens
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 whitespace-pre-wrap leading-relaxed">
                    {displayContent}
                  </p>
                  {needsTruncation && (
                    <button
                      onClick={() => toggleChunk(chunk.chunk_index)}
                      className="text-[11px] text-primary-500 hover:text-primary-600 mt-1 font-medium"
                    >
                      {isExpanded ? "Show less" : "Show more"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-4">
            No chunks — document may still be processing
          </p>
        )
      )}

      {/* Log tab */}
      {tab === "log" && (
        data.ingestion_steps && data.ingestion_steps.length > 0 ? (
          <IngestionLog steps={data.ingestion_steps} />
        ) : (
          <p className="text-sm text-gray-400 py-4">
            No ingestion log available
          </p>
        )
      )}
    </div>
  );
}

function stepLabel(step: string): string {
  const labels: Record<string, string> = {
    extract: "Extract content",
    hash_check: "Content change check",
    budget_check: "Character budget",
    chunk: "Chunk content",
    embed: "Generate embeddings",
    index: "Store vectors",
  };
  return labels[step] || step;
}

function stepDetail(step: { step: string; status: string; detail: string | null }): string {
  if (step.step === "hash_check" && step.status === "skipped") {
    return "Content unchanged — skipped re-indexing";
  }
  return step.detail || "";
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function runOutcome(steps: NonNullable<DocumentContentResponse["ingestion_steps"]>): {
  label: string;
  color: string;
} {
  const failed = steps.find((s) => s.status === "failed");
  if (failed) return { label: `Failed at ${stepLabel(failed.step).toLowerCase()}`, color: "text-red-500" };
  const hashSkip = steps.find((s) => s.step === "hash_check" && s.status === "skipped");
  if (hashSkip) return { label: "Skipped — content unchanged", color: "text-gray-500" };
  const budgetSkip = steps.find((s) => s.step === "budget_check" && s.status === "skipped");
  if (budgetSkip) return { label: "Skipped — over character budget", color: "text-amber-500" };
  return { label: "Completed successfully", color: "text-green-600" };
}

function IngestionLog({ steps }: {
  steps: NonNullable<DocumentContentResponse["ingestion_steps"]>;
}) {
  const firstStep = steps[0];
  const runTime = firstStep?.started_at ? formatTimestamp(firstStep.started_at) : null;
  const totalMs = steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const outcome = runOutcome(steps);

  return (
    <div className="space-y-3">
      {/* Run summary */}
      <div className="bg-gray-50 border border-gray-100 rounded-lg px-3 py-2.5 text-xs space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-gray-500">
            {runTime ? `Run at ${runTime}` : "Last ingestion run"}
          </span>
          {totalMs > 0 && (
            <span className="text-gray-400">{totalMs < 1000 ? `${totalMs}ms` : `${(totalMs / 1000).toFixed(1)}s`} total</span>
          )}
        </div>
        <div className={`font-medium ${outcome.color}`}>{outcome.label}</div>
      </div>

      {/* Steps */}
      <div className="space-y-1.5">
        {steps.map((s, i) => {
          const Icon = stepStatusIcon[s.status] || CheckCircle;
          const color = stepStatusColor[s.status] || "text-gray-400";
          return (
            <div key={i} className="flex items-start gap-2 text-xs">
              <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${color}`} />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-gray-700">{stepLabel(s.step)}</span>
                {stepDetail(s) && (
                  <span className="text-gray-400 ml-1.5">{stepDetail(s)}</span>
                )}
                {s.error && (
                  <span className="text-red-500 ml-1.5">{s.error}</span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {s.started_at && (
                  <span className="text-[10px] text-gray-300">{new Date(s.started_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
                )}
                {s.duration_ms != null && (
                  <span className="text-[10px] text-gray-300">{s.duration_ms}ms</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
