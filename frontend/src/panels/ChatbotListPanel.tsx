import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getChatbots } from "@/lib/api-functions";
import { Chatbot } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

export function ChatbotListPanel(_props: Record<string, unknown>) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [bots, setBots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getChatbots(workspace.id)
      .then(setBots)
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
    <div className="p-4 space-y-2">
      {bots.map((b) => (
        <a
          key={b.id}
          href={`/chatbots/${b.id}`}
          className="block rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-xs hover:bg-gray-50 transition-colors"
        >
          <div className="font-medium text-gray-800">{b.display_name || b.name}</div>
          <div className="text-gray-400 mt-0.5">
            {b.is_active ? "Active" : "Inactive"} · {b.llm_model}
          </div>
        </a>
      ))}
      {bots.length === 0 && (
        <p className="text-center text-gray-400 py-4">No chatbots found.</p>
      )}
    </div>
  );
}
