# Pulse — UX Flows & Screen Specifications
## Novel Feature User Experience Document
### Version 1.0 — March 2026

> **Purpose**: This document describes what users see and what they can do on each novel screen.
> Standard SaaS screens (auth, settings, billing) are omitted — those are self-explanatory.
> This covers the 9 features with no direct competitor reference.

---

## Table of Contents

1. [Onboarding Flow — First-Run Wizard](#1-onboarding-flow)
2. [Homepage — Autonomous Resolution Rate Dashboard](#2-homepage-dashboard)
3. [Exceptions Queue](#3-exceptions-queue)
4. [Documentation Gap Detection](#4-gap-detection)
5. [Lead Intelligence Feed](#5-lead-intelligence)
6. [Topic Intelligence Dashboard](#6-topic-intelligence)
7. [Sentiment Trend View](#7-sentiment-intelligence)
8. [Functional Gap / Feature Request Feed](#8-feature-requests)
9. [Widget Install Experience](#9-widget-install)

---

## 1. Onboarding Flow — First-Run Wizard {#1-onboarding-flow}

### Entry Point
User signs up → email verified → lands on wizard. Cannot access main app until wizard is completed or explicitly skipped.

### Step 1 — Workspace Setup
**What the user sees:**
- Full-screen centered card
- Fields: Workspace name, Upload logo (optional), Timezone selector
- Progress indicator: Step 1 of 6
- "Continue" button

**What they can do:**
- Name their workspace (e.g. company name)
- Upload a logo (used in widget + dashboard)
- Set timezone (used for scheduling intelligence reports)

**What happens:** Workspace record created. User is the Owner.

---

### Step 2 — Create First Chatbot
**What the user sees:**
- Fields: Chatbot name, Persona selector (cards with icons: Friendly, Professional, Concise, Custom)
- If Custom selected: text area for custom persona instructions
- Optional: Off-topic restriction toggle ("Stay strictly on topic")
- "Continue" button

**What they can do:**
- Name their bot (displayed in widget to end-users)
- Choose a base persona tone
- Optionally restrict the bot from answering off-topic questions

**What happens:** Chatbot record created, linked to workspace.

---

### Step 3 — Add Knowledge Sources
**What the user sees:**
- Three tabs: **URL / Website**, **Upload Files**, **Paste Text / Q&A**
- URL tab: input field + "Add" button, crawl depth selector (this page only / full site), list of added URLs below
- Upload tab: drag-and-drop zone, supports PDF, DOCX, TXT, CSV
- Paste tab: text area for direct content or Q&A pairs (format: Q: ... / A: ...)
- Running list of all added sources with status (queued / indexing / ready)
- "Continue" button — enabled once at least 1 source is added and indexed
- Skip option: "I'll add sources later" (bot will have no KB, will always escalate)

**What they can do:**
- Add multiple sources of any type
- Remove sources before confirming
- See real-time indexing status per source

**What happens:** Sources ingested, chunked, embedded, stored in vector store. Chatbot is now capable of answering questions.

---

### Step 4 — LLM Configuration
**What the user sees:**
- Two option cards side by side:
  - **Use Credits** (highlighted as default): "Use our platform credits. Simple pricing, no API keys needed." Shows current credits balance.
  - **Bring Your Own Key (BYOK)**: "Use your own API key. Pay the provider directly, platform fee only."
- If BYOK selected: Provider selector (OpenAI / Anthropic / Google / Azure OpenAI) + API key input field + "Verify key" button
- Confidence threshold slider: "How confident should the AI be before answering autonomously?" (default 70%, range 50–95%)
- Explanation text: "Below this threshold, conversations are escalated to your Exceptions Queue."
- "Continue" button

**What they can do:**
- Choose credits or BYOK
- If BYOK: enter and verify their API key
- Set their escalation confidence threshold

**What happens:** LLM config saved per chatbot. API key encrypted and stored per workspace if BYOK.

---

### Step 5 — Widget Customization
**What the user sees:**
- Left panel: customization controls
  - Primary color picker
  - Widget position (bottom-right / bottom-left)
  - Welcome message text input
  - Chatbot avatar (upload or choose from presets)
  - Launcher button text (e.g. "Chat with us")
- Right panel: **live widget preview** that updates in real-time as settings change
- "Continue" button

**What they can do:**
- Visually design the widget in real-time
- See exactly what end-users will see

**What happens:** Widget appearance config saved. Widget is ready to embed.

---

### Step 6 — Install Widget
**What the user sees:**
- Tab selector: **Script Tag** / **Shareable Link**
- Script Tag tab:
  - Code snippet (pre-filled with their chatbot ID) with one-click copy button
  - Platform quick-guides (collapsible): WordPress, Shopify, Webflow, Wix, Custom HTML — each with 2-3 step instructions
  - Status badge: 🔴 "Not detected yet" → turns 🟢 "Active" when first conversation arrives
- Shareable Link tab:
  - Standalone hosted URL for the chatbot (no installation needed)
  - Copy button + QR code
- "Go to Dashboard" button

**What they can do:**
- Copy the embed snippet
- Follow platform-specific guides
- Use shareable link as alternative to embedding
- Proceed to dashboard without waiting for detection

**What happens:** User lands on the main dashboard. Onboarding complete.

---

## 2. Homepage — Autonomous Resolution Rate Dashboard {#2-homepage-dashboard}

### Entry Point
Main dashboard after login. This is what users see every day.

### Layout Overview
```
┌─────────────────────────────────────────────────────┐
│  [CHATBOT SELECTOR ▼]          [Date range: 7d ▼]   │
├──────────────────┬──────────────────────────────────┤
│                  │  ESCALATION BREAKDOWN             │
│  RESOLUTION      │  ┌──────────────────────────────┐ │
│  RATE            │  │ Low confidence      45%       │ │
│                  │  │ Negative sentiment  22%       │ │
│  78%  ↑3%        │  │ High value lead     18%       │ │
│  this week       │  │ Explicit request    15%       │ │
│                  │  └──────────────────────────────┘ │
├──────────────────┴──────────────────────────────────┤
│  RESOLUTION RATE TREND (weekly line chart)           │
├─────────────┬─────────────┬───────────┬─────────────┤
│ TOTAL CHATS │ RESOLVED    │ ESCALATED │ KB ARTICLES │
│ 1,243       │ 969         │ 274       │ +3 this wk  │
├─────────────┴─────────────┴───────────┴─────────────┤
│  INTELLIGENCE HIGHLIGHTS (cards)                     │
│  [🔴 3 new doc gaps] [👤 12 leads] [📈 topic spike] │
└─────────────────────────────────────────────────────┘
```

### Primary KPI — Resolution Rate
**What the user sees:**
- Large percentage (e.g. 78%) with trend indicator (↑3% vs last week)
- Color coding: green (>75%), amber (50–75%), red (<50%)
- Sub-label: "of conversations fully resolved by AI this week"

**What they can do:**
- Switch between chatbots via selector at top
- Change date range (7d / 30d / 90d)
- Click resolution rate → drills into conversation-level breakdown

---

### Escalation Breakdown
**What the user sees:**
- Horizontal bar chart: why conversations escalated (low confidence / sentiment / high value / compliance / explicit request)
- % share of each escalation reason

**What they can do:**
- Click a reason → filters Exceptions Queue to that reason

---

### Resolution Rate Trend Chart
**What the user sees:**
- Line chart: weekly resolution rate over last 12 weeks
- Annotations: vertical markers where KB articles were approved ("+2 KB articles")
- Shows the self-improvement loop visually (KB improvements → resolution rate rises)

---

### Intelligence Highlights
**What the user sees:**
- Row of clickable alert cards at the bottom:
  - Doc gap card: "3 new knowledge gaps detected"
  - Lead card: "12 high-score leads this week"
  - Topic spike card: "'Pricing' topic up 40%"
  - Sentiment card: shown if alert triggered
- Each card links to the relevant intelligence module

**What they can do:**
- Click any card → jump to that intelligence module

---

## 3. Exceptions Queue {#3-exceptions-queue}

### Entry Point
Sidebar nav → "Exceptions" or notification alert (Slack/email). This is NOT a traditional inbox.

### Queue List View
**What the user sees:**
- List of escalated conversations, newest first
- Each item (card) shows:
  - Contact name + company (if known)
  - Escalation reason tag (color-coded): `low confidence` / `negative sentiment` / `high value` / `compliance` / `explicit request`
  - Confidence score at escalation point (e.g. "AI confidence: 34%")
  - Time of escalation
  - First message preview (truncated)
  - Status: `open` / `in progress` / `resolved`
- Filter bar: by escalation reason, by chatbot, by status, by date
- Sort: newest / oldest / highest value (lead score)
- Unread count badge on sidebar nav item

**What they can do:**
- Click any item to open the full conversation view
- Filter queue by reason or chatbot
- Mark items as resolved from list view (checkbox)

---

### Conversation Detail View
**What the user sees (3-panel layout):**

**Left panel — Conversation timeline:**
- Full message thread: user messages + bot responses, chronologically
- Each bot response has a confidence score badge (e.g. 🟡 62%) shown inline
- Escalation event shown as a divider: "AI escalated — Reason: Low confidence (34%)"
- Messages after escalation (if human took over) shown in different style

**Right panel — Customer context:**
- Contact name, email, company
- Lead score (if scored)
- Contact events (pages visited, previous conversations)
- Company data (size, industry — if available)
- Tags

**Bottom bar — Action panel:**
- 💡 **Suggested action** (AI-generated): e.g. "This user is asking about refund policy — suggest sending the refund doc link and closing"
- Reply text box: type a response to the user
- Send button
- "Mark as resolved" button
- "Escalate to team member" dropdown (if RBAC allows)

**What they can do:**
- Read the full conversation with confidence scores visible
- See who the customer is and their history
- Follow the suggested action or decide differently
- Reply directly to the user
- Mark resolved → conversation moves out of queue, resolution logged
- Escalate to another team member

**What happens on resolve:** Resolution method logged to DB → feeds AI improvement cycle → contributes to escalation analysis on dashboard.

---

## 4. Documentation Gap Detection {#4-gap-detection}

### Entry Point
Sidebar nav → "Knowledge" → "Gap Report" tab. Also reachable via intelligence highlight card on homepage.

### Gap Report — Cluster List View
**What the user sees:**
- Header metrics row:
  - "Gaps detected this week: 47"
  - "Gaps resolved this week: 12"
  - "Knowledge Velocity: ↑ improving"
- List of gap clusters, sorted by frequency (highest first)
- Each cluster card shows:
  - AI-generated cluster name (e.g. "Refund & cancellation policy")
  - Frequency badge (e.g. "23 unanswered questions")
  - Trend indicator (↑ new / ↓ declining / → stable)
  - Status: `new` / `draft ready` / `pending approval` / `resolved`
  - "View draft" button (if AI has generated an article)

**What they can do:**
- Click any cluster to expand it
- Filter by status (new / draft ready / pending approval / resolved)
- Sort by frequency or trend

---

### Gap Cluster — Expanded View
**What the user sees:**
- Cluster name + frequency
- Example user queries that triggered this gap (verbatim, last 5–10 shown)
  - e.g. "Do you offer refunds?", "How do I cancel my subscription?", "30-day money back?"
- AI-generated draft KB article (full content shown in read-only view)
- Three action buttons: ✅ **Approve** / ✏️ **Edit** / ❌ **Reject**

**What they can do:**
- Read the example queries to understand the gap
- Review the AI-drafted article
- **Approve**: article immediately published + re-indexed. Confirmation toast: "Article published — chatbot is now smarter."
- **Edit**: opens article in editor (rich text). User edits → then approves from editor.
- **Reject**: cluster archived. Option to add a note (e.g. "out of scope").

**What happens on approve:** Article written to KB → re-indexed into vector store → retrieval_logs will start matching this topic → resolution rate improves for these queries.

---

### KB Article Editor (Edit flow)
**What the user sees:**
- Full-page rich text editor (markdown or WYSIWYG toggle)
- Article title (editable)
- Article body (AI-drafted, fully editable)
- "Approve & Publish" button
- "Save Draft" button
- "Back to gap" link

---

## 5. Lead Intelligence Feed {#5-lead-intelligence}

### Entry Point
Sidebar nav → "Intelligence" → "Leads". Also reachable from homepage highlight card.

### Lead Feed — List View
**What the user sees:**
- Header: "High-intent leads from your chatbot conversations"
- Filter bar: date range, chatbot, score threshold (e.g. show only >60), CRM push status
- Sorted list of leads (highest score first by default)
- Each lead card shows:
  - Contact name + company (if captured)
  - **Score badge** (large, color-coded): 🔴 >80 High / 🟡 50–80 Medium / ⚪ <50 Low
  - Top 2–3 signals detected (e.g. "💬 Asked about pricing", "🏢 Enterprise company size", "⚡ Mentioned urgency")
  - Conversation snippet (the highest-signal message)
  - Time of conversation
  - CRM status: `pushed` / `pending` / `not pushed`

**What they can do:**
- Click any lead to open detail view
- Filter by score or date
- Sort by score, recency, or company
- Bulk push selected leads to CRM

---

### Lead Detail View
**What the user sees (2-panel layout):**

**Left — Score breakdown:**
- Overall score (large badge)
- Signal breakdown table:
  | Signal | Weight | Detected |
  |--------|--------|----------|
  | Pricing question | High | ✅ "What does the enterprise plan cost?" |
  | Competitor mention | High | ✅ "We're currently using Intercom" |
  | Company size signal | Medium | ✅ "We have 200 support agents" |
  | Urgency language | Medium | ❌ Not detected |
  | Demo/trial request | High | ❌ Not detected |
- Scoring rationale (1–2 sentence AI summary)

**Right — Actions:**
- Contact info collected from conversation (name, email, company — if captured)
- "Push to CRM" button → if CRM connected: choose CRM, review pre-filled data, confirm push
- "View full conversation" link → opens conversation in exceptions queue view (read-only)
- Tag as: `contacted` / `not a fit` / `converted`

---

## 6. Topic Intelligence Dashboard {#6-topic-intelligence}

### Entry Point
Sidebar nav → "Intelligence" → "Topics".

### Topic Overview
**What the user sees:**
- Time period selector: 7d / 30d / 90d (top right)
- Chatbot selector (if multiple chatbots)
- Anomaly alert banner (if any topic spiked): "⚠️ 'Pricing' conversations up 40% this week"
- Grid of topic cluster cards (auto-generated, no configuration needed)
- Each card shows:
  - Topic name (AI-generated label, e.g. "Billing & Invoices")
  - Volume (e.g. "143 conversations")
  - Trend badge: 📈 +40% / 📉 -12% / → Stable
  - Sparkline (mini 7-day trend chart)
  - Top 2 example questions in this topic

**What they can do:**
- Click any topic card → drill into conversation list for that topic
- Change time period → all cards update
- Sort cards by volume / trend / alphabetical

---

### Topic Drill-Down View
**What the user sees:**
- Topic name + total volume for period
- Volume trend chart (full size)
- List of conversations in this topic cluster
  - Each row: contact, date, resolution status (resolved/escalated), message preview
- Option to export list (CSV)

**What they can do:**
- Click any conversation → opens read-only conversation view
- Export the conversation list for this topic
- Navigate back to topic grid

---

## 7. Sentiment Trend View {#7-sentiment-intelligence}

### Entry Point
Sidebar nav → "Intelligence" → "Sentiment".

### Sentiment Overview
**What the user sees:**
- **Primary chart**: Sentiment score over time (line chart, scale -1 to +1)
  - Green zone (positive), amber zone (neutral), red zone (negative)
  - Alert threshold line (configurable, default -0.3)
  - Annotated points: if any alert was triggered, shown as a marker on the chart
- Filter controls: chatbot, date range, topic filter
- Aggregate stats row:
  - Average sentiment this period
  - % conversations positive / neutral / negative
  - Trend vs previous period
- **Alert history** (below chart): list of past alerts with date, trigger condition, value at trigger

**What they can do:**
- Hover chart → see exact sentiment score + conversation count for that date
- Click chart point → opens list of conversations from that day
- Change alert threshold (slider) — saves per chatbot
- Change date range / chatbot filter

---

### Alert Configuration
**What the user sees:**
- Collapsible panel: "Alert Settings"
  - Threshold slider: "Alert me when average sentiment drops below [value]"
  - Alert channels: Slack / Email toggles
  - Alert frequency: Immediate / Daily digest
- "Save" button

---

### Sentiment Drill-Down (click chart point)
**What the user sees:**
- Date shown as header
- List of conversations from that date, sorted by sentiment (most negative first)
- Each row: contact, sentiment score badge, escalation status, message preview

**What they can do:**
- Click conversation → read-only view
- See why sentiment was low on a specific day

---

## 8. Functional Gap / Feature Request Feed {#8-feature-requests}

### Entry Point
Sidebar nav → "Intelligence" → "Feature Requests".

### Feature Request Overview
**What the user sees:**
- Header: "What your users are asking you to build — extracted from chatbot conversations"
- Anomaly banner (if new cluster surges): "🆕 New cluster: 'Dark mode support' — 18 requests this week"
- List of feature request clusters, sorted by volume
- Each cluster card shows:
  - Feature name (AI-generated, e.g. "Dark mode support")
  - Request count (e.g. "34 requests")
  - Trend badge: 🆕 New / 📈 Growing / → Stable / 📉 Declining
  - Example quote (verbatim user request, 1 shown)
  - PM tool push status: `pushed to Jira` / `pushed to Linear` / `not pushed`

**What they can do:**
- Click any cluster → expand detail view
- Filter by status (pushed / not pushed) or trend
- Sort by volume or trend

---

### Feature Request Cluster — Detail View
**What the user sees:**
- Cluster name + total request count + trend
- Volume trend chart (weekly)
- **Example quotes** (up to 10 verbatim user messages)
  - e.g. "It would be great if you had a dark mode"
  - e.g. "Please add dark mode, my eyes!"
  - e.g. "Any plans for dark theme?"
- "Push to PM tool" button

**Push to PM tool dialog:**
- Select tool: Jira / Linear (whichever is connected)
- Select project / board
- Pre-filled issue title: "[Feature Request] Dark mode support (34 users)"
- Pre-filled description: cluster summary + example quotes
- "Create issue" button
- On success: issue URL shown + cluster marked as `pushed`

**What they can do:**
- Read all verbatim requests
- Push cluster to Jira or Linear with one click
- View linked issue (if already pushed)

---

## 9. Widget Install Experience {#9-widget-install}

### Entry Point
Chatbot settings → "Deploy" tab. Also shown in onboarding Step 6.

### Deploy Tab — Main View
**What the user sees:**
- Three sub-tabs: **Script Tag** / **Shareable Link** / **Test Widget**
- Installation status badge (top right): 🔴 "Not installed" → 🟢 "Active" (auto-detected on first conversation)

---

### Script Tag Tab
**What the user sees:**
- Code snippet block (pre-filled):
  ```html
  <script
    src="https://cdn.pulse.ai/widget.js"
    data-chatbot-id="abc123"
    async>
  </script>
  ```
- Copy button (one click copies entire snippet)
- "Paste this before the closing </body> tag on your website"
- Platform installation guides (collapsible accordions):
  - **WordPress**: 3-step guide (Plugin → Appearance → Custom HTML → paste)
  - **Shopify**: 3-step guide (Online Store → Themes → Edit Code → paste)
  - **Webflow**: 2-step guide (Page Settings → Custom Code → paste)
  - **Wix**: 2-step guide (Settings → Custom Code → paste)
  - **Custom HTML**: 1-step guide

**What they can do:**
- Copy the snippet
- Follow their platform's guide
- Widget auto-detects installation → status turns green

---

### Shareable Link Tab
**What the user sees:**
- Hosted URL (e.g. `https://chat.pulse.ai/c/abc123`)
- Copy button
- QR code (downloadable)
- "Use this if you can't embed a script — share the link directly"
- Preview button → opens the standalone chat page in new tab

---

### Test Widget Tab
**What the user sees:**
- Embedded live widget preview directly inside the dashboard
- Simulates exactly what end-users will see
- "Type a test message" prompt
- After test conversation: shows the confidence score for the response + which KB source was used
- Link: "See this conversation in your Exceptions Queue" (if escalated)

**What they can do:**
- Chat with their own bot before going live
- Verify the KB is working correctly
- See confidence scores in real-time
- Identify KB gaps immediately after setup

---

## Appendix — Navigation Structure

```
Sidebar:
├── 🏠 Dashboard (Resolution Rate homepage)
├── 💬 Exceptions Queue
├── 🧠 Knowledge Base
│   ├── Sources
│   ├── Articles
│   └── Gap Report ← novel
├── 📊 Intelligence
│   ├── Leads ← novel
│   ├── Topics ← novel
│   ├── Sentiment ← novel
│   └── Feature Requests ← novel
├── 🤖 Chatbots
│   ├── [Chatbot name]
│   │   ├── Settings
│   │   ├── Deploy ← novel (widget install)
│   │   └── Conversations
├── 👥 Team
├── ⚙️ Settings
│   ├── Workspace
│   ├── Integrations
│   ├── Billing
│   └── API Keys (BYOK)
```

