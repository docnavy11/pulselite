import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getCrawlStatus, getLatestCrawlForChatbot } from "@/lib/api-functions";
import { CrawlStatusResponse } from "@/lib/types";
import type { CrawlProgressEvent, CrawlCompletedEvent } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { useSocketEvent, getSocket } from "@/lib/socket";

interface Props {
  chatbot_id?: string;
  job_id?: string;
}

export function CrawlStatusPanel({ chatbot_id, job_id }: Props) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [status, setStatus] = useState<CrawlStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // Initial fetch to get current state
  useEffect(() => {
    if (!workspace || (!chatbot_id && !job_id)) {
      setLoading(false);
      setNotFound(true);
      return;
    }

    async function fetchInitial() {
      if (!workspace) return;
      try {
        let data: CrawlStatusResponse | null = null;
        if (job_id) {
          data = await getCrawlStatus(workspace.id, job_id);
        } else if (chatbot_id) {
          data = await getLatestCrawlForChatbot(workspace.id, chatbot_id);
        }
        if (!data) {
          setNotFound(true);
          return;
        }
        setStatus(data);
      } catch {
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }

    fetchInitial();
  }, [workspace?.id, chatbot_id, job_id]);

  // Real-time crawl progress
  useSocketEvent<CrawlProgressEvent>("crawl:progress", (data) => {
    if (job_id && data.job_id !== job_id) return;
    if (!job_id && data.chatbot_id !== chatbot_id) return;
    setStatus((prev) => prev ? {
      ...prev,
      phase: data.phase,
      pages_discovered: data.pages_discovered,
      pages_queued: data.pages_queued,
      pages_failed: data.pages_failed,
      status: "running",
    } : prev);
  });

  // Real-time crawl completed
  useSocketEvent<CrawlCompletedEvent>("crawl:completed", (data) => {
    if (job_id && data.job_id !== job_id) return;
    if (!job_id && data.chatbot_id !== chatbot_id) return;
    setStatus((prev) => prev ? {
      ...prev,
      status: data.status,
      pages_queued: data.pages_queued,
      pages_failed: data.pages_failed,
      error_message: data.error_message ?? null,
      phase: null,
    } : prev);
  });

  // Refetch on reconnect
  useEffect(() => {
    const s = getSocket();
    const onReconnect = () => {
      if (!workspace) return;
      const fetch = job_id
        ? getCrawlStatus(workspace.id, job_id)
        : chatbot_id
        ? getLatestCrawlForChatbot(workspace.id, chatbot_id)
        : null;
      fetch?.then(setStatus).catch(() => {});
    };
    s.on("connect", onReconnect);
    return () => { s.off("connect", onReconnect); };
  }, [workspace?.id, chatbot_id, job_id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div className="flex justify-center py-8">
      <Spinner className="h-5 w-5 text-primary-500" />
    </div>
  );

  if (notFound || !status) return (
    <div className="p-4 text-xs text-gray-400 text-center py-8">No crawl job found.</div>
  );

  const isActive = status.status === "running" || status.status === "pending";

  const crawlPct = status.status === "pending"
    ? 5
    : status.status === "completed"
    ? 100
    : Math.min(95, (status.pages_queued / Math.max(status.pages_discovered, 1)) * 100);

  const indexPct = status.docs_total === 0
    ? 0
    : Math.round(((status.docs_indexed + status.docs_failed) / status.docs_total) * 100);

  const statusColor: Record<string, string> = {
    pending: "text-amber-500",
    running: "text-blue-500",
    completed: "text-green-600",
    failed: "text-red-500",
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">Crawl status</span>
        <span className={`text-[11px] font-semibold capitalize ${statusColor[status.status] ?? "text-gray-500"}`}>
          {isActive && <span className="inline-block w-1.5 h-1.5 rounded-full bg-current mr-1 animate-pulse" />}
          {status.status}
        </span>
      </div>

      {status.status === "failed" && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          Crawl failed. The site may be unreachable or blocking crawlers.
        </div>
      )}

      {/* Crawling */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-gray-600 font-medium">Pages crawled</span>
          <span className="text-gray-400">
            {status.pages_queued} / {status.pages_discovered || "…"}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-100">
          <div
            className="h-1.5 rounded-full bg-primary-500 transition-all duration-500"
            style={{ width: `${crawlPct}%` }}
          />
        </div>
        {status.pages_failed > 0 && (
          <p className="text-[10px] text-amber-600 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {status.pages_failed} page{status.pages_failed > 1 ? "s" : ""} failed
          </p>
        )}
      </div>

      {/* Indexing */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px]">
          <span className="text-gray-600 font-medium">Pages indexed</span>
          <span className="text-gray-400">
            {status.docs_indexed} / {status.docs_total || "…"}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-100">
          <div
            className="h-1.5 rounded-full bg-primary-400 transition-all duration-500"
            style={{ width: `${indexPct}%` }}
          />
        </div>
        {status.docs_failed > 0 && (
          <p className="text-[10px] text-amber-600 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {status.docs_failed} failed to index
          </p>
        )}
      </div>

      {status.stalled && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800">
          Taking longer than expected — the site may be slow or blocking crawlers.
        </div>
      )}

      {status.status === "completed" && (
        <div className="rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-[11px] text-green-800 font-medium">
          ✓ Crawl complete — {status.docs_indexed} pages indexed
        </div>
      )}

      {(status.docs_skipped ?? 0) > 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          {status.docs_skipped} page{status.docs_skipped > 1 ? "s were" : " was"} skipped — character limit reached.
        </div>
      )}
    </div>
  );
}
