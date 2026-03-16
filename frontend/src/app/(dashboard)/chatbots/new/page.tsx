import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, ChevronRight, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { createChatbot, startCrawl } from "@/lib/api-functions";

function StepRow({ stepNum, label, done, active, isLast, nextDone, children }: {
  stepNum: number;
  label: string;
  done: boolean;
  active: boolean;
  isLast: boolean;
  nextDone: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex gap-3.5">
      <div className="flex flex-col items-center" style={{ width: 26 }}>
        <div className={`w-[26px] h-[26px] rounded-full flex items-center justify-center flex-shrink-0 ${
          done ? "bg-primary-500" :
          active ? "bg-primary-500" :
          "border-2 border-gray-300"
        }`}>
          {done ? (
            <Check className="h-3.5 w-3.5 text-white" />
          ) : (
            <span className={`text-xs font-semibold ${active ? "text-white" : "text-gray-400"}`}>{stepNum}</span>
          )}
        </div>
        {!isLast && (
          <div className={`w-0.5 flex-1 min-h-[16px] ${done && nextDone ? "bg-primary-500" : "bg-gray-200"}`} />
        )}
      </div>
      <div className="flex-1 pb-6">
        <div className="pt-0.5 mb-1">
          <span className={`text-sm font-medium ${
            done ? "text-gray-700" :
            active ? "text-gray-900" :
            "text-gray-400"
          }`}>{label}</span>
        </div>
        {(done || active) && children}
      </div>
    </div>
  );
}

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
      <h1 className="text-xl font-bold text-gray-900 mb-8">Setting up your bot</h1>

      <div className="space-y-0">
        {/* Step 1: Your website — active with form */}
        <StepRow stepNum={1} label="Your website" done={false} active={true} isLast={false} nextDone={false}>
          <form onSubmit={(e) => handleStart(e)} className="space-y-4 mt-2">
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
            {error && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}
            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={!url.trim() || starting} loading={starting}>
                Start setup
                <ChevronRight className="ml-1.5 h-4 w-4" />
              </Button>
            </div>
          </form>
        </StepRow>

        {/* Step 2: Crawl & analyse — upcoming */}
        <StepRow stepNum={2} label="Crawl & analyse" done={false} active={false} isLast={false} nextDone={false} />

        {/* Step 3: Review config — upcoming */}
        <StepRow stepNum={3} label="Review config" done={false} active={false} isLast={false} nextDone={false} />

        {/* Step 4: Go live — upcoming */}
        <StepRow stepNum={4} label="Go live" done={false} active={false} isLast={true} nextDone={false} />
      </div>
    </div>
  );
}
