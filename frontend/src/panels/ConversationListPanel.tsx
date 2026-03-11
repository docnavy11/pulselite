"use client";

import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getConversations } from "@/lib/api-functions";
import { Conversation } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

interface Props {
  filters?: { status?: string; chatbot_id?: string };
  chatbot_id?: string;
}

export function ConversationListPanel({ filters, chatbot_id }: Props) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getConversations(workspace.id, {
      ...filters,
      chatbot_id: chatbot_id ?? filters?.chatbot_id,
    })
      .then(setConversations)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace?.id]);

  if (loading)
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-5 w-5 text-primary-500" />
      </div>
    );

  return (
    <div className="p-4">
      <p className="text-xs text-gray-400 mb-3">{conversations.length} conversations</p>
      <div className="space-y-2">
        {conversations.map((c) => (
          <a
            key={c.id}
            href={`/conversations/${c.id}`}
            className={`block rounded-lg border px-3 py-2.5 text-xs hover:bg-gray-50 transition-colors ${
              c.status === "escalated"
                ? "border-red-200 bg-red-50"
                : "border-gray-200 bg-white"
            }`}
          >
            <div className="font-medium text-gray-800 truncate">#{c.id.slice(0, 8)}</div>
            <div className="text-gray-400 mt-0.5">
              {c.status === "escalated" && (
                <span className="text-red-500 mr-1">Escalated ·</span>
              )}
              {new Date(c.created_at).toLocaleDateString()}
            </div>
          </a>
        ))}
        {conversations.length === 0 && (
          <p className="text-center text-gray-400 py-4">No conversations found.</p>
        )}
      </div>
    </div>
  );
}
