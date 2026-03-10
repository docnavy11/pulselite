"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { clsx } from "clsx";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { getChatbot, duplicateChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  IconKnowledge,
  IconConfigure,
  IconActions,
  IconAppearance,
  IconTest,
  IconPublish,
} from "@/components/icons/NavIcons";

const TABS = [
  { label: "Knowledge",   segment: null,       Icon: IconKnowledge },
  { label: "Configure",   segment: "settings", Icon: IconConfigure },
  { label: "Actions",     segment: "actions",  Icon: IconActions },
  { label: "Appearance",  segment: "customize", Icon: IconAppearance },
  { label: "Test",        segment: "chat",     Icon: IconTest },
  { label: "Publish",     segment: "deploy",   Icon: IconPublish },
] as const;

export default function ChatbotLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbotId = params.id as string;
  const [chatbot, setChatbot] = useState<Chatbot | null>(null);
  const [loading, setLoading] = useState(true);
  const [duplicating, setDuplicating] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getChatbot(workspace.id, chatbotId)
      .then(setChatbot)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, chatbotId]);

  async function handleDuplicate() {
    if (!workspace || !chatbot) return;
    setDuplicating(true);
    try {
      const copy = await duplicateChatbot(workspace.id, chatbot.id);
      router.push(`/chatbots/${copy.id}`);
    } catch {
      // handle error
    } finally {
      setDuplicating(false);
    }
  }

  function tabHref(segment: string | null): string {
    return segment ? `/chatbots/${chatbotId}/${segment}` : `/chatbots/${chatbotId}`;
  }

  function isActive(segment: string | null): boolean {
    if (segment === null) {
      return pathname === `/chatbots/${chatbotId}`;
    }
    return pathname.startsWith(`/chatbots/${chatbotId}/${segment}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <Link
        href="/chatbots"
        className="inline-flex items-center gap-1 mb-3 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        ← Chatbots
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {chatbot?.display_name || chatbot?.name}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {chatbot?.llm_provider} / {chatbot?.llm_model}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleDuplicate}
          loading={duplicating}
        >
          <Copy className="h-4 w-4 mr-1.5" />
          Duplicate
        </Button>
      </div>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {TABS.map((tab) => {
            const { Icon } = tab;
            return (
              <Link
                key={tab.label}
                href={tabHref(tab.segment)}
                className={clsx(
                  "pb-3 text-sm font-medium border-b-2 transition-all duration-200 flex items-center gap-1.5",
                  isActive(tab.segment)
                    ? "border-primary-500 text-primary-500"
                    : "border-transparent text-gray-400 hover:text-gray-600 hover:border-gray-300",
                )}
              >
                <Icon size={12} />
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {children}
    </div>
  );
}
