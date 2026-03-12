import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Globe, CheckCircle, ChevronRight, Copy, Check, AlertTriangle, RefreshCw } from "lucide-react";
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

const TONE_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: "professional", label: "Professional", description: "Formal and business-like" },
  { value: "friendly",     label: "Friendly",     description: "Warm and approachable" },
  { value: "casual",       label: "Casual",       description: "Relaxed and conversational" },
  { value: "formal",       label: "Formal",       description: "Strict and authoritative" },
];

const LANG_NAMES: Record<string, string> = {
  en: "English", nl: "Dutch", fr: "French", de: "German",
  es: "Spanish", pt: "Portuguese", it: "Italian", pl: "Polish",
  ru: "Russian", tr: "Turkish", ar: "Arabic", zh: "Chinese",
  ja: "Japanese", ko: "Korean", sv: "Swedish", da: "Danish",
  no: "Norwegian", fi: "Finnish", cs: "Czech", ro: "Romanian",
};

const PLATFORM_GUIDES: { id: string; name: string; logo: string; steps: string[] }[] = [
  {
    id: "wordpress",
    name: "WordPress",
    logo: "W",
    steps: [
      "Install the free plugin <strong>Insert Headers and Footers</strong> (WPCode).",
      "Go to <strong>Code Snippets → Header & Footer</strong> in your WP admin.",
      "Paste the snippet into the <strong>Footer</strong> section.",
      "Click <strong>Save Changes</strong>. The widget appears on all pages.",
    ],
  },
  {
    id: "shopify",
    name: "Shopify",
    logo: "S",
    steps: [
      "In your Shopify admin, go to <strong>Online Store → Themes</strong>.",
      "Click <strong>⋯ Actions → Edit code</strong> on your active theme.",
      "Open <strong>Layout → theme.liquid</strong>.",
      "Paste the snippet just before <code>&lt;/body&gt;</code> and click <strong>Save</strong>.",
    ],
  },
  {
    id: "wix",
    name: "Wix",
    logo: "X",
    steps: [
      "In the Wix Editor, click <strong>Settings → Custom Code</strong>.",
      "Click <strong>+ Add Custom Code</strong> at the bottom of the page.",
      "Paste the snippet, set placement to <strong>Body — end</strong>.",
      "Set it to load on <strong>All pages</strong> and click <strong>Apply</strong>.",
    ],
  },
  {
    id: "squarespace",
    name: "Squarespace",
    logo: "⬜",
    steps: [
      "Go to <strong>Settings → Advanced → Code Injection</strong>.",
      "Paste the snippet into the <strong>Footer</strong> text area.",
      "Click <strong>Save</strong>. Changes apply site-wide instantly.",
    ],
  },
  {
    id: "webflow",
    name: "Webflow",
    logo: "W",
    steps: [
      "Open your project and go to <strong>Project Settings → Custom Code</strong>.",
      "Paste the snippet into the <strong>Footer Code</strong> box.",
      "Click <strong>Save Changes</strong>, then <strong>Publish</strong> your site.",
    ],
  },
  {
    id: "html",
    name: "Plain HTML",
    logo: "</> ",
    steps: [
      "Open your HTML file (e.g., <code>index.html</code>).",
      "Paste the snippet just before the closing <code>&lt;/body&gt;</code> tag.",
      "Save the file and upload it to your hosting provider.",
    ],
  },
];

