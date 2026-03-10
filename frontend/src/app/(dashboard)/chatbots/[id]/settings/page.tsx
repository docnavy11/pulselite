"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { getChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { SettingsTab } from "../SettingsTab";

export default function ChatbotSettingsPage() {
  const params = useParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbotId = params.id as string;
  const [chatbot, setChatbot] = useState<Chatbot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getChatbot(workspace.id, chatbotId)
      .then(setChatbot)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  if (loading || !chatbot) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return <SettingsTab chatbot={chatbot} onUpdate={setChatbot} />;
}
