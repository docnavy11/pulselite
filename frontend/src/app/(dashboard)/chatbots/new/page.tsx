import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, CheckCircle, AlertTriangle, Copy, ChevronRight, ChevronDown, ChevronUp } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { Highlight, themes } from "prism-react-renderer";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { createChatbot, startCrawl, getChatbot, getCrawlStatus, updateChatbot } from "@/lib/api-functions";
import { useSocketEvent, getSocket } from "@/lib/socket";
import type { Chatbot, CrawlStatusResponse, CrawlProgressEvent, CrawlCompletedEvent, ChatbotStatusEvent } from "@/lib/types";

const APP_URL = import.meta.env.VITE_APP_URL || "http://localhost:3001";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const deployTabs = ["Script Tag", "Shareable Link", "REST API"] as const;
type DeployTab = (typeof deployTabs)[number];

// ── Shared UI helpers ──────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 transition-all duration-200"
    >
      {copied ? <><Check className="h-3.5 w-3.5 text-green-500" />Copied</> : <><Copy className="h-3.5 w-3.5" />Copy</>}
    </button>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <div className="relative rounded-lg overflow-hidden border border-gray-200">
      <div className="absolute top-2 right-2 z-10"><CopyButton text={code} /></div>
      <Highlight theme={themes.vsLight} code={code.trim()} language={language}>
        {({ className, style, tokens, getLineProps, getTokenProps }) => (
          <pre className={clsx(className, "p-4 text-sm overflow-auto")} style={style}>
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>{line.map((token, key) => <span key={key} {...getTokenProps({ token })} />)}</div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}

function StepRow({ stepNum, label, done, active, error, isLast, nextDone, children }: {
  stepNum: number; label: string; done: boolean; active: boolean; error?: boolean; isLast: boolean; nextDone: boolean; children?: React.ReactNode;
}) {
  return (
    <div className="flex gap-3.5">
      <div className="flex flex-col items-center" style={{ width: 26 }}>
        <div className={`w-[26px] h-[26px] rounded-full flex items-center justify-center flex-shrink-0 ${
          error ? "bg-amber-500" : done ? "bg-primary-500" : active ? "bg-primary-500" : "border-2 border-gray-300"
        }`}>
          {error ? <AlertTriangle className="h-3.5 w-3.5 text-white" />
            : done ? <Check className="h-3.5 w-3.5 text-white" />
            : <span className={`text-xs font-semibold ${active ? "text-white" : "text-gray-400"}`}>{stepNum}</span>}
        </div>
        {!isLast && <div className={`w-0.5 flex-1 min-h-[16px] ${done && nextDone ? "bg-primary-500" : "bg-gray-200"}`} />}
      </div>
      <div className="flex-1 pb-6">
        <div className="pt-0.5 mb-1">
          <span className={`text-sm font-medium ${done ? "text-gray-700" : active ? "text-gray-900" : "text-gray-400"}`}>{label}</span>
        </div>
        {(done || active) && children}
      </div>
    </div>
  );
}

const platformGuides = [
  { name: "WordPress", steps: ["Go to Appearance > Theme Editor or use a plugin like Insert Headers and Footers", "Paste the script tag before the closing </body> tag", "Save changes"] },
  { name: "Shopify", steps: ["Go to Online Store > Themes > Edit Code", "Open theme.liquid", "Paste the script tag before </body>"] },
  { name: "Webflow", steps: ["Go to Project Settings > Custom Code", "Paste the script in the Footer Code section", "Publish your site"] },
];

function getSetupStep(s: string | null | undefined): "crawling" | "configuring" | "failed" | "review" | "done" {
  if (!s || s === "done") return "done";
  if (s === "crawling") return "crawling";
  if (s === "configuring") return "configuring";
  if (s === "setup_failed") return "failed";
  if (s === "ready") return "review";
  return "done";
}

const toneOptions = ["professional", "friendly", "casual", "formal"];
const languageOptions = [
  { value: "en", label: "English" }, { value: "nl", label: "Dutch" }, { value: "fr", label: "French" },
  { value: "de", label: "German" }, { value: "es", label: "Spanish" },
];

// ── Main component ─────────────────────────────────────────────────────────

export default function NewBotWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  // Step 1 state
  const [url, setUrl] = useState("");
  const [botName, setBotName] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [starting, setStarting] = useState(false);

  // Once created, the chatbot drives steps 2-4
  const [chatbot, setChatbot] = useState<Chatbot | null>(null);
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatusResponse | null>(null);
  const chatbotId = chatbot?.id ?? null;

  // Review form (step 3)
  const [reviewName, setReviewName] = useState("");
  const [reviewWelcome, setReviewWelcome] = useState("");
  const [reviewSystemPrompt, setReviewSystemPrompt] = useState("");
  const [reviewFallback, setReviewFallback] = useState("");
  const [reviewColor, setReviewColor] = useState("#ff6b35");
  const [reviewTone, setReviewTone] = useState("professional");
  const [reviewLanguage, setReviewLanguage] = useState("en");
  const [reviewAutoDetect, setReviewAutoDetect] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Step 4
  const [step4Active, setStep4Active] = useState(false);
  const step4ActiveRef = useRef(false);
  step4ActiveRef.current = step4Active;
  const [activeDeployTab, setActiveDeployTab] = useState<DeployTab>("Script Tag");
  const [expandedGuide, setExpandedGuide] = useState<string | null>(null);
  const qrRef = useRef<HTMLDivElement>(null);

  // Configuring timeout
  const CONFIGURING_TIMEOUT_MS = 5 * 60 * 1000;
  const [configuringTimedOut, setConfiguringTimedOut] = useState(false);

  function inferName(rawUrl: string) {
    try { return new URL(rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`).hostname.replace(/^www\./, "").split(".")[0]; }
    catch { return ""; }
  }

  function populateReviewForm(bot: Chatbot) {
    setReviewName(bot.name ?? "");
    setReviewWelcome(bot.welcome_message ?? "");
    setReviewSystemPrompt(bot.system_prompt ?? "");
    setReviewFallback(bot.fallback_message ?? "");
    setReviewColor(bot.brand_color ?? "#ff6b35");
    setReviewTone(bot.tone ?? "professional");
    setReviewLanguage(bot.language ?? "en");
    setReviewAutoDetect(bot.auto_detect_language ?? false);
  }

  // ── Resume an in-progress setup (from /chatbots/:id/setup redirect) ────

  const resumed = useRef(false);
  useEffect(() => {
    const resumeId = searchParams.get("resume");
    if (!resumeId || !workspace || resumed.current) return;
    resumed.current = true;
    getChatbot(workspace.id, resumeId).then((bot) => {
      setChatbot(bot);
      const step = getSetupStep(bot.setup_status);
      if (step === "done") { navigate(`/chatbots/${resumeId}`, { replace: true }); return; }
      if (step === "review") populateReviewForm(bot);
      if (step === "crawling" && bot.active_crawl_job_id) {
        getCrawlStatus(workspace.id, bot.active_crawl_job_id).then(setCrawlStatus).catch(() => {});
      }
      window.history.replaceState(null, "", `/chatbots/${resumeId}/setup`);
    }).catch(() => { navigate("/chatbots", { replace: true }); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace]);

  // ── Step 1: submit URL ───────────────────────────────────────────────────

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

  async function handleStart(e?: { preventDefault: () => void }, overrideUrl?: string, overrideName?: string) {
    e?.preventDefault();
    if (!workspace) return;
    setSubmitError("");
    setStarting(true);

    const rawUrl = overrideUrl ?? url;
    const rawName = overrideName ?? botName;
    const normalized = rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`;
    const name = rawName.trim() || inferName(normalized) || "My Bot";

    try {
      const bot = await createChatbot(workspace.id, { name });
      await startCrawl(workspace.id, normalized, [], [], bot.id);
      setChatbot(bot);
      // Update URL without navigating — keeps the same component mounted
      window.history.replaceState(null, "", `/chatbots/${bot.id}/setup`);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setStarting(false);
    }
  }

  // ── Real-time events (steps 2-3) ────────────────────────────────────────

  useSocketEvent<CrawlProgressEvent>("crawl:progress", (data) => {
    if (!chatbotId || data.chatbot_id !== chatbotId) return;
    setCrawlStatus((prev) => ({
      ...(prev ?? { job_id: data.job_id, error_message: null, docs_indexed: 0, docs_total: 0, docs_failed: 0, docs_skipped: 0, stalled: false, phase: null }),
      pages_discovered: data.pages_discovered, pages_queued: data.pages_queued, pages_failed: data.pages_failed, phase: data.phase, status: "running",
    }));
  });

  useSocketEvent<CrawlCompletedEvent>("crawl:completed", (data) => {
    if (!chatbotId || data.chatbot_id !== chatbotId) return;
    setCrawlStatus((prev) => prev ? { ...prev, pages_queued: data.pages_queued, pages_failed: data.pages_failed, error_message: data.error_message ?? null, status: data.status, phase: null } : prev);
  });

  useSocketEvent<ChatbotStatusEvent>("chatbot:status_changed", (data) => {
    if (!chatbotId || data.chatbot_id !== chatbotId) return;
    setChatbot((prev) => prev ? { ...prev, setup_status: data.setup_status, setup_error: data.setup_error ?? prev.setup_error } : prev);
    const step = getSetupStep(data.setup_status);
    if (step === "review" && workspace) {
      getChatbot(workspace.id, data.chatbot_id).then((bot) => { setChatbot(bot); populateReviewForm(bot); }).catch(() => {});
    }
    if (step === "done" && !step4ActiveRef.current) {
      navigate(`/chatbots/${chatbotId}`, { replace: true });
    }
  });

  // Configuring timeout
  useEffect(() => {
    if (getSetupStep(chatbot?.setup_status) !== "configuring") { setConfiguringTimedOut(false); return; }
    const timer = setTimeout(() => setConfiguringTimedOut(true), CONFIGURING_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [chatbot?.setup_status]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling fallback
  useEffect(() => {
    const step = getSetupStep(chatbot?.setup_status);
    if (step !== "crawling" && step !== "configuring") return;
    if (!workspace || !chatbotId) return;
    const interval = setInterval(() => {
      getChatbot(workspace.id, chatbotId).then((bot) => {
        const newStep = getSetupStep(bot.setup_status);
        if (newStep !== step) { setChatbot(bot); if (newStep === "review") populateReviewForm(bot); if (newStep === "done") navigate(`/chatbots/${chatbotId}`, { replace: true }); }
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [chatbot?.setup_status, workspace, chatbotId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reconnect handler
  useEffect(() => {
    const s = getSocket();
    const onReconnect = () => {
      if (!workspace || !chatbotId) return;
      getChatbot(workspace.id, chatbotId).then((bot) => {
        setChatbot(bot);
        const step = getSetupStep(bot.setup_status);
        if (step === "done" && !step4ActiveRef.current) navigate(`/chatbots/${chatbotId}`, { replace: true });
        if (step === "review") populateReviewForm(bot);
        if (step === "crawling" && bot.active_crawl_job_id) getCrawlStatus(workspace.id, bot.active_crawl_job_id).then(setCrawlStatus).catch(() => {});
      }).catch(() => {});
    };
    s.on("connect", onReconnect);
    return () => { s.off("connect", onReconnect); };
  }, [workspace, chatbotId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 3: save review ──────────────────────────────────────────────────

  async function handleSave() {
    if (!workspace || !chatbotId) return;
    setSaving(true);
    setSaveError(null);
    try {
      await updateChatbot(workspace.id, chatbotId, {
        name: reviewName, welcome_message: reviewWelcome, system_prompt: reviewSystemPrompt,
        fallback_message: reviewFallback, brand_color: reviewColor, tone: reviewTone,
        language: reviewLanguage, auto_detect_language: reviewAutoDetect, setup_status: "done",
      } as Parameters<typeof updateChatbot>[2]);
      setStep4Active(true);
    } catch { setSaveError("Failed to save. Please try again."); }
    finally { setSaving(false); }
  }

  // ── Derived state ────────────────────────────────────────────────────────

  const wizardStep = chatbot ? getSetupStep(chatbot.setup_status) : null;
  const activeStepNum = !chatbot ? 1
    : step4Active ? 4
    : wizardStep === "crawling" || wizardStep === "configuring" || wizardStep === "failed" ? 2
    : wizardStep === "review" ? 3
    : 1;

  const step1Done = !!chatbot;
  const step2Done = activeStepNum >= 3;
  const step3Done = activeStepNum >= 4;
  const step2Error = wizardStep === "failed" || (wizardStep === "crawling" && crawlStatus?.status === "failed");
  const languageLabel = languageOptions.find((l) => l.value === reviewLanguage)?.label ?? reviewLanguage;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">
      <h1 className="text-xl font-bold text-gray-900 mb-8">Setting up your bot</h1>

      <div className="space-y-0">
        {/* ── Step 1: Your website ─────────────────────────────────────── */}
        <StepRow stepNum={1} label="Your website" done={step1Done} active={!step1Done} isLast={false} nextDone={step2Done}>
          {step1Done ? (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <span className="text-sm text-green-700">{chatbot.name}</span>
            </div>
          ) : (
            <form onSubmit={(e) => handleStart(e)} className="space-y-4 mt-2">
              <Input label="Website URL" placeholder="https://acmecorp.com" value={url} onChange={(e) => setUrl(e.target.value)} autoFocus />
              <Input label="Bot name (optional)" placeholder={inferName(url) || "My Support Bot"} value={botName} onChange={(e) => setBotName(e.target.value)} />
              {submitError && <div className="flex items-center gap-2 text-sm text-red-600"><AlertTriangle className="h-4 w-4 shrink-0" />{submitError}</div>}
              <div className="flex justify-end pt-2">
                <Button type="submit" disabled={!url.trim() || starting} loading={starting}>Start setup<ChevronRight className="ml-1.5 h-4 w-4" /></Button>
              </div>
            </form>
          )}
        </StepRow>

        {/* ── Step 2: Crawl & analyse ──────────────────────────────────── */}
        <StepRow stepNum={2} label="Crawl & analyse" done={step2Done} active={activeStepNum === 2} error={step2Error} isLast={false} nextDone={step3Done}>
          {step2Done ? (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <span className="text-sm text-green-700">
                {crawlStatus?.pages_queued ?? chatbot?.crawl_progress?.pages_queued ?? 0} pages crawled · AI config ready
              </span>
            </div>
          ) : activeStepNum === 2 ? (
            <div className="space-y-4">
              {wizardStep === "failed" ? (
                <div className="text-center py-4">
                  <AlertTriangle className="h-10 w-10 text-amber-400 mx-auto mb-4" />
                  <h2 className="text-lg font-bold text-gray-900 mb-2">Autoconfig failed</h2>
                  <p className="text-sm text-gray-500 mb-2">{chatbot?.setup_error || "Your bot was created but couldn't be auto-configured."}</p>
                  <p className="text-sm text-gray-500 mb-6">You can set it up manually in settings.</p>
                  <Button onClick={() => navigate(`/chatbots/${chatbotId}`)}>Go to settings</Button>
                </div>
              ) : (() => {
                const pagesQueued = crawlStatus?.pages_queued ?? chatbot?.crawl_progress?.pages_queued ?? 0;
                const pagesDiscovered = crawlStatus?.pages_discovered ?? chatbot?.crawl_progress?.pages_discovered ?? 0;
                const docsIndexed = crawlStatus?.docs_indexed ?? 0;
                const docsTotal = crawlStatus?.docs_total ?? 0;
                const isCrawlFailed = crawlStatus?.status === "failed";
                const isIndexing = crawlStatus?.status === "completed" && docsTotal > 0;
                const crawlDone = wizardStep === "configuring";

                if (isCrawlFailed) return (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-700 space-y-3">
                    <div className="flex items-start gap-2"><AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" /><span>{crawlStatus?.error_message || "The crawl could not complete."}</span></div>
                    <p className="text-xs text-red-500">Your bot was created but has no knowledge base content.</p>
                    <div className="flex gap-2 pt-1">
                      <Button variant="secondary" onClick={() => { setChatbot(null); setStarting(false); setUrl(""); window.history.replaceState(null, "", "/chatbots/new"); }}>Start over</Button>
                      <Button variant="secondary" onClick={() => navigate(`/chatbots/${chatbotId}`)}>Go to settings</Button>
                    </div>
                  </div>
                );

                return (<>
                  {/* Discovering */}
                  <div className="flex items-center gap-3">
                    {crawlDone || pagesDiscovered > 0
                      ? <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                      : <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />}
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-700">Discovering pages</div>
                      {(crawlDone || pagesDiscovered > 0) && <div className="text-xs text-gray-400">{pagesDiscovered} pages found</div>}
                    </div>
                  </div>

                  {/* Fetching */}
                  {(crawlDone || pagesDiscovered > 0) && (
                    <div className="flex items-center gap-3">
                      {crawlDone || pagesQueued >= pagesDiscovered
                        ? <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                        : <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />}
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-700">Fetching pages</span>
                          <span className="text-xs text-gray-400">{pagesQueued} / {pagesDiscovered || pagesQueued}</span>
                        </div>
                        {!crawlDone && <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden"><div className="h-full bg-primary-400 rounded-full transition-all duration-500" style={{ width: pagesDiscovered > 0 ? `${(pagesQueued / pagesDiscovered) * 100}%` : "0%" }} /></div>}
                      </div>
                    </div>
                  )}

                  {/* Indexing */}
                  {(crawlDone || isIndexing) && (
                    <div className="flex items-center gap-3">
                      {crawlDone || docsIndexed >= docsTotal
                        ? <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
                        : <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />}
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-700">Indexing content</span>
                          {!crawlDone && <span className="text-xs text-gray-400">{docsIndexed} / {docsTotal}</span>}
                        </div>
                        {!crawlDone && <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden"><div className="h-full bg-primary-400 rounded-full transition-all duration-500" style={{ width: docsTotal > 0 ? `${(docsIndexed / docsTotal) * 100}%` : "0%" }} /></div>}
                      </div>
                    </div>
                  )}

                  {/* Configuring */}
                  {wizardStep === "configuring" && (
                    configuringTimedOut ? (
                      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm text-amber-700">
                        Configuration is taking longer than expected. You can keep waiting or{" "}
                        <button onClick={() => navigate(`/chatbots/${chatbotId}`)} className="underline font-medium">configure manually</button>.
                      </div>
                    ) : (
                      <div className="flex items-center gap-3">
                        <Spinner className="h-5 w-5 text-primary-500 flex-shrink-0" />
                        <span className="text-sm text-gray-600">AI is configuring your bot…</span>
                      </div>
                    )
                  )}
                </>);
              })()}
            </div>
          ) : null}
        </StepRow>

        {/* ── Step 3: Review config ────────────────────────────────────── */}
        <StepRow stepNum={3} label="Review config" done={step3Done} active={activeStepNum === 3} isLast={false} nextDone={false}>
          {step3Done ? (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <span className="text-sm text-green-700">{reviewName} · {reviewTone} · {languageLabel}</span>
            </div>
          ) : activeStepNum === 3 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Bot name</label><input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" value={reviewName} onChange={(e) => setReviewName(e.target.value)} /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Welcome message</label><textarea className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none" rows={3} value={reviewWelcome} onChange={(e) => setReviewWelcome(e.target.value)} /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">System prompt</label><textarea className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none" rows={5} value={reviewSystemPrompt} onChange={(e) => setReviewSystemPrompt(e.target.value)} /><p className="text-[11px] text-gray-400 mt-1">Behavioral guidance only — persona, tone, scope. No specific facts.</p></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Fallback message</label><textarea className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none" rows={2} value={reviewFallback} onChange={(e) => setReviewFallback(e.target.value)} /><p className="text-[11px] text-gray-400 mt-1">Shown when the bot cannot find a confident answer.</p></div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
                <div className="flex flex-wrap gap-2">
                  {toneOptions.map((t) => <button key={t} onClick={() => setReviewTone(t)} className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${reviewTone === t ? "bg-primary-50 border-primary-300 text-primary-700" : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"}`}>{t.charAt(0).toUpperCase() + t.slice(1)}</button>)}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{reviewAutoDetect ? "Fallback language" : "Language"}</label>
                <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" value={reviewLanguage} onChange={(e) => setReviewLanguage(e.target.value)}>
                  {languageOptions.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
                <label className="flex items-center gap-2 mt-2"><input type="checkbox" checked={reviewAutoDetect} onChange={(e) => setReviewAutoDetect(e.target.checked)} className="rounded border-gray-300" /><span className="text-sm text-gray-600">Auto-detect visitor language</span></label>
              </div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Brand color</label><div className="flex items-center gap-3"><input type="color" className="h-9 w-14 rounded border border-gray-300 p-0.5 cursor-pointer" value={reviewColor} onChange={(e) => setReviewColor(e.target.value)} /><span className="text-sm text-gray-500 font-mono">{reviewColor}</span></div></div>
              {saveError && <p className="text-sm text-red-600">{saveError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <Button variant="secondary" onClick={() => navigate(`/chatbots/${chatbotId}`)}>Skip</Button>
                <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save & finish"}</Button>
              </div>
            </div>
          ) : null}
        </StepRow>

        {/* ── Step 4: Go live ──────────────────────────────────────────── */}
        <StepRow stepNum={4} label="Go live" done={false} active={activeStepNum === 4} isLast={true} nextDone={false}>
          {activeStepNum === 4 && chatbot ? (() => {
            const scriptTag = `<script src="${window.location.origin}/widget/${chatbot.id}.js"></script>`;
            const chatUrl = `${APP_URL}/chat/${chatbot.id}`;
            const curlExample = `curl -X POST ${API_URL}/api/v1/public/chat \\\n  -H "Content-Type: application/json" \\\n  -d '{\n    "chatbot_id": "${chatbot.id}",\n    "message": "Hello, I need help",\n    "session_id": "unique-session-id"\n  }'`;

            return (
              <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
                <div className="border-b border-gray-200">
                  <nav className="flex gap-5">
                    {deployTabs.map((tab) => <button key={tab} onClick={() => setActiveDeployTab(tab)} className={clsx("pb-2.5 text-sm font-medium border-b-2 transition-all duration-200", activeDeployTab === tab ? "border-primary-500 text-primary-500" : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300")}>{tab}</button>)}
                  </nav>
                </div>

                {activeDeployTab === "Script Tag" && (
                  <div className="space-y-4">
                    <div><p className="text-sm text-gray-500 mb-3">Add this script tag to your website to display the chat widget.</p><CodeBlock code={scriptTag} language="html" /></div>
                    <div>
                      <h3 className="text-sm font-medium text-gray-700 mb-2">Platform guides</h3>
                      <div className="space-y-1.5">
                        {platformGuides.map((guide) => (
                          <div key={guide.name} className="rounded-lg border border-gray-200">
                            <button onClick={() => setExpandedGuide(expandedGuide === guide.name ? null : guide.name)} className="flex w-full items-center justify-between px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all duration-200">
                              {guide.name}
                              {expandedGuide === guide.name ? <ChevronUp className="h-4 w-4 text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-400" />}
                            </button>
                            {expandedGuide === guide.name && <div className="px-3 pb-2.5"><ol className="list-decimal list-inside space-y-1 text-sm text-gray-600">{guide.steps.map((s, i) => <li key={i}>{s}</li>)}</ol></div>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {activeDeployTab === "Shareable Link" && (
                  <div className="space-y-4">
                    <div><p className="text-sm text-gray-500 mb-3">Share this link to let users chat with your bot.</p><div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2.5"><code className="flex-1 text-sm text-gray-700 truncate">{chatUrl}</code><CopyButton text={chatUrl} /></div></div>
                    <div ref={qrRef} className="flex flex-col items-center pt-2">
                      <QRCodeSVG value={chatUrl} size={160} level="M" />
                      <p className="text-xs text-gray-400 mt-3">Scan to open chat</p>
                      <button onClick={() => { const svg = qrRef.current?.querySelector("svg") as SVGSVGElement; if (!svg) return; const d = new XMLSerializer().serializeToString(svg); const b = new Blob([d], { type: "image/svg+xml" }); const u = URL.createObjectURL(b); const a = document.createElement("a"); a.href = u; a.download = `chatbot-qr-${chatbot.id}.svg`; a.click(); URL.revokeObjectURL(u); }} className="mt-2 text-sm text-primary-500 hover:text-primary-700 font-medium">Download QR Code</button>
                    </div>
                  </div>
                )}

                {activeDeployTab === "REST API" && (
                  <div><p className="text-sm text-gray-500 mb-3">Send chat messages programmatically.</p><CodeBlock code={curlExample} language="bash" /></div>
                )}

                <div className="flex justify-end pt-1"><Button onClick={() => navigate(`/chatbots/${chatbot.id}`)}>Go to dashboard</Button></div>
              </div>
            );
          })() : null}
        </StepRow>
      </div>
    </div>
  );
}