export default function NewBotWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [step, setStep] = useState<Step>("url");
  const [url, setUrl] = useState("");
  const [botName, setBotName] = useState("");
  const [error, setError] = useState("");

  // crawling state
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatusResponse | null>(null);
  const [autoconfigRunning, setAutoconfigRunning] = useState(false);
  const [autoconfigError, setAutoconfigError] = useState("");
  const [crawlJobId, setCrawlJobId] = useState("");
  const [crawlKbId, setCrawlKbId] = useState("");
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const pollStartRef = useRef<number>(0);
  const POLL_TIMEOUT_MS = 10 * 60 * 1000; // 10 min client-side safety net
  const [elapsedSec, setElapsedSec] = useState(0);
  const elapsedRef = useRef<NodeJS.Timeout | null>(null);

  // result state
  const [config, setConfig] = useState<AutoConfigResponse | null>(null);
  const [chatbotId, setChatbotId] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activePlatform, setActivePlatform] = useState("wordpress");

  // editable review fields
  const [reviewName, setReviewName] = useState("");
  const [reviewWelcome, setReviewWelcome] = useState("");
  const [reviewColor, setReviewColor] = useState("");
  const [reviewTone, setReviewTone] = useState("professional");
  const [reviewLanguage, setReviewLanguage] = useState("en");

  // back-navigation state
  const [editingStep1, setEditingStep1] = useState(false);
  const [editingStep3, setEditingStep3] = useState(false);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (elapsedRef.current) clearInterval(elapsedRef.current);
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

    const rawUrl = overrideUrl ?? url;
    const rawName = overrideName ?? botName;
    const normalized = rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`;
    const name = rawName.trim() || inferName(normalized) || "My Bot";

    try {
      setStep("crawling");

      const chatbot = await createChatbot(workspace.id, { name });
      setChatbotId(chatbot.id);

      const crawl = await startCrawl(workspace.id, normalized, [], [], chatbot.id);
      setCrawlJobId(crawl.job_id);
      setCrawlKbId(crawl.kb_id);
      setCrawlStatus({ job_id: crawl.job_id, status: "pending", phase: null, error_message: null, pages_discovered: crawl.pages_discovered, pages_queued: 0, pages_failed: 0, docs_indexed: 0, docs_total: 0, docs_failed: 0, docs_skipped: 0, stalled: false });

      pollStartRef.current = Date.now();
      setElapsedSec(0);
      elapsedRef.current = setInterval(() => {
        setElapsedSec(Math.floor((Date.now() - pollStartRef.current) / 1000));
      }, 1000);
      pollRef.current = setInterval(async () => {
        // Client-side timeout safety net
        if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) {
          clearInterval(pollRef.current!);
          setCrawlStatus((prev: CrawlStatusResponse | null) => prev ? { ...prev, stalled: true } : prev);
          return;
        }
        try {
          const status = await getCrawlStatus(workspace.id, crawl.job_id);
          setCrawlStatus(status);

          if (status.status === "failed") {
            clearInterval(pollRef.current!);
            clearInterval(elapsedRef.current!);
            // error_message from backend is surfaced in the UI — stay on crawling step
            return;
          }

          // Backend-detected stall — stop polling, let UI show the stalled state
          if (status.stalled) {
            clearInterval(pollRef.current!);
            return;
          }

          // All docs settled (indexed + failed) — ready to proceed even if some failed
          const crawlDone = status.status === "completed";
          const docsSettled = status.docs_total > 0 &&
            (status.docs_indexed + status.docs_failed) >= status.docs_total;

          if (crawlDone && docsSettled) {
            clearInterval(pollRef.current!);
            clearInterval(elapsedRef.current!);
            if (status.docs_indexed === 0) {
              setError("All pages failed to index. The site may block crawlers.");
              setStep("url");
              return;
            }
            setAutoconfigRunning(true);
            setAutoconfigError("");
            try {
              const result = await runAutoconfig(workspace.id, chatbot.id, crawl.kb_id);
              setConfig(result);
              setReviewName(result.name);
              setReviewWelcome(result.welcome_message ?? "");
              setReviewColor(result.brand_color ?? "#ff6b35");
              setReviewTone(result.tone ?? "professional");
              setReviewLanguage(result.language ?? "en");
              setStep("review");
            } catch (acErr: unknown) {
              const msg = acErr instanceof Error ? acErr.message : "AI configuration failed.";
              setAutoconfigError(msg);
            } finally {
              setAutoconfigRunning(false);
            }
          }
        } catch {
          // Network blip — don't abort, just keep polling
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
        tone: reviewTone,
        language: reviewLanguage,
      } as Parameters<typeof updateChatbot>[2]);
      setStep("done");
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleRestart() {
    if (pollRef.current) clearInterval(pollRef.current);
    if (elapsedRef.current) clearInterval(elapsedRef.current);
    setElapsedSec(0);
    setCrawlStatus(null);
    setCrawlJobId("");
    setCrawlKbId("");
    setAutoconfigRunning(false);
    setAutoconfigError("");
    setConfig(null);
    setChatbotId("");
    setReviewName("");
    setReviewWelcome("");
    setReviewColor("");
    setReviewTone("professional");
    setReviewLanguage("en");
    setEditingStep1(false);
    setEditingStep3(false);
    setStep("url");
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const STEP_ORDER: Step[] = ["url", "crawling", "review", "done"];
  const stepIndex = STEP_ORDER.indexOf(step);
  const embedCode = `<script src="https://cdn.pulse.ai/widget.js" data-key="${chatbotId}"></script>`;
  const activePlatformGuide = PLATFORM_GUIDES.find((p) => p.id === activePlatform)!;

  // Timeline derived state
  const step2Done =
    (step === "review" || step === "done") &&
    !crawlStatus?.stalled &&
    !autoconfigError;
  const step2Error = step === "crawling" && (!!crawlStatus?.stalled || !!autoconfigError);

  const step1Completed = stepIndex > 0;
  const step2Completed = step2Done;
  const step3Completed = step === "done";

  const line12Color = step1Completed && step2Completed ? "bg-primary-500" : "bg-gray-200";
  const line23Color = step2Completed && step3Completed ? "bg-primary-500" : "bg-gray-200";
  const line34Color = step3Completed ? "bg-primary-500" : "bg-gray-200";

  const hostnameChip = (() => {
    try {
      return new URL(url.startsWith("http") ? url : `https://${url}`)
        .hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  })();

  // Phase states for crawling step
  const crawlPct = !crawlStatus || crawlStatus.status === "pending"
    ? 5
    : crawlStatus.status === "completed"
    ? 100
    : Math.min(95, (crawlStatus.pages_queued / Math.max(crawlStatus.pages_discovered, 1)) * 100);

  const indexPct = !crawlStatus || crawlStatus.docs_total === 0
    ? 0
    : Math.round((crawlStatus.docs_indexed / crawlStatus.docs_total) * 100);

  const crawlComplete = crawlStatus?.status === "completed" || (crawlStatus?.status === "running" && crawlPct === 100);
  const indexComplete = indexPct === 100 && crawlStatus!?.docs_total > 0;

  // ─── helper: spine circle ────────────────────────────────────────────
  const circleBase = "flex h-[26px] w-[26px] items-center justify-center rounded-full text-[11px] font-bold flex-shrink-0";

  return (
    <div className="max-w-2xl mx-auto py-10 px-4">

      {/* ── STEP 1: Your website ── */}
      <div className="flex gap-3.5">
        {/* spine */}
        <div className="flex flex-col items-center w-[26px] flex-shrink-0">
          <div className={`${circleBase} ${
            step1Completed && !editingStep1
              ? "bg-primary-500 text-white"
              : editingStep1
              ? "bg-amber-500 text-white"
              : "bg-primary-500 text-white"
          }`}>
            {step1Completed && !editingStep1 ? <Check className="h-3.5 w-3.5" /> : "1"}
          </div>
          <div className={`w-0.5 flex-1 min-h-[20px] mt-1 ${line12Color}`} />
        </div>
        {/* content */}
        <div className={`flex-1 pb-3 ${editingStep1 ? "opacity-100" : ""}`}>
          {/* Active: URL form */}
          {step === "url" && !editingStep1 && (
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
                    <Button type="submit" disabled={!url.trim()}>
                      Start setup
                      <ChevronRight className="ml-1.5 h-4 w-4" />
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {/* Collapsed chip (step 1 done, not editing) */}
          {step1Completed && !editingStep1 && (
            <button
              onClick={() => step2Done ? setEditingStep1(true) : undefined}
              className={`w-full text-left bg-green-50 border border-green-200 rounded-lg px-3 py-2 flex justify-between items-center group ${
                step2Done ? "cursor-pointer" : "cursor-default"
              }`}
            >
              <div>
                <p className="text-[11px] font-semibold text-green-800">Your website</p>
                <p className="text-[10px] text-green-700 mt-0.5">
                  {hostnameChip} · {botName || inferName(url) || "My Bot"}
                </p>
              </div>
              {step2Done && (
                <span className="text-[10px] text-green-600 opacity-0 group-hover:opacity-60 transition-opacity">edit ✎</span>
              )}
            </button>
          )}

          {/* Back-navigation: step 1 reopened with warning */}
          {editingStep1 && (
            <Card className="border-2 border-amber-400 ring-4 ring-amber-50">
              <CardContent className="pt-6 pb-6">
                <p className="text-[12px] font-semibold text-amber-800 mb-3">Your website</p>
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4 text-[11px] text-amber-800">
                  ⚠ Changing the URL will restart the crawl and discard the current config.
                </div>
                <Input
                  label="Website URL"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  autoFocus
                />
                <div className="flex gap-2 mt-4">
                  <Button variant="secondary" onClick={() => setEditingStep1(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      handleRestart();
                      handleStart(undefined, url, botName);
                    }}
                    disabled={!url.trim()}
                  >
                    Restart with new URL →
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ── STEP 2: Crawl & analyse ── */}
      <div className={`flex gap-3.5 ${editingStep1 ? "opacity-40 pointer-events-none" : ""}`}>
        {/* spine */}
        <div className="flex flex-col items-center w-[26px] flex-shrink-0">
          <div className={`${circleBase} ${
            step2Error
              ? "bg-amber-500 text-white"
              : step2Completed
              ? "bg-primary-500 text-white"
              : step === "crawling"
              ? "bg-primary-500 text-white"
              : "bg-white border-2 border-gray-200 text-gray-400"
          }`}>
            {step2Completed ? <Check className="h-3.5 w-3.5" /> : "2"}
          </div>
          <div className={`w-0.5 flex-1 min-h-[20px] mt-1 ${line23Color}`} />
        </div>
        {/* content */}
        <div className="flex-1 pb-3">
          {/* Pending label */}
          {stepIndex < 1 && (
            <p className="text-[11px] font-medium text-gray-400 pt-1">Crawl &amp; analyse</p>
          )}

          {/* Active: crawling card */}
          {step === "crawling" && (() => {
            const isFailed = crawlStatus?.status === "failed";
            const isDiscovering = !isFailed && (crawlStatus?.phase === "discovering" || (!crawlStatus?.phase && crawlStatus?.status === "running" && !crawlStatus?.pages_discovered));
            const isFetching = !isFailed && (crawlStatus?.phase === "fetching" || (crawlStatus?.status === "running" && (crawlStatus?.pages_discovered ?? 0) > 0));
            const isIndexing = !isFailed && (crawlStatus?.docs_total ?? 0) > 0 && !indexComplete;
            const isAutoconfiguring = !isFailed && autoconfigRunning;
            const elapsed = `${Math.floor(elapsedSec / 60)}:${String(elapsedSec % 60).padStart(2, "0")}`;

            type RowState = "done" | "active" | "error" | "waiting";
            const PhaseRow = ({ state, label, detail, children }: { state: RowState; label: string; detail?: string; children?: React.ReactNode }) => (
              <div className="flex items-start gap-3 py-2.5 border-b border-gray-100 last:border-0">
                <div className="flex-shrink-0 mt-0.5">
                  {state === "done" && <div className="h-5 w-5 rounded-full bg-green-100 flex items-center justify-center"><Check className="h-3 w-3 text-green-600" /></div>}
                  {state === "active" && <Spinner className="h-5 w-5 text-primary-500" />}
                  {state === "error" && <div className="h-5 w-5 rounded-full bg-red-100 flex items-center justify-center"><AlertTriangle className="h-3 w-3 text-red-500" /></div>}
                  {state === "waiting" && <div className="h-5 w-5 rounded-full border-2 border-gray-200" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-[13px] font-medium ${state === "done" ? "text-gray-500 line-through" : state === "error" ? "text-red-700" : state === "active" ? "text-gray-900" : "text-gray-400"}`}>{label}</p>
                  {detail && <p className={`text-[11px] mt-0.5 ${state === "error" ? "text-red-600" : "text-gray-500"}`}>{detail}</p>}
                  {children}
                </div>
              </div>
            );

            return (
              <Card>
                <CardContent className="pt-5 pb-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-[13px] font-semibold text-gray-900">
                      {isFailed ? "Setup failed" : isAutoconfiguring ? "Almost there…" : "Setting up your bot…"}
                    </h2>
                    {!isFailed && <span className="text-[11px] text-gray-400 tabular-nums">{elapsed}</span>}
                  </div>

                  <div className="divide-y divide-gray-100">
                    {/* Queued */}
                    <PhaseRow state="done" label="Job queued" />

                    {/* Discovering pages */}
                    <PhaseRow
                      state={isFailed && !crawlStatus?.pages_discovered ? "error" : (crawlStatus?.pages_discovered ?? 0) > 0 ? "done" : isDiscovering ? "active" : "waiting"}
                      label="Discovering pages"
                      detail={
                        isFailed && !crawlStatus?.pages_discovered
                          ? (crawlStatus?.error_message ?? "Discovery failed")
                          : isDiscovering
                          ? "Checking sitemap · crawling links"
                          : (crawlStatus?.pages_discovered ?? 0) > 0
                          ? `${crawlStatus!.pages_discovered} page${crawlStatus!.pages_discovered === 1 ? "" : "s"} found`
                          : undefined
                      }
                    />

                    {/* Fetching pages */}
                    <PhaseRow
                      state={isFailed && (crawlStatus?.pages_discovered ?? 0) > 0 ? "error" : crawlComplete ? "done" : isFetching ? "active" : "waiting"}
                      label="Fetching pages"
                      detail={
                        isFailed && (crawlStatus?.pages_discovered ?? 0) > 0
                          ? (crawlStatus?.error_message ?? "Fetch failed")
                          : crawlComplete
                          ? `${crawlStatus!.pages_queued} fetched${crawlStatus!.pages_failed > 0 ? ` · ${crawlStatus!.pages_failed} failed` : ""}`
                          : isFetching && (crawlStatus?.pages_discovered ?? 0) > 0
                          ? `${crawlStatus!.pages_queued} / ${crawlStatus!.pages_discovered}`
                          : undefined
                      }
                    >
                      {isFetching && (crawlStatus?.pages_discovered ?? 0) > 0 && (
                        <div className="h-1.5 w-full rounded-full bg-gray-100 mt-1.5">
                          <div className="h-1.5 rounded-full bg-primary-500 transition-all duration-500" style={{ width: `${crawlPct}%` }} />
                        </div>
                      )}
                    </PhaseRow>

                    {/* Indexing content */}
                    <PhaseRow
                      state={indexComplete ? "done" : isIndexing ? "active" : "waiting"}
                      label="Indexing content"
                      detail={
                        indexComplete
                          ? `${crawlStatus!.docs_indexed} indexed${crawlStatus!.docs_failed > 0 ? ` · ${crawlStatus!.docs_failed} failed` : ""}`
                          : isIndexing
                          ? `${crawlStatus!.docs_indexed} / ${crawlStatus!.docs_total}`
                          : undefined
                      }
                    >
                      {isIndexing && (
                        <div className="h-1.5 w-full rounded-full bg-gray-100 mt-1.5">
                          <div className="h-1.5 rounded-full bg-primary-400 transition-all duration-500" style={{ width: `${indexPct}%` }} />
                        </div>
                      )}
                    </PhaseRow>

                    {/* AI configuration */}
                    <PhaseRow
                      state={isAutoconfiguring ? "active" : autoconfigError ? "error" : "waiting"}
                      label="AI configuration"
                      detail={autoconfigError || (isAutoconfiguring ? "Generating config…" : undefined)}
                    >
                      {autoconfigError && !autoconfigRunning && (
                        <div className="flex gap-2 mt-2">
                          <button
                            onClick={async () => {
                              if (!workspace || !chatbotId || !crawlKbId) return;
                              setAutoconfigRunning(true);
                              setAutoconfigError("");
                              try {
                                const result = await runAutoconfig(workspace.id, chatbotId, crawlKbId);
                                setConfig(result);
                                setReviewName(result.name);
                                setReviewWelcome(result.welcome_message ?? "");
                                setReviewColor(result.brand_color ?? "#ff6b35");
                                setReviewTone(result.tone ?? "professional");
                                setReviewLanguage(result.language ?? "en");
                                setStep("review");
                              } catch (acErr: unknown) {
                                const msg = acErr instanceof Error ? acErr.message : "AI configuration failed.";
                                setAutoconfigError(msg);
                              } finally {
                                setAutoconfigRunning(false);
                              }
                            }}
                            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-white bg-primary-500 hover:bg-primary-600 rounded-lg transition-colors"
                          >
                            <RefreshCw className="h-3 w-3" /> Retry
                          </button>
                          <button onClick={handleRestart} className="px-2.5 py-1 text-[11px] text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                            Start over
                          </button>
                        </div>
                      )}
                    </PhaseRow>
                  </div>

                  {/* Stalled warning */}
                  {crawlStatus?.stalled && !isFailed && (
                    <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-2">
                      <p className="text-[12px] text-amber-800 font-medium">Taking longer than expected.</p>
                      <p className="text-[11px] text-amber-600">The site may be slow or blocking crawlers.</p>
                      <button onClick={handleRestart} className="px-3 py-1.5 text-[11px] font-medium text-amber-700 border border-amber-300 rounded-lg hover:bg-amber-100 transition-colors">
                        Start over
                      </button>
                    </div>
                  )}

                  {/* Hard failure with error message */}
                  {isFailed && (
                    <div className="mt-4 flex justify-end">
                      <button onClick={handleRestart} className="px-3 py-1.5 text-[11px] font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                        Start over
                      </button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Collapsed chip (step 2 done) */}
          {step2Completed && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 flex justify-between items-center">
              <div>
                <p className="text-[11px] font-semibold text-green-800">Crawl &amp; analyse</p>
                <p className="text-[10px] text-green-700 mt-0.5">
                  {crawlStatus?.docs_indexed ?? 0} pages indexed · AI config ready
                </p>
              </div>
              <span className="text-[9px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-semibold">Done</span>
            </div>
          )}
        </div>
      </div>

      {/* ── STEP 3: Review config ── */}
      <div className={`flex gap-3.5 ${editingStep1 ? "opacity-40 pointer-events-none" : ""}`}>
        {/* spine */}
        <div className="flex flex-col items-center w-[26px] flex-shrink-0">
          <div className={`${circleBase} ${
            step3Completed && !editingStep3
              ? "bg-primary-500 text-white"
              : step === "review" || editingStep3
              ? "bg-primary-500 text-white"
              : "bg-white border-2 border-gray-200 text-gray-400"
          }`}>
            {step3Completed && !editingStep3 ? <Check className="h-3.5 w-3.5" /> : "3"}
          </div>
          <div className={`w-0.5 flex-1 min-h-[20px] mt-1 ${line34Color}`} />
        </div>
        {/* content */}
        <div className="flex-1 pb-3">
          {/* Pending label */}
          {stepIndex < 2 && !step2Done && (
            <p className="text-[11px] font-medium text-gray-400 pt-1">Review config</p>
          )}

          {/* Active: review card */}
          {(step === "review" || editingStep3) && config && (
            <Card>
              <CardContent className="pt-8 pb-8">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">Your bot is ready</h2>
                    <p className="text-sm text-gray-500 mt-1">Configured from your site. Review and adjust.</p>
                  </div>
                  {reviewLanguage && (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-primary-50 text-primary-600 rounded-full text-[11px] font-semibold">
                      🌐 {LANG_NAMES[reviewLanguage] ?? reviewLanguage.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="space-y-5">
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
                    <label className="block text-sm font-medium text-gray-700 mb-2">Tone</label>
                    <div className="grid grid-cols-2 gap-2">
                      {TONE_OPTIONS.map((t) => (
                        <button
                          key={t.value}
                          onClick={() => setReviewTone(t.value)}
                          className={`flex flex-col items-start px-3 py-2.5 rounded-lg border text-left transition-all ${
                            reviewTone === t.value
                              ? "border-primary-400 bg-primary-50 ring-1 ring-primary-300"
                              : "border-[#f0ebe3] hover:border-gray-300 hover:bg-[#faf8f5]"
                          }`}
                        >
                          <span className={`text-[12px] font-semibold ${reviewTone === t.value ? "text-primary-600" : "text-gray-700"}`}>
                            {t.label}
                          </span>
                          <span className="text-[11px] text-gray-400 mt-0.5">{t.description}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  {config.suggested_questions && config.suggested_questions.length > 0 && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Suggested questions</label>
                      <div className="flex flex-wrap gap-2">
                        {config.suggested_questions.map((q, i) => (
                          <span key={i} className="rounded-full bg-[#faf8f5] border border-[#f0ebe3] px-3 py-1 text-xs text-gray-600">
                            {q}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
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
                </div>
                {error && <p className="text-sm text-red-600 mt-4">{error}</p>}
                <div className="flex justify-end gap-3 pt-6">
                  {editingStep3 ? (
                    <Button variant="secondary" onClick={() => setEditingStep3(false)}>
                      Cancel
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={() => navigate("/chatbots")}>
                      Skip
                    </Button>
                  )}
                  <Button onClick={async () => { await handleSave(); if (editingStep3) setEditingStep3(false); }} loading={saving}>
                    Save &amp; finish
                    <ChevronRight className="ml-1.5 h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Collapsed chip (step 3 done) */}
          {step3Completed && !editingStep3 && (
            <button
              onClick={() => setEditingStep3(true)}
              className="w-full text-left bg-green-50 border border-green-200 rounded-lg px-3 py-2 flex justify-between items-center group cursor-pointer"
            >
              <div>
                <p className="text-[11px] font-semibold text-green-800">Review config</p>
                <p className="text-[10px] text-green-700 mt-0.5">
                  {reviewName} · {reviewTone} · {LANG_NAMES[reviewLanguage] ?? reviewLanguage}
                </p>
              </div>
              <span className="text-[10px] text-green-600 opacity-0 group-hover:opacity-60 transition-opacity">edit ✎</span>
            </button>
          )}
        </div>
      </div>

      {/* ── STEP 4: Go live ── */}
      <div className={`flex gap-3.5 ${editingStep1 || editingStep3 ? "opacity-40 pointer-events-none" : ""}`}>
        {/* spine — no line after last step */}
        <div className="flex flex-col items-center w-[26px] flex-shrink-0">
          <div className={`${circleBase} ${
            step === "done"
              ? "bg-primary-500 text-white"
              : "bg-white border-2 border-gray-200 text-gray-400"
          }`}>
            {step === "done" ? <Check className="h-3.5 w-3.5" /> : "4"}
          </div>
        </div>
        {/* content */}
        <div className="flex-1 pb-3">
          {/* Pending label */}
          {step !== "done" && (
            <p className="text-[11px] font-medium text-gray-400 pt-1">Go live</p>
          )}

          {/* Active: done content */}
          {step === "done" && (
            <div className="space-y-6">
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
                    <Button variant="secondary" onClick={() => navigate("/chatbots")}>
                      Back to bots
                    </Button>
                    <Button onClick={() => navigate(`/chatbots/${chatbotId}`)}>
                      Open bot settings
                    </Button>
                  </div>
                </CardContent>
              </Card>
              {/* Platform install guides */}
              <Card>
                <CardContent className="pt-6 pb-6">
                  <h3 className="text-[13px] font-semibold text-gray-900 mb-4">How to add it to your site</h3>
                  <div className="flex flex-wrap gap-2 mb-5">
                    {PLATFORM_GUIDES.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setActivePlatform(p.id)}
                        className={`px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all ${
                          activePlatform === p.id
                            ? "bg-primary-500 text-white"
                            : "bg-[#faf8f5] border border-[#f0ebe3] text-gray-500 hover:border-gray-300 hover:text-gray-700"
                        }`}
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                  <ol className="space-y-3">
                    {activePlatformGuide.steps.map((s, i) => (
                      <li key={i} className="flex gap-3">
                        <span className="flex-shrink-0 flex h-5 w-5 items-center justify-center rounded-full bg-primary-100 text-primary-600 text-[10px] font-bold mt-0.5">
                          {i + 1}
                        </span>
                        <p
                          className="text-[13px] text-gray-600 leading-relaxed"
                          dangerouslySetInnerHTML={{ __html: s }}
                        />
                      </li>
                    ))}
                  </ol>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
