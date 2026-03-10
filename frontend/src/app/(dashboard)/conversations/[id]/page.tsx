"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { clsx } from "clsx";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Conversation, Message } from "@/lib/types";
import {
  getConversation,
  getMessages,
  updateConversationStatus,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (confidence == null) return null;
  const variant =
    confidence > 0.75 ? "success" : confidence > 0.5 ? "warning" : "danger";
  return (
    <Badge variant={variant} className="text-[10px]">
      {Math.round(confidence * 100)}%
    </Badge>
  );
}

const statusOptions = ["open", "pending", "resolved", "closed"];

export default function ConversationDetailPage() {
  const params = useParams();
  const conversationId = params.id as string;
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    Promise.all([
      getConversation(workspace.id, conversationId),
      getMessages(workspace.id, conversationId),
    ])
      .then(([conv, msgs]) => {
        setConversation(conv);
        setMessages(msgs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, conversationId]);

  async function handleStatusChange(status: string) {
    if (!workspace || !conversation) return;
    try {
      const updated = await updateConversationStatus(
        workspace.id,
        conversationId,
        status,
      );
      setConversation(updated);
    } catch {
      // handle error
    }
  }

  if (loading || !conversation) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="flex gap-6 h-[calc(100vh-8rem)]">
      <div className="flex-[2] flex flex-col overflow-hidden">
        <h1 className="text-lg font-semibold text-gray-900 mb-4">
          Conversation
        </h1>
        <div className="flex-1 overflow-auto rounded-lg border border-gray-200 bg-white p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={clsx(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={clsx(
                  "max-w-[70%] rounded-lg px-4 py-2.5 text-sm",
                  msg.role === "user"
                    ? "bg-primary-600 text-white"
                    : "bg-gray-100 text-gray-900",
                )}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.role === "assistant" && (
                  <div className="mt-1 flex items-center gap-1">
                    <ConfidenceBadge confidence={msg.confidence} />
                    <span className="text-[10px] text-gray-400">
                      {new Date(msg.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1">
        <Card>
          <CardContent className="pt-6 pb-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900">Details</h2>

            <div>
              <label className="text-xs font-medium text-gray-500">Contact</label>
              <p className="text-sm text-gray-900">
                {conversation.contact_name || conversation.contact_email || "Anonymous"}
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Status</label>
              <select
                value={conversation.status}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {statusOptions.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Confidence</label>
              <p className="text-sm">
                {conversation.confidence != null
                  ? `${Math.round(conversation.confidence * 100)}%`
                  : "-"}
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Outcome</label>
              <p className="text-sm text-gray-900">
                {conversation.outcome || "-"}
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Created</label>
              <p className="text-sm text-gray-900">
                {new Date(conversation.created_at).toLocaleString()}
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500">Updated</label>
              <p className="text-sm text-gray-900">
                {new Date(conversation.updated_at).toLocaleString()}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
