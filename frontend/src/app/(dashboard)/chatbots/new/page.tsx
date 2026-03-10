"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Globe, CheckCircle, ChevronRight, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  createChatbot,
  startCrawl,
  getCrawlStatus,
  runAutoconfig,
  updateChatbot,
} from "@/lib/api-functions";
import { AutoConfigResponse, CrawlStatusResponse } from "@/lib/types";

type Step = "url" | "crawling" | "review" | "done";

const STEPS: { id: Step; label: string }[] = [
  { id: "url", label: "Your website" },
  { id: "crawling", label: "Crawling" },
  { id: "review", label: "Review" },
  { id: "done", label: "Done" },
];

export default function NewBotWizardPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [botName, setBotName] = useState("");
  const [error, setError] = useState("");

  // crawling state
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatusResponse | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // result state
  const [config, setConfig] = useState<AutoConfigResponse | null>(null);
  const [chatbotId, setChatbotId] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  // editable review fields
  const [reviewName, setReviewName] = useState("");
  const [reviewWelcome, setReviewWelcome] = useState("");
  const [reviewColor, setReviewColor] = useState("");

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function inferName(rawUrl: string) {
    try {
      const host = new URL(rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`).hostname;
      return host.replace(/^www\./, "").split(".")[0];
    } catch {
      return "";
    }
  }

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setError("");

    const normalized = url.startsWith("http") ? url : `https://${url}`;
    const name = botName.trim() || inferName(normalized) || "My Bot";

    try {
      setStep("crawling");

      // Create chatbot first
      const chatbot = await createChatbot(workspace.id, { name });
      setChatbotId(chatbot.id);

      // Start crawl
      const crawl = await startCrawl(workspace.id, normalized, 50);
      setCrawlStatus({ job_id: crawl.job_id, status: "pending", pages_discovered: crawl.pages_discovered, pages_queued: 0, pages_failed: 0 });

      // Poll for completion
      pollRef.current = setInterval(async () => {
        try {
          const status = await getCrawlStatus(workspace.id, crawl.job_id);
          setCrawlStatus(status);
          if (status.status === "completed" || status.status === "failed") {
            clearInterval(pollRef.current!);
            if (status.status === "failed") {
              setError("Crawl failed. Please try again.");
              setStep("url");
              return;
            }
            // Run autoconfig
            const result = await runAutoconfig(workspace.id, chatbot.id, crawl.kb_id);
            setConfig(result);
            setReviewName(result.name);
            setReviewWelcome(result.welcome_message ?? "");
            setReviewColor(result.brand_color ?? "#4F46E5");
            setStep("review");
          }
        } catch {
          clearInterval(pollRef.current!);
          setError("Something went wrong. Please try again.");
          setStep("url");
        }
      }, 2000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(msg);
      setStep("url");
    }
  }

  async function handleSave() {
    if (!workspace || !chatbotId) return;
    setSaving(true);
    try {
      await updateChatbot(workspace.id, chatbotId, {
        name: reviewName,
        welcome_message: reviewWelcome,
        brand_color: reviewColor,
      } as Parameters<typeof updateChatbot>[2]);
      setStep("done");
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const embedCode = `<script src="${typeof window !== "undefined" ? window.location.origin : ""}/widget.js" data-key="${chatbotId}"></script>`;

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      {/* Progress bar */}
      <div className="flex items-center gap-2 mb-10">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2 flex-1">
            <div className="flex items-center gap-2">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  i < stepIndex
                    ? "bg-primary-600 text-white"
                    : i === stepIndex
                    ? "bg-primary-600 text-white"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {i < stepIndex ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              <span
                className={`text-sm font-medium hidden sm:block ${
                  i === stepIndex ? "text-gray-900" : "text-gray-400"
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px ${i < stepIndex ? "bg-primary-600" : "bg-gray-200"}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step: URL */}
      {step === "url" && (
        <Card>
          <CardContent className="pt-8 pb-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                <Globe className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Your website</h2>
                <p className="text-sm text-gray-500">We'll crawl it and set up your bot automatically.</p>
              </div>
            </div>

            <form onSubmit={handleStart} className="space-y-4">
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
                <Button type="submit" disabled={!url.trim()}>
                  Start setup
                  <ChevronRight className="ml-1.5 h-4 w-4" />
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Step: Crawling */}
      {step === "crawling" && (
        <Card>
          <CardContent className="pt-8 pb-8">
            <div className="flex flex-col items-center text-center gap-4 py-6">
              <Spinner className="h-10 w-10 text-primary-600" />
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Crawling your site…</h2>
                <p className="text-sm text-gray-500 mt-1">
                  {crawlStatus
                    ? `${crawlStatus.pages_discovered} pages found${crawlStatus.pages_queued > 0 ? `, ${crawlStatus.pages_queued} queued` : ""}`
                    : "Starting crawl…"}
                </p>
              </div>
              {crawlStatus && crawlStatus.pages_discovered > 0 && (
                <div className="w-full max-w-xs mt-2">
                  <div className="h-2 w-full rounded-full bg-gray-100">
                    <div
                      className="h-2 rounded-full bg-primary-600 transition-all duration-500"
                      style={{
                        width: crawlStatus.status === "running"
                          ? `${Math.min(85, (crawlStatus.pages_queued / Math.max(crawlStatus.pages_discovered, 1)) * 100)}%`
                          : "100%",
                      }}
                    />
                  </div>
                </div>
              )}
              <p className="text-xs text-gray-400 mt-2">This usually takes under a minute.</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Review */}
      {step === "review" && config && (
        <Card>
          <CardContent className="pt-8 pb-8">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gray-900">Your bot is ready</h2>
              <p className="text-sm text-gray-500 mt-1">We've configured it from your site. Review and save.</p>
            </div>

            <div className="space-y-4">
              <Input
                label="Bot name"
                value={reviewName}
                onChange={(e) => setReviewName(e.target.value)}
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Welcome message</label>
                <textarea
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  rows={2}
                  value={reviewWelcome}
                  onChange={(e) => setReviewWelcome(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Brand color</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={reviewColor}
                    onChange={(e) => setReviewColor(e.target.value)}
                    className="h-9 w-14 cursor-pointer rounded border border-gray-300 p-0.5"
                  />
                  <span className="text-sm text-gray-500 font-mono">{reviewColor}</span>
                </div>
              </div>
              {config.suggested_questions && config.suggested_questions.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Suggested questions</label>
                  <div className="flex flex-wrap gap-2">
                    {config.suggested_questions.map((q, i) => (
                      <span key={i} className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
                        {q}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {error && <p className="text-sm text-red-600 mt-4">{error}</p>}

            <div className="flex justify-end gap-3 pt-6">
              <Button variant="secondary" onClick={() => router.push("/chatbots")}>
                Skip
              </Button>
              <Button onClick={handleSave} loading={saving}>
                Save & finish
                <ChevronRight className="ml-1.5 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step: Done */}
      {step === "done" && (
        <Card>
          <CardContent className="pt-8 pb-8">
            <div className="flex flex-col items-center text-center gap-3 mb-8">
              <CheckCircle className="h-12 w-12 text-green-500" />
              <h2 className="text-lg font-semibold text-gray-900">You're live!</h2>
              <p className="text-sm text-gray-500">Add this snippet to your site to activate the widget.</p>
            </div>

            <div className="relative rounded-lg bg-gray-50 border border-gray-200 p-4">
              <code className="text-xs text-gray-700 break-all font-mono">{embedCode}</code>
              <button
                onClick={() => handleCopy(embedCode)}
                className="absolute top-3 right-3 flex items-center gap-1 rounded-md bg-white border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
              >
                {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>

            <div className="flex justify-end gap-3 pt-6">
              <Button variant="secondary" onClick={() => router.push("/chatbots")}>
                Back to bots
              </Button>
              <Button onClick={() => router.push(`/chatbots/${chatbotId}`)}>
                Open bot settings
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
