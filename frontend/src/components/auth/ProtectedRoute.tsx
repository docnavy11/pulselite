import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useDeploymentStore } from "@/stores/deployment-store";
import { api } from "@/lib/api";
import { getLLMSettings } from "@/lib/api-functions";
import { Workspace } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { AISetupDialog } from "@/components/setup/AISetupDialog";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { tokens, isLoading, initialize } = useAuthStore();
  const { currentWorkspace, setCurrentWorkspace, setWorkspaces } =
    useWorkspaceStore();
  const isCloud = useDeploymentStore((s) => s.isCloud);

  const [needsAISetup, setNeedsAISetup] = useState<boolean | null>(null);
  const [hasApiKey, setHasApiKey] = useState(false);

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && !tokens) {
      navigate("/login");
    }
  }, [isLoading, tokens, navigate]);

  useEffect(() => {
    if (!tokens || currentWorkspace) return;
    api
      .get<Workspace[]>("/api/v1/workspaces")
      .then((workspaces) => {
        setWorkspaces(workspaces);
        if (workspaces.length > 0) {
          setCurrentWorkspace(workspaces[0]);
        }
      })
      .catch(() => {});
  }, [tokens, currentWorkspace, setWorkspaces, setCurrentWorkspace]);

  // Check if AI is configured once workspace is loaded
  useEffect(() => {
    if (!currentWorkspace) return;
    getLLMSettings(currentWorkspace.id)
      .then((settings) => {
        const needsKey = !settings.effective_api_key_set;
        const needsModels = settings.allowed_models.length === 0;
        setHasApiKey(settings.effective_api_key_set);
        setNeedsAISetup(needsKey || needsModels);
      })
      .catch(() => {
        // If we can't check, let them through
        setNeedsAISetup(false);
      });
  }, [currentWorkspace]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  if (!tokens) return null;

  // Show AI setup dialog if not configured
  if (needsAISetup && currentWorkspace) {
    return (
      <AISetupDialog
        workspaceId={currentWorkspace.id}
        isCloud={isCloud}
        hasApiKey={hasApiKey}
        onComplete={() => setNeedsAISetup(false)}
      />
    );
  }

  // Still checking AI config
  if (needsAISetup === null && currentWorkspace) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return <>{children}</>;
}
