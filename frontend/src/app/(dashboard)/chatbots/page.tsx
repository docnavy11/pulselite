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
import { getChatbots } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function ChatbotsPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);

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
          <Link key={chatbot.id} href={`/chatbots/${chatbot.id}`}>
            <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
              <CardContent className="py-5">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-500">
                    <Bot className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-gray-900 truncate">
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
              </CardContent>
            </Card>
          </Link>
        ))}

        {chatbots.length === 0 && (
          <Card className="col-span-full">
            <CardContent className="flex flex-col items-center justify-center py-12 text-gray-400">
              <Bot className="h-12 w-12 mb-3" />
              <p className="text-sm font-medium">No chatbots yet</p>
              <p className="text-xs mt-1">
                <button
                  className="text-primary-500 hover:underline"
                  onClick={() => router.push("/chatbots/new")}
                >
                  Create your first chatbot
                </button>{" "}
                to get started
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
