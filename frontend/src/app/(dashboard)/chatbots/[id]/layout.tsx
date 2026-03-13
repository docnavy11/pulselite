import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation, Link, Outlet } from "react-router-dom";
import { clsx } from "clsx";
import { Copy, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { getChatbot, duplicateChatbot, updateChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useChatbotStore } from "@/stores/chatbot-store";
import { useCopilot } from "@/components/copilot/CopilotProvider";
import { LayoutDashboard } from "lucide-react";
import {
  IconKnowledge,
  IconConfigure,
  IconActions,
  IconAppearance,
  IconTest,
  IconPublish,
} from "@/components/icons/NavIcons";

const IconDashboard = LayoutDashboard;

const TABS = [
  { label: "Dashboard",  segment: null,        Icon: IconDashboard },
  { label: "Knowledge",  segment: "sources",   Icon: IconKnowledge },
  { label: "Configure",  segment: "settings",  Icon: IconConfigure },
  { label: "Actions",    segment: "actions",   Icon: IconActions },
  { label: "Appearance", segment: "customize", Icon: IconAppearance },
  { label: "Test",       segment: "chat",      Icon: IconTest },
  { label: "Publish",    segment: "deploy",    Icon: IconPublish },
] as const;

export default function ChatbotLayout() {
  const { id: chatbotId } = useParams() as { id: string };
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const { currentChatbot: chatbot, setChatbot, patchChatbot, clearChatbot } = useChatbotStore();
  const { register } = useCopilot();
  const [loading, setLoading] = useState(true);
  const [duplicating, setDuplicating] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [savingName, setSavingName] = useState(false);

  useEffect(() => {
    if (!workspace || !chatbotId) return;
    getChatbot(workspace.id, chatbotId)
      .then((bot) => {
        setChatbot(bot);
        register({
          page: "chatbot-settings",
          chatbot_id: bot.id,
          data: {
            chatbot: {
              name: bot.name,
              display_name: bot.display_name,
              llm_model: bot.llm_model,
              confidence_threshold: bot.confidence_threshold,
              is_active: bot.is_active,
              tone: bot.tone,
            },
          },
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => clearChatbot();
  }, [workspace, chatbotId, register]);

  function startEditName() {
    setNameValue(chatbot?.display_name || chatbot?.name || "");
    setEditingName(true);
  }

  async function saveName() {
    if (!workspace || !chatbot || !nameValue.trim()) return;
    setSavingName(true);
    try {
      const updated = await updateChatbot(workspace.id, chatbot.id, { display_name: nameValue.trim() });
      patchChatbot({ display_name: updated.display_name });
      setEditingName(false);
    } catch {
    } finally {
      setSavingName(false);
    }
  }

  async function handleDuplicate() {
    if (!workspace || !chatbot) return;
    setDuplicating(true);
    try {
      const copy = await duplicateChatbot(workspace.id, chatbot.id);
      navigate(`/chatbots/${copy.id}`);
    } catch {
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
        to="/chatbots"
        className="inline-flex items-center gap-1 mb-3 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        ← Chatbots
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div>
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                autoFocus
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveName();
                  if (e.key === "Escape") setEditingName(false);
                }}
                className="text-2xl font-bold text-gray-900 border-b-2 border-primary-500 bg-transparent focus:outline-none w-64"
              />
              <button onClick={saveName} disabled={savingName} className="text-green-600 hover:text-green-700 disabled:opacity-50">
                <Check className="h-5 w-5" />
              </button>
              <button onClick={() => setEditingName(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <h1 className="text-2xl font-bold text-gray-900">
                {chatbot?.display_name || chatbot?.name}
              </h1>
              <button
                onClick={startEditName}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-gray-600"
              >
                <Pencil className="h-4 w-4" />
              </button>
            </div>
          )}
          <p className="text-sm text-gray-500 mt-1">
            {chatbot?.llm_model?.split("/").pop()} / {chatbot?.tone}
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
        <nav className="flex gap-6 overflow-x-auto scrollbar-none">
          {TABS.map((tab) => {
            const { Icon } = tab;
            return (
              <Link
                key={tab.label}
                to={tabHref(tab.segment)}
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

      <Outlet />
    </div>
  );
}
