"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus,
  Globe,
  FileText,
  Type,
  RotateCw,
  Trash2,
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
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { AddSourceModal } from "@/components/knowledge/AddSourceModal";

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
  }, [fetchDocuments]);

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
        <Spinner className="h-6 w-6 text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Sources</h2>
        <Button onClick={() => setShowAddSource(true)} size="sm">
          <Plus className="h-4 w-4 mr-1" />
          Add Source
        </Button>
      </div>

      {documents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-gray-400">
            <FileText className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No sources yet</p>
            <p className="text-xs mt-1">
              Add URLs, files, or text to build the knowledge base
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Source
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Type
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Status
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Chunks
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Last Indexed
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Sync
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const Icon = sourceTypeIcon[doc.source_type] || FileText;
                return (
                  <tr
                    key={doc.id}
                    className="border-b border-gray-100 last:border-0"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-gray-400 shrink-0" />
                        <span className="truncate max-w-xs">
                          {doc.title || doc.source_url || "Untitled"}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500 capitalize">
                      {doc.source_type}
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={statusVariant[doc.status] || "default"}
                        className={
                          doc.status === "processing" ? "animate-pulse" : ""
                        }
                      >
                        {doc.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {doc.chunk_count}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
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
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleReindex(doc.id)}
                          className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-all duration-200"
                          title="Reindex"
                        >
                          <RotateCw className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 transition-all duration-200"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
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
