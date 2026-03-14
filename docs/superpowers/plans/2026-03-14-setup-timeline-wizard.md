# Setup Timeline Wizard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the chatbot setup page to show a vertical 4-step timeline instead of one step at a time.

**Architecture:** Single-file rewrite of `setup/page.tsx`. All existing state management, API calls, and Socket.IO handlers stay the same. Only the JSX layout changes to render all 4 steps simultaneously in a vertical spine.

**Tech Stack:** React, Tailwind CSS, lucide-react icons, existing Socket.IO hooks

**Spec:** `docs/superpowers/specs/2026-03-14-setup-timeline-wizard-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Rewrite | `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx` | Full timeline wizard UI |

No new files. No other files modified.

---

## Task 1: Rewrite setup page with vertical timeline

**Files:**
- Rewrite: `frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx`

### State & Logic Changes

- [ ] **Step 1: Add `step4Active` state and update state machine**

In `setup/page.tsx`, add a `step4Active` state boolean. Update `getSetupStep()` — no changes needed to the function itself, but add a helper that derives the active step number (1–4) and per-step completion status:

```tsx
const [step4Active, setStep4Active] = useState(false);
const [copied, setCopied] = useState(false);

// Ref so Socket.IO handlers always see the latest value
const step4ActiveRef = useRef(false);
step4ActiveRef.current = step4Active;

// Derive which step is active and which are completed
const wizardStep = getSetupStep(chatbot.setup_status);
const activeStepNum = step4Active ? 4
  : wizardStep === "crawling" || wizardStep === "configuring" || wizardStep === "failed" ? 2
  : wizardStep === "review" ? 3
  : 1; // "done" — redirect fires in useEffect, use inert value to avoid flashing step 4

const step1Done = true; // always completed on setup page
const step2Done = activeStepNum >= 3;
const step3Done = activeStepNum >= 4;
const step2Error = wizardStep === "failed" || (wizardStep === "crawling" && crawlStatus?.status === "failed");

// Language label lookup for step 3 chip
const languageOptions = [
  { value: "en", label: "English" },
  { value: "nl", label: "Dutch" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
];
const languageLabel = languageOptions.find((l) => l.value === reviewLanguage)?.label ?? reviewLanguage;
```

- [ ] **Step 2: Update `chatbot:status_changed` handler to suppress redirect when `step4Active`**

In the existing `useSocketEvent<ChatbotStatusEvent>("chatbot:status_changed", ...)` handler, change the redirect guard:

```tsx
// Before:
if (step === "done") {
  navigate(`/chatbots/${id}`, { replace: true });
}

// After — use the ref declared in Step 1:
if (step === "done" && !step4ActiveRef.current) {
  navigate(`/chatbots/${id}`, { replace: true });
}
```

Also update the **reconnect handler** (the `useEffect` with `s.on("connect", onReconnect)`) to use the same guard:

```tsx
// In the onReconnect callback, change:
if (step === "done") navigate(`/chatbots/${id}`, { replace: true });
// To:
if (step === "done" && !step4ActiveRef.current) navigate(`/chatbots/${id}`, { replace: true });
```

- [ ] **Step 3: Update `handleSave` to set `step4Active` instead of navigating**

```tsx
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
    setStep4Active(true);
  } finally {
    setSaving(false);
  }
}
```

### Timeline Layout

- [ ] **Step 4: Build the timeline spine layout**

Replace the current conditional return blocks (lines 189–456) with a single timeline layout that renders all 4 steps. The structure:

```tsx
{/* Timeline container */}
<div className="max-w-2xl mx-auto py-10 px-4">
  {/* Page title */}
  <h1 className="text-xl font-bold text-gray-900 mb-8">Setting up your bot</h1>

  <div className="space-y-0">
    {/* Step 1 */}
    <StepRow
      stepNum={1}
      label="Your website"
      done={step1Done}
      active={false}
      error={false}
      isLast={false}
      nextDone={step2Done}
    >
      {/* Always a chip */}
      <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
        <span className="text-sm text-green-700">{chatbot.name}</span>
      </div>
    </StepRow>

    {/* Step 2 */}
    <StepRow stepNum={2} label="Crawl & analyse" done={step2Done} active={activeStepNum === 2} error={step2Error} isLast={false} nextDone={step3Done}>
      {step2Done ? (
        <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          <span className="text-sm text-green-700">
            {crawlStatus?.pages_queued ?? chatbot.crawl_progress?.pages_queued ?? 0} pages crawled · AI config ready
          </span>
        </div>
      ) : (
        <CrawlContent />  /* existing crawl + configuring + error UI */
      )}
    </StepRow>

    {/* Step 3 */}
    <StepRow stepNum={3} label="Review config" done={step3Done} active={activeStepNum === 3} error={false} isLast={false} nextDone={false}>
      {step3Done ? (
        <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          <span className="text-sm text-green-700">{reviewName} · {reviewTone} · {languageLabel}</span>
        </div>
      ) : activeStepNum === 3 ? (
        <ReviewForm />  /* existing review form */
      ) : (
        <span className="text-sm text-gray-400">Review config</span>
      )}
    </StepRow>

    {/* Step 4 */}
    <StepRow stepNum={4} label="Go live" done={false} active={activeStepNum === 4} error={false} isLast={true} nextDone={false}>
      {activeStepNum === 4 ? (
        <GoLiveContent />  /* embed snippet */
      ) : (
        <span className="text-sm text-gray-400">Go live</span>
      )}
    </StepRow>
  </div>
