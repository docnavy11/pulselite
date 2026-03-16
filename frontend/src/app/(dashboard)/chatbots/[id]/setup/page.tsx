/**
 * Setup page for an existing chatbot (accessed via /chatbots/:id/setup).
 *
 * This is a thin redirect — the full wizard lives in /chatbots/new.
 * When you land here (e.g. page refresh mid-setup, or clicking a
 * "crawling" chatbot card), we redirect to /chatbots/new with the
 * chatbot ID so the wizard picks up where it left off.
 *
 * If the chatbot setup is already "done", we redirect to the detail page.
 */
import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Spinner } from "@/components/ui/Spinner";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { getChatbot } from "@/lib/api-functions";

export default function ChatbotSetupPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  useEffect(() => {
    if (!workspace || !id) return;
    getChatbot(workspace.id, id)
      .then((bot) => {
        if (!bot.setup_status || bot.setup_status === "done") {
          navigate(`/chatbots/${id}`, { replace: true });
        } else {
          // Redirect to the unified wizard — it will load this chatbot's state
          navigate(`/chatbots/new?resume=${id}`, { replace: true });
        }
      })
      .catch(() => {
        navigate("/chatbots", { replace: true });
      });
  }, [workspace, id, navigate]);

  return (
    <div className="flex items-center justify-center py-20">
      <Spinner className="h-8 w-8 text-primary-500" />
    </div>
  );
}
