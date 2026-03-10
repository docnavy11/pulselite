"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Bot } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { getChatbots, updateChatbot, deleteChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function ChatbotsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handleToggle = async (e: { preventDefault: () => void }, chatbot: Chatbot) => {
    e.preventDefault();
    if (!workspace) return;
    setActionPending(chatbot.id);
    try {
      const updated = await updateChatbot(workspace.id, chatbot.id, { is_active: !chatbot.is_active });
      setChatbots((prev) => prev.map((c) => (c.id === chatbot.id ? { ...c, ...updated } : c)));
    } finally {
      setActionPending(null);
    }
  };

  const handleDelete = async (e: { preventDefault: () => void }, id: string) => {
    e.preventDefault();
    if (!workspace) return;
    setActionPending(id);
    try {
      await deleteChatbot(workspace.id, id);
      setChatbots((prev) => prev.filter((c) => c.id !== id));
    } finally {
      setActionPending(null);
      setConfirmDelete(null);
    }
  };

  useEffect(() => {
    if (!workspace) return;
    getChatbots(workspace.id)
      .then(setChatbots)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Chatbots</h1>
        <Button onClick={() => router.push("/chatbots/new")}>
          <Plus className="h-4 w-4 mr-2" />
          Create Chatbot
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {chatbots.map((chatbot) => (
          <div key={chatbot.id} className="group relative">
            {/* Delete confirmation overlay */}
            {confirmDelete === chatbot.id && (
              <div className="absolute inset-0 z-10 bg-white border border-red-200 rounded-xl flex flex-col items-center justify-center gap-3 p-4 shadow-lg">
                <p className="text-[13px] font-semibold text-gray-800 text-center">Delete "{chatbot.display_name || chatbot.name}"?</p>
                <p className="text-[11px] text-gray-400 text-center">This cannot be undone.</p>
                <div className="flex gap-2">
                  <button
                    onClick={(e) => handleDelete(e, chatbot.id)}
                    disabled={actionPending === chatbot.id}
                    className="px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white rounded-lg text-[11px] font-semibold transition-colors disabled:opacity-60"
                  >
                    {actionPending === chatbot.id ? "Deleting…" : "Delete"}
                  </button>
                  <button
                    onClick={() => setConfirmDelete(null)}
                    className="px-3 py-1.5 bg-[#faf8f5] border border-[#f0ebe3] text-gray-600 rounded-lg text-[11px] font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <Link href={`/chatbots/${chatbot.id}`}>
              <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
                <CardContent className="py-5">
                  <div className="flex items-start gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${chatbot.is_active ? "bg-primary-50 text-primary-500" : "bg-gray-100 text-gray-400"}`}>
                      <Bot className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className={`text-sm font-semibold truncate ${chatbot.is_active ? "text-gray-900" : "text-gray-400"}`}>
                          {chatbot.display_name || chatbot.name}
                        </h3>
                        <Badge variant={chatbot.is_active ? "success" : "default"}>
                          {chatbot.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-gray-500">
                        {chatbot.llm_model} / {chatbot.tone}
                      </p>
                    </div>
                  </div>

                  {/* Hover actions */}
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[#faf8f5] opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                    <button
                      onClick={(e) => handleToggle(e, chatbot)}
                      disabled={actionPending === chatbot.id}
                      className="flex-1 py-1 text-[11px] font-medium text-gray-500 hover:text-gray-700 border border-[#f0ebe3] rounded-lg hover:bg-[#faf8f5] transition-colors disabled:opacity-50"
                    >
                      {actionPending === chatbot.id ? "…" : chatbot.is_active ? "Disable" : "Enable"}
                    </button>
                    <button
                      onClick={(e) => { e.preventDefault(); setConfirmDelete(chatbot.id); }}
                      className="flex-1 py-1 text-[11px] font-medium text-red-400 hover:text-red-600 border border-[#f0ebe3] rounded-lg hover:bg-red-50 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </div>
        ))}

        {chatbots.length === 0 && !loading && (
          <div className="col-span-full flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <path
                  d="M24 4 L29 18 L44 24 L29 30 L24 44 L19 30 L4 24 L19 18 Z"
                  stroke="#ff6b35" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  fill="none"
                />
              </svg>
            </div>
            <h3 className="text-[16px] font-bold text-gray-800 mb-2">Your first bot is one URL away</h3>
            <p className="text-[13px] text-gray-400 mb-5 max-w-xs">
              Paste a URL, we crawl it and auto-configure a chatbot in minutes.
            </p>
            <button
              onClick={() => router.push("/chatbots/new")}
              className="px-5 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-xl text-[13px] font-semibold transition-colors"
            >
              Create my first chatbot
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
