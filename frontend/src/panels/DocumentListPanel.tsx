import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getDocuments, getKnowledgeBases } from "@/lib/api-functions";
import { Document } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  chatbot_id?: string;
  knowledge_base_id?: string;
}

export function DocumentListPanel({ chatbot_id, knowledge_base_id }: Props) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    async function load() {
      if (!workspace) return;
      let kbId = knowledge_base_id;
      if (!kbId && chatbot_id) {
        const kbs = await getKnowledgeBases(workspace.id, chatbot_id).catch(() => []);
        kbId = kbs[0]?.id;
      }
      if (!kbId) {
        setLoading(false);
        return;
      }
      await getDocuments(workspace.id, kbId)
        .then(setDocs)
        .catch(() => {});
      setLoading(false);
    }
    load();
  }, [workspace?.id, chatbot_id, knowledge_base_id]);

  if (!chatbot_id && !knowledge_base_id)
    return <p className="p-4 text-sm text-gray-400">No chatbot selected.</p>;
  if (loading)
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-5 w-5 text-primary-500" />
      </div>
    );

  return (
    <div className="p-4 space-y-2">
      <p className="text-xs text-gray-400 mb-2">{docs.length} documents</p>
      {docs.map((d) => (
        <div
          key={d.id}
          className="rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-xs"
        >
          <div className="font-medium text-gray-800 truncate">{d.title || "Untitled"}</div>
          <div className="text-gray-400 mt-0.5">
            {d.source_type} · {d.status}
          </div>
        </div>
      ))}
      {docs.length === 0 && (
        <p className="text-center text-gray-400 py-4">No documents.</p>
      )}
    </div>
  );
}