</div>
```

The `StepRow` is a local inline component (not a separate file) defined at the top of the component:

```tsx
function StepRow({ stepNum, label, done, active, error, isLast, nextDone, children }: {
  stepNum: number;
  label: string;
  done: boolean;
  active: boolean;
  error: boolean;
  isLast: boolean;
  nextDone: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3.5">
      {/* Spine column */}
      <div className="flex flex-col items-center" style={{ width: 26 }}>
        {/* Circle */}
        <div className={`w-[26px] h-[26px] rounded-full flex items-center justify-center flex-shrink-0 ${
          error ? "bg-amber-500" :
          done ? "bg-primary-500" :
          active ? "bg-primary-500" :
          "border-2 border-gray-300"
        }`}>
          {error ? (
            <AlertTriangle className="h-3.5 w-3.5 text-white" />
          ) : done ? (
            <Check className="h-3.5 w-3.5 text-white" />
          ) : (
            <span className={`text-xs font-semibold ${active ? "text-white" : "text-gray-400"}`}>{stepNum}</span>
          )}
        </div>
        {/* Connecting line */}
        {!isLast && (
          <div className={`w-0.5 flex-1 min-h-[16px] ${done && nextDone ? "bg-primary-500" : "bg-gray-200"}`} />
        )}
      </div>
      {/* Content column */}
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
```

Import `Check` from lucide-react (already imports `CheckCircle` and `AlertTriangle`).

- [ ] **Step 5: Move crawl/configuring/error UI into the step 2 content area**

Take the existing crawl progress UI (discovering, fetching, indexing sub-steps), configuring spinner, and error states and render them inside the step 2 content area. This is the same JSX — just indented into the timeline layout instead of returned early. Include all states:

- `crawling` phase: discovering + fetching + indexing progress
- `configuring` phase: spinner + timeout warning
- `crawl failed`: red alert with buttons
- `setup_failed`: amber alert icon, "Autoconfig failed" message, "Go to settings" button

- [ ] **Step 6: Move review form into the step 3 content area**

Take the existing review form JSX (bot name, welcome message, system prompt, fallback, tone, language, brand color, Save & Skip buttons) and render it inside the step 3 content area. Wrap in a card: `bg-white border border-gray-200 rounded-xl p-6 space-y-5`.

- [ ] **Step 7: Build the step 4 "Go live" content**

```tsx
{activeStepNum === 4 && (
  <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
    <div>
      <h3 className="text-sm font-medium text-gray-700 mb-2">Embed on your website</h3>
      <div className="relative">
        <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-700 overflow-x-auto">
          {`<script src="${window.location.origin}/widget/${chatbot.id}.js"></script>`}
        </pre>
        <button
          onClick={() => {
            navigator.clipboard.writeText(`<script src="${window.location.origin}/widget/${chatbot.id}.js"></script>`);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          className="absolute top-2 right-2 px-2 py-1 text-xs font-medium rounded bg-white border border-gray-200 text-gray-500 hover:text-gray-700 hover:border-gray-300 transition-colors"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
    <div className="flex justify-end">
      <Button onClick={() => navigate(`/chatbots/${id}`)}>
        Go to dashboard →
      </Button>
    </div>
  </div>
)}
```

`copied` and `setCopied` state was already declared in Step 1.

- [ ] **Step 8: Remove the old conditional return blocks**

Delete the old per-step return blocks that rendered one step at a time. The new timeline layout replaces all of them. Keep the loading state (spinner when `!chatbot`) and error state (`loadError`) at the top — those still return early.

- [ ] **Step 9: Verify the build compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 10: Manual smoke test**

Run: `make up` and navigate to a chatbot in setup state. Verify:
1. All 4 steps visible in vertical timeline
2. Completed steps show green chips
3. Active step shows expanded content
4. Pending steps show gray labels
5. Spine lines connect circles with correct colors

- [ ] **Step 11: Commit**

```bash
git add frontend/src/app/(dashboard)/chatbots/[id]/setup/page.tsx
git commit -m "feat: rewrite setup page with vertical timeline wizard

Show all 4 steps (website, crawl, review, go live) in a vertical
timeline. Completed steps collapse to summary chips, active step
expands inline, pending steps shown grayed out."
```
