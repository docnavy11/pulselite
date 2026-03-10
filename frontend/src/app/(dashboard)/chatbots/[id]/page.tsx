"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { KnowledgeBase } from "@/lib/types";
import { getKnowledgeBases } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { SourcesTab } from "./sources/SourcesTab";

export default function ChatbotSourcesPage() {
  const params = useParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbotId = params.id as string;
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getKnowledgeBases(workspace.id, chatbotId)
      .then(setKnowledgeBases)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <SourcesTab
      chatbotId={chatbotId}
      knowledgeBases={knowledgeBases}
      onKnowledgeBasesChange={setKnowledgeBases}
    />
  );
}
