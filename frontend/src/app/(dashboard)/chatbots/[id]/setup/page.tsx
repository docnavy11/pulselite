import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { CheckCircle, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { getChatbot, getCrawlStatus, updateChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { Chatbot, CrawlStatusResponse } from "@/lib/types";

// Maps setup_status to a wizard step
function getSetupStep(
  s: string | null | undefined,
): "crawling" | "configuring" | "failed" | "review" | "done" {
  if (!s || s === "done") return "done";
  if (s === "crawling") return "crawling";
  if (s === "configuring") return "configuring";
  if (s === "setup_failed") return "failed";
  if (s === "ready") return "review";
  return "done";
}

export default function ChatbotSetupPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [chatbot, setChatbot] = useState<Chatbot | null>(null);
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatusResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Review form state (step "ready")
  const [reviewName, setReviewName] = useState("");
  const [reviewWelcome, setReviewWelcome] = useState("");
  const [reviewSystemPrompt, setReviewSystemPrompt] = useState("");
  const [reviewFallback, setReviewFallback] = useState("");
  const [reviewColor, setReviewColor] = useState("#ff6b35");
  const [reviewTone, setReviewTone] = useState("professional");
  const [reviewLanguage, setReviewLanguage] = useState("en");
  const [saving, setSaving] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const configuringStartRef = useRef<number | null>(null);
  const CONFIGURING_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Load chatbot on mount
  useEffect(() => {
    if (!workspace || !id) return;
    getChatbot(workspace.id, id)
      .then((bot) => {
        setChatbot(bot);
        const step = getSetupStep(bot.setup_status);
        if (step === "done") {
          navigate(`/chatbots/${id}`, { replace: true });
          return;
        }
        if (step === "review") {
          populateReviewForm(bot);
        }
        if (step === "crawling" && bot.active_crawl_job_id) {
          startCrawlPolling(bot.active_crawl_job_id);
        }
        if (step === "configuring") {
          configuringStartRef.current = Date.now();
          startConfiguringPolling();
        }
      })
      .catch(() => setLoadError("Failed to load chatbot"));
  }, [workspace, id]); // eslint-disable-line react-hooks/exhaustive-deps

  function populateReviewForm(bot: Chatbot) {
    setReviewName(bot.name ?? "");
    setReviewWelcome(bot.welcome_message ?? "");
    setReviewSystemPrompt(bot.system_prompt ?? "");
    setReviewFallback(bot.fallback_message ?? "");
    setReviewColor(bot.brand_color ?? "#ff6b35");
    setReviewTone(bot.tone ?? "professional");
    setReviewLanguage((bot as Chatbot & { language?: string }).language ?? "en");
  }

  function startCrawlPolling(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      if (!workspace || !id) return;
      try {
        const status = await getCrawlStatus(workspace.id, jobId);
        setCrawlStatus(status);
        if (status.status === "failed") {
          clearInterval(pollRef.current!);
          return;
        }
        // Crawl done + docs settled → refetch chatbot to get updated setup_status
        const docsTotal = status.docs_total ?? 0;
        const docsDone = (status.docs_indexed ?? 0) + (status.docs_failed ?? 0) + (status.docs_skipped ?? 0);
        if (status.status === "completed" && docsTotal > 0 && docsDone >= docsTotal) {
          clearInterval(pollRef.current!);
          const bot = await getChatbot(workspace.id, id);
          setChatbot(bot);
          const step = getSetupStep(bot.setup_status);
          if (step === "configuring") {
            configuringStartRef.current = Date.now();
            startConfiguringPolling();
          } else if (step === "review") {
            populateReviewForm(bot);
          }
        }
      } catch {
        // network blip — keep polling
      }
    }, 2000);
  }

  function startConfiguringPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      if (!workspace || !id) return;
      // Timeout check
      if (configuringStartRef.current && Date.now() - configuringStartRef.current > CONFIGURING_TIMEOUT_MS) {
        clearInterval(pollRef.current!);
        return; // UI will show timeout message based on elapsed time
      }
      try {
        const bot = await getChatbot(workspace.id, id);
        setChatbot(bot);
        const step = getSetupStep(bot.setup_status);
        if (step === "review") {
          clearInterval(pollRef.current!);
          populateReviewForm(bot);
        } else if (step === "failed" || step === "done") {
          clearInterval(pollRef.current!);
          if (step === "done") navigate(`/chatbots/${id}`, { replace: true });
        }
      } catch {
        // network blip
      }
    }, 3000);
  }

  async function handleSave() {
    if (!workspace || !id) return;
    setSaving(true);
    try {
      await updateChatbot(workspace.id, id, {
        name: reviewName,
        welcome_message: reviewWelcome,
        system_prompt: reviewSystemPrompt,
        fallback_message: reviewFallback,
        brand_color: reviewColor,
        tone: reviewTone,
        setup_status: "done",
      } as Parameters<typeof updateChatbot>[2]);
      navigate(`/chatbots/${id}`);
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <p className="text-sm text-red-500">{loadError}</p>
        <Button variant="secondary" onClick={() => navigate("/chatbots")}>Back to bots</Button>
      </div>
    );
  }

  if (!chatbot) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  const step = getSetupStep(chatbot.setup_status);
  const isConfiguringTimedOut =
    step === "configuring" &&
    configuringStartRef.current !== null &&
    Date.now() - configuringStartRef.current > CONFIGURING_TIMEOUT_MS;

  // ── Step: crawling ──────────────────────────────────────────────────────────
  if (step === "crawling") {
    const pagesQueued = crawlStatus?.pages_queued ?? chatbot.crawl_progress?.pages_queued ?? 0;
    const pagesDiscovered = crawlStatus?.pages_discovered ?? chatbot.crawl_progress?.pages_discovered ?? 0;
    const docsIndexed = crawlStatus?.docs_indexed ?? 0;
    const docsTotal = crawlStatus?.docs_total ?? 0;
    const isFailed = crawlStatus?.status === "failed";
    const isIndexing = crawlStatus?.status === "completed" && docsTotal > 0;

    return (
      <div className="max-w-lg mx-auto py-16 px-4">
        <div className="text-center mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">
            {isFailed ? "Crawl failed" : "Crawling website…"}
          </h2>
          <p className="text-sm text-gray-400 truncate">{chatbot.name}</p>
        </div>

        {isFailed ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-700 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{crawlStatus?.error_message || "The crawl could not complete."}</span>
            </div>
            <p className="text-xs text-red-500">
              Your bot was created but has no knowledge base content. You can delete it and start over, or configure it manually.
            </p>
            <div className="flex gap-2 pt-1">
              <Button variant="secondary" onClick={() => navigate("/chatbots/new")}>Start over</Button>
              <Button variant="secondary" onClick={() => navigate(`/chatbots/${id}`)}>Go to settings</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Discovering */}
            <div className="flex items-center gap-3">
              {pagesDiscovered > 0 ? (
                <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
              ) : (
                <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />
              )}
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-700">Discovering pages</div>
                {pagesDiscovered > 0 && (
                  <div className="text-xs text-gray-400">{pagesDiscovered} pages found</div>
                )}
              </div>
            </div>

            {/* Fetching */}
            {pagesDiscovered > 0 && (
              <div className="flex items-center gap-3">
                {pagesQueued >= pagesDiscovered ? (
                  <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : (
                  <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">Fetching pages</span>
                    <span className="text-xs text-gray-400">{pagesQueued} / {pagesDiscovered}</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-400 rounded-full transition-all duration-500"
                      style={{ width: pagesDiscovered > 0 ? `${(pagesQueued / pagesDiscovered) * 100}%` : "0%" }}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Indexing */}
            {isIndexing && (
              <div className="flex items-center gap-3">
                {docsIndexed >= docsTotal ? (
                  <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : (
                  <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">Indexing content</span>
                    <span className="text-xs text-gray-400">{docsIndexed} / {docsTotal}</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-400 rounded-full transition-all duration-500"
                      style={{ width: docsTotal > 0 ? `${(docsIndexed / docsTotal) * 100}%` : "0%" }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── Step: configuring ───────────────────────────────────────────────────────
  if (step === "configuring") {
    return (
      <div className="max-w-lg mx-auto py-16 px-4 text-center">
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-1">AI is configuring your bot…</h2>
          <p className="text-sm text-gray-400 truncate">{chatbot.name}</p>
        </div>
        {isConfiguringTimedOut ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm text-amber-700">
            Configuration is taking longer than expected. You can keep waiting or{" "}
            <button
              onClick={() => navigate(`/chatbots/${id}`)}
              className="underline font-medium"
            >
              configure manually in settings
            </button>.
          </div>
        ) : (
          <Spinner className="h-8 w-8 text-primary-500 mx-auto" />
        )}
      </div>
    );
  }

  // ── Step: setup_failed ──────────────────────────────────────────────────────
  if (step === "failed") {
    return (
      <div className="max-w-lg mx-auto py-16 px-4 text-center">
        <AlertTriangle className="h-10 w-10 text-red-400 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Autoconfig failed</h2>
        <p className="text-sm text-gray-500 mb-6">
          Your bot was created but couldn't be auto-configured. You can set it up manually in settings.
        </p>
        <Button onClick={() => navigate(`/chatbots/${id}`)}>Go to settings →</Button>
      </div>
    );
  }

  // ── Step: review ────────────────────────────────────────────────────────────
  const toneOptions = ["professional", "friendly", "casual", "formal"];
  const languageOptions = [
    { value: "en", label: "English" },
    { value: "nl", label: "Dutch" },
    { value: "fr", label: "French" },
    { value: "de", label: "German" },
    { value: "es", label: "Spanish" },
  ];

  return (
    <div className="max-w-lg mx-auto py-16 px-4">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-green-100 mb-4">
          <CheckCircle className="h-6 w-6 text-green-500" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">Review your bot</h2>
        <p className="text-sm text-gray-400 mt-1">Edit anything before saving.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
        {/* Bot name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Bot name</label>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            value={reviewName}
            onChange={(e) => setReviewName(e.target.value)}
          />
        </div>

        {/* Welcome message */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Welcome message</label>
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
            rows={3}
            value={reviewWelcome}
            onChange={(e) => setReviewWelcome(e.target.value)}
          />
        </div>

        {/* System prompt */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">System prompt</label>
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
            rows={5}
            value={reviewSystemPrompt}
            onChange={(e) => setReviewSystemPrompt(e.target.value)}
          />
          <p className="text-[11px] text-gray-400 mt-1">
            Behavioral guidance only — persona, tone, scope. No specific facts.
          </p>
        </div>

        {/* Fallback message */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Fallback message</label>
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
            rows={2}
            value={reviewFallback}
            onChange={(e) => setReviewFallback(e.target.value)}
          />
          <p className="text-[11px] text-gray-400 mt-1">
            Shown when the bot cannot find a confident answer.
          </p>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
          <div className="flex flex-wrap gap-2">
            {toneOptions.map((t) => (
              <button
                key={t}
                onClick={() => setReviewTone(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  reviewTone === t
                    ? "bg-primary-50 border-primary-300 text-primary-700"
                    : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Language */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
          <select
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            value={reviewLanguage}
            onChange={(e) => setReviewLanguage(e.target.value)}
          >
            {languageOptions.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>

        {/* Brand color */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Brand color</label>
          <div className="flex items-center gap-3">
            <input
              type="color"
              className="h-9 w-14 rounded border border-gray-300 p-0.5 cursor-pointer"
              value={reviewColor}
              onChange={(e) => setReviewColor(e.target.value)}
            />
            <span className="text-sm text-gray-500 font-mono">{reviewColor}</span>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3 mt-6">
        <Button variant="secondary" onClick={() => navigate(`/chatbots/${id}`)}>
          Skip
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save & finish"}
        </Button>
      </div>
    </div>
  );
}
