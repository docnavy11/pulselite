import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus,
  Globe,
  FileText,
  Type,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Document, KnowledgeBase } from "@/lib/types";
import {
  getDocuments,
  deleteDocument,
  reindexDocument,
  createKnowledgeBase,
  updateDocument,
  getCrawlHistory,
} from "@/lib/api-functions";
import { CrawlJobSummary } from "@/lib/types";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { AddSourceModal } from "@/components/knowledge/AddSourceModal";

function errorDescription(error: string): string {
  if (!error) return "Unknown error";
  if (error.includes("429")) return "Rate limited — the server rejected too many requests from our crawler";
  if (error.includes("403")) return "Access denied — the server is blocking our crawler";
  if (error.includes("404")) return "Page not found";
  if (error.includes("401")) return "Authentication required — the page is behind a login";
  if (error.includes("410")) return "Page permanently removed";
  const m5xx = error.match(/HTTP 5(\d\d)/);
  if (m5xx) return `Server error (${m5xx[0]}) — the remote site had an internal problem`;
  const m4xx = error.match(/HTTP 4(\d\d)/);
  if (m4xx) return `Client error (${m4xx[0]}) — the page rejected the request`;
  if (error === "Empty response") return "Page loaded but returned no readable content";
  return error;
}

const statusVariant: Record<string, "default" | "success" | "warning" | "danger"> = {
  pending: "default",
  processing: "warning",
  indexed: "success",
  failed: "danger",
};

const sourceTypeIcon: Record<string, typeof Globe> = {
  url: Globe,
  file: FileText,
  text: Type,
};

interface SourcesTabProps {
  chatbotId: string;
  knowledgeBases: KnowledgeBase[];
  onKnowledgeBasesChange: (kbs: KnowledgeBase[]) => void;
}

