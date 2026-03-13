import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Globe, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { createChatbot, startCrawl } from "@/lib/api-functions";

export default function NewBotWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [url, setUrl] = useState("");
  const [botName, setBotName] = useState("");
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  function inferName(rawUrl: string) {
    try {
      const host = new URL(rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`).hostname;
      return host.replace(/^www\./, "").split(".")[0];
    } catch {
      return "";
    }
  }

  const autoStarted = useRef(false);

  useEffect(() => {
    const prefillUrl = searchParams.get("url") ?? "";
    const prefillName = searchParams.get("name") ?? "";
    if (!prefillUrl || !workspace || autoStarted.current) return;
    autoStarted.current = true;
    setUrl(prefillUrl);
    if (prefillName) setBotName(prefillName);
    handleStart(undefined, prefillUrl, prefillName);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  async function handleStart(
    e?: { preventDefault: () => void },
    overrideUrl?: string,
    overrideName?: string,
  ) {
    e?.preventDefault();
    if (!workspace) return;
    setError("");
    setStarting(true);

    const rawUrl = overrideUrl ?? url;
    const rawName = overrideName ?? botName;
    const normalized = rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`;
    const name = rawName.trim() || inferName(normalized) || "My Bot";

    try {
      const chatbot = await createChatbot(workspace.id, { name });
      await startCrawl(workspace.id, normalized, [], [], chatbot.id);
      navigate(`/chatbots/${chatbot.id}/setup`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setStarting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      <Card>
        <CardContent className="pt-8 pb-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-500">
              <Globe className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Your website</h2>
              <p className="text-sm text-gray-500">We'll crawl it and set up your bot automatically.</p>
            </div>
          </div>
          <form onSubmit={(e) => handleStart(e)} className="space-y-4">
            <Input
              label="Website URL"
              placeholder="https://acmecorp.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              autoFocus
            />
            <Input
              label="Bot name (optional)"
              placeholder={inferName(url) || "My Support Bot"}
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={!url.trim() || starting} loading={starting}>
                Start setup
                <ChevronRight className="ml-1.5 h-4 w-4" />
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