export function SourcesTab({
  chatbotId,
  knowledgeBases,
  onKnowledgeBasesChange,
}: SourcesTabProps) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddSource, setShowAddSource] = useState(false);
  const [crawlHistory, setCrawlHistory] = useState<CrawlJobSummary[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [failedOpen, setFailedOpen] = useState(true);
  const [retryingAll, setRetryingAll] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const primaryKb = knowledgeBases[0];

  const fetchDocuments = useCallback(async () => {
    if (!primaryKb || !workspace) {
      setLoading(false);
      return;
    }
    try {
      const docs = await getDocuments(workspace.id, primaryKb.id);
      setDocuments(docs);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }, [primaryKb, workspace]);

  useEffect(() => {
    fetchDocuments();
    if (workspace) {
      getCrawlHistory(workspace.id, chatbotId).then(setCrawlHistory).catch(() => {});
    }
  }, [fetchDocuments, workspace, chatbotId]);

  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === "processing" || d.status === "pending");
    if (hasProcessing) {
      pollRef.current = setInterval(fetchDocuments, 5000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [documents, fetchDocuments]);

  async function handleDelete(docId: string) {
    if (!workspace) return;
    try {
      await deleteDocument(workspace.id, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      // handle error
    }
  }

  async function handleReindex(docId: string) {
    if (!workspace) return;
    try {
      const updated = await reindexDocument(workspace.id, docId);
      setDocuments((prev) => prev.map((d) => (d.id === docId ? updated : d)));
    } catch {
      // handle error
    }
  }

  async function handleRetryAll() {
    if (!workspace) return;
    setRetryingAll(true);
    try {
      await Promise.all(
        failedDocs.map((doc) =>
          reindexDocument(workspace.id, doc.id).then((updated) =>
            setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)))
          )
        )
      );
    } catch {
      // handle error
    } finally {
      setRetryingAll(false);
    }
  }

  async function ensureKnowledgeBase(): Promise<string> {
    if (primaryKb) return primaryKb.id;
    if (!workspace) throw new Error("No workspace");
    const kb = await createKnowledgeBase(workspace.id, {
      name: "Default",
      kb_type: "general",
      chatbot_id: chatbotId,
    });
    onKnowledgeBasesChange([...knowledgeBases, kb]);
    return kb.id;
  }

  function handleSourcesAdded() {
    setShowAddSource(false);
    fetchDocuments();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="h-6 w-6 text-primary-500" />
      </div>
    );
  }

  const activeDocs = documents.filter((d) => d.status !== "failed");
  const failedDocs = documents.filter((d) => d.status === "failed");
  // If no failed docs in DB but crawl history shows failures, it's an older crawl
  const failedFromHistory = crawlHistory.length > 0 ? crawlHistory[0].pages_failed : 0;
  const hasUnrecordedFailures = failedDocs.length === 0 && failedFromHistory > 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Sources</h2>
        <Button onClick={() => setShowAddSource(true)} size="sm">
          <Plus className="h-4 w-4 mr-1" />
          Add Source
        </Button>
      </div>

      {/* Active sources table */}
      {activeDocs.length === 0 && failedDocs.length === 0 && !hasUnrecordedFailures ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-gray-400">
            <FileText className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No sources yet</p>
            <p className="text-xs mt-1">
              Add URLs, files, or text to build the knowledge base
            </p>
          </CardContent>
        </Card>
      ) : activeDocs.length > 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Last synced</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Sync</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {activeDocs.map((doc) => {
                const Icon = sourceTypeIcon[doc.source_type] || FileText;
                return (
                  <tr
                    key={doc.id}
                    className="group border-b border-[#faf8f5] last:border-0 hover:bg-[#faf8f5] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-gray-400 shrink-0" />
                        <span className="truncate max-w-xs">
                          {doc.title || doc.source_url || "Untitled"}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500 capitalize">{doc.source_type}</td>
                    <td className="px-4 py-3">
                      {doc.status === "processing" && (
                        <span className="flex items-center gap-1.5 text-amber-500 text-[11px] animate-pulse">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
                          Processing…
                        </span>
                      )}
                      {doc.status === "pending" && (
                        <span className="flex items-center gap-1.5 text-gray-400 text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-gray-300 inline-block" />
                          Pending
                        </span>
                      )}
                      {doc.status === "indexed" && (
                        <span className="flex items-center gap-1.5 text-green-600 text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                          Indexed
                        </span>
                      )}
                      {!["processing", "pending", "indexed"].includes(doc.status) && (
                        <Badge variant={statusVariant[doc.status] || "default"}>
                          {doc.status}
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-[11px]">
                      {doc.last_indexed_at
                        ? new Date(doc.last_indexed_at).toLocaleDateString()
                        : "-"}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={doc.sync_frequency || "manual"}
                        onChange={async (e) => {
                          if (!workspace) return;
                          const updated = await updateDocument(workspace.id, doc.id, {
                            sync_frequency: e.target.value,
                          });
                          setDocuments((prev) => prev.map((d) => (d.id === doc.id ? updated : d)));
                        }}
                        className="text-xs text-gray-600 border border-gray-200 rounded px-2 py-1"
                      >
                        <option value="manual">Manual</option>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center gap-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                        <button
                          onClick={() => handleReindex(doc.id)}
                          className="text-[11px] text-gray-400 hover:text-gray-700"
                        >
                          Reindex
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="text-[11px] text-red-400 hover:text-red-600"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* Failed pages section */}
      {(failedDocs.length > 0 || hasUnrecordedFailures) && (
        <div className="mt-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setFailedOpen((o) => !o)}
              className="flex items-center gap-2 text-sm font-medium text-red-500 hover:text-red-700 transition-colors"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              <span className={`transition-transform text-xs ${failedOpen ? "rotate-90" : ""}`}>▶</span>
              Failed pages
              <span className="text-xs font-normal text-red-400">
                ({failedDocs.length > 0 ? failedDocs.length : failedFromHistory})
              </span>
            </button>
            {failedDocs.length > 1 && (
              <button
                onClick={handleRetryAll}
                disabled={retryingAll}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50 transition-colors"
              >
                <RefreshCw className={`h-3 w-3 ${retryingAll ? "animate-spin" : ""}`} />
                Retry all
              </button>
            )}
          </div>

          {failedOpen && (
            <div className="mt-2">
              {hasUnrecordedFailures ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                  <span className="font-medium">{failedFromHistory} pages failed</span> during the last crawl, but per-URL error details weren&apos;t saved for this run.{" "}
                  Re-crawl the site to see exactly which URLs failed and why.
                </div>
              ) : (
                <div className="rounded-lg border border-red-100 bg-white overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100 bg-red-50">
                        <th className="text-left px-4 py-2.5 font-medium text-red-600">URL</th>
                        <th className="text-left px-4 py-2.5 font-medium text-red-600">Reason</th>
                        <th className="text-right px-4 py-2.5 font-medium text-red-600">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {failedDocs.map((doc) => {
                        const rawError = doc.metadata_?.error || "";
                        return (
                          <tr key={doc.id} className="group border-b border-red-50 last:border-0 hover:bg-red-50 transition-colors">
                            <td className="px-4 py-2.5 max-w-[240px]">
                              <div className="flex items-center gap-1.5">
                                <span className="truncate text-gray-600" title={doc.source_url}>
                                  {doc.source_url || doc.title || "Unknown URL"}
                                </span>
                                {doc.source_url && (
                                  <a
                                    href={doc.source_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="shrink-0 text-gray-300 hover:text-blue-500 transition-colors"
                                    title="Open in new tab"
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-2.5 max-w-[260px]">
                              <span className="text-red-500 font-medium">{rawError}</span>
                              {rawError && (
                                <span className="block text-gray-400 mt-0.5 leading-snug">
                                  {errorDescription(rawError)}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-right">
                              <div className="flex items-center gap-3 justify-end">
                                <button
                                  onClick={() => handleReindex(doc.id)}
                                  className="flex items-center gap-1 text-gray-400 hover:text-gray-700 transition-colors"
                                  title="Retry this page"
                                >
                                  <RefreshCw className="h-3 w-3" />
                                  Retry
                                </button>
                                <button
                                  onClick={() => handleDelete(doc.id)}
                                  className="text-red-300 hover:text-red-600 transition-colors"
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Crawl history */}
      {crawlHistory.length > 0 && (
        <div className="mt-6">
          <button
            onClick={() => setHistoryOpen((o) => !o)}
            className="flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors"
          >
            <span className={`transition-transform text-xs ${historyOpen ? "rotate-90" : ""}`}>▶</span>
            Crawl history
            <span className="text-xs font-normal text-gray-400">({crawlHistory.length})</span>
          </button>

          {historyOpen && (
            <div className="mt-2 rounded-lg border border-gray-200 bg-white overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">URL</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Status</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Crawled</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Indexed</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Failed</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Duration</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {crawlHistory.map((job) => {
                    const statusDot: Record<string, string> = {
                      completed: "bg-green-400",
                      running: "bg-blue-400 animate-pulse",
                      pending: "bg-gray-300",
                      failed: "bg-red-400",
                    };
                    const total = job.pages_queued + job.pages_failed;
                    const failPct = total > 0 ? job.pages_failed / total : 0;
                    const durationMs = job.completed_at
                      ? new Date(job.completed_at).getTime() - new Date(job.created_at).getTime()
                      : null;
                    const duration = durationMs !== null
                      ? durationMs < 60000
                        ? `${Math.round(durationMs / 1000)}s`
                        : `${Math.round(durationMs / 60000)}m`
                      : "—";
                    return (
                      <tr key={job.job_id} className="border-b border-[#faf8f5] last:border-0">
                        <td className="px-4 py-2.5 text-gray-600 max-w-[160px]">
                          <span className="truncate block" title={job.root_url}>{job.root_url}</span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="flex items-center gap-1.5 capitalize">
                            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusDot[job.status] ?? "bg-gray-300"}`} />
                            {job.status}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-gray-500">{job.pages_queued}</td>
                        <td className="px-4 py-2.5 text-green-600 font-medium">{job.docs_indexed}</td>
                        <td className="px-4 py-2.5">
                          {job.pages_failed > 0 ? (
                            <span className={`flex items-center gap-1 font-medium ${failPct > 0.5 ? "text-red-500" : "text-amber-500"}`}>
                              {failPct > 0.3 && <AlertTriangle className="h-3 w-3 flex-shrink-0" />}
                              {job.pages_failed}
                            </span>
                          ) : (
                            <span className="text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-gray-400">{duration}</td>
                        <td className="px-4 py-2.5 text-gray-400">
                          {new Date(job.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showAddSource && workspace && (
        <AddSourceModal
          workspaceId={workspace.id}
          getKnowledgeBaseId={ensureKnowledgeBase}
          onClose={() => setShowAddSource(false)}
          onAdded={handleSourcesAdded}
        />
      )}
    </div>
  );
}
