# Pulse — Core Test Scenarios

## Perspectives

| ID | Perspective | Who |
|----|------------|-----|
| **A** | New Admin / Owner | Sets up workspace, chatbot, billing |
| **B** | AI Supervisor | Monitors queue, approves KB, handles escalations |
| **C** | End User | Visitor chatting via widget or shareable link |
| **D** | Team Member | Invited member with limited access |
| **E** | API Consumer | Developer using the REST API |

---

## 1. Authentication & Account

### 1.1 Registration
- **[A]** Sign up with email + password → receive verification email → verify → land on onboarding wizard
- **[A]** Sign up with Google OAuth → land on onboarding wizard
- **[A]** Attempt duplicate registration with existing email → expect error
- **[A]** Invalid email format → validation error before submission

### 1.2 Login
- **[A]** Login with valid credentials → redirect to dashboard
- **[A]** Login with wrong password → error message
- **[A]** Login with unknown email → generic error (no user enumeration)
- **[A]** JWT access token expires (30 min) → silent refresh via refresh token → session continues
- **[A]** Refresh token expires (7 days) → redirect to login

### 1.3 Google OAuth
- **[A]** Click "Sign in with Google" → OAuth flow → land on dashboard
- **[A]** Re-login with same Google account → existing workspace loaded (no duplicate created)

### 1.4 Two-Factor Authentication (2FA / TOTP)
- **[A]** Enable TOTP in security settings → scan QR code → enter code → 2FA active
- **[A]** Login with 2FA enabled → prompted for TOTP after password → access granted
- **[A]** Enter wrong TOTP code → rejected
- **[A]** Disable 2FA → confirm with password → disabled

### 1.5 SSO (OIDC)
- **[A]** Configure SSO provider (Okta/Entra/Google Workspace/Auth0) → enter discovery URL + client credentials → save
- **[A]** Login with SSO-domain email → redirected to IdP → callback → dashboard access
- **[A]** SSO login with non-configured domain → falls back to password login

---

## 2. Onboarding Wizard

### 2.1 Step 1 — Workspace Setup
- **[A]** Enter workspace name, optional logo, timezone → Continue → workspace created
- **[A]** Skip logo upload → workspace created with default avatar
- **[A]** Submit without workspace name → validation error

### 2.2 Step 2 — Create First Chatbot
- **[A]** Name chatbot, select "Professional" persona → Continue
- **[A]** Select "Custom" persona → enter custom instructions → Continue
- **[A]** Toggle "Stay strictly on topic" → verify it's saved in chatbot config

### 2.3 Step 3 — Add Knowledge Sources
- **[A]** Add a URL source → status shows "queued" → "indexing" → "ready"
- **[A]** Upload a PDF → indexing → ready
- **[A]** Paste Q&A text (format `Q: ... / A: ...`) → ready
- **[A]** Add multiple source types simultaneously → all indexed
- **[A]** "I'll add sources later" skip → wizard advances (bot will always escalate)
- **[A]** Continue button disabled until at least 1 source is ready

### 2.4 Step 4 — LLM Configuration
- **[A]** Select "Use Credits" → confidence threshold set to 70% → Continue
- **[A]** Select "BYOK" → choose OpenAI → enter valid API key → "Verify key" succeeds → Continue
- **[A]** BYOK with invalid API key → "Verify key" fails with error
- **[A]** Adjust confidence threshold slider to 85% → saved per chatbot

### 2.5 Step 5 — Widget Customization
- **[A]** Change primary color → live preview updates immediately
- **[A]** Switch widget position to bottom-left → preview reflects change
- **[A]** Set custom welcome message → visible in preview
- **[A]** Upload chatbot avatar → preview updates

### 2.6 Step 6 — Install Widget
- **[A]** Script tag tab → copy snippet → button feedback (copied)
- **[A]** Platform guide accordions expand (WordPress, Shopify, Webflow, Wix, Custom HTML)
- **[A]** Shareable link tab → copy URL → QR code visible + downloadable
- **[A]** "Go to Dashboard" → lands on main dashboard

---

## 3. Chatbot Management

### 3.1 Create / Edit Chatbot
- **[A]** Create additional chatbot after onboarding → name, persona saved
- **[A]** Edit chatbot name, persona instructions → saved and reflected in next chat
- **[A]** Toggle "Stay strictly on topic" on existing chatbot → off-topic queries escalated
- **[A]** Duplicate chatbot → new chatbot created with same settings (KB links not copied per spec)

### 3.2 LLM & Behavior Settings
- **[A]** Switch chatbot from "Use Credits" to BYOK → verify key → saved
- **[A]** Change confidence threshold → new threshold applied to subsequent conversations
- **[A]** Adjust temperature, max_tokens, retrieval_top_k → saved
- **[A]** Toggle use_reranking, use_hybrid_retrieval → saved

### 3.3 Widget Customization (post-onboarding)
- **[A]** Open Customize tab → change primary color → live preview updates
- **[A]** Change welcome message → reflected in test widget
- **[A]** Set custom CSS in textarea → applied in widget shadow root
- **[A]** Set widget position bottom-left → preview confirms

### 3.4 Allowed Domains
- **[A]** Add allowed domain (e.g. `example.com`) → widget requests from other origins rejected (403)
- **[A]** Leave allowed domains empty → widget accessible from any origin
- **[A]** Add subdomain → `sub.example.com` matches

### 3.5 Deploy Tab
- **[A]** Script tag tab → copy snippet → contains correct chatbot ID
- **[A]** Shareable link → preview opens standalone chat page
- **[A]** Test Widget tab → chat with own bot inside dashboard → see confidence score + KB source used
- **[A]** After first external conversation arrives → install status badge turns green

### 3.6 Actions
- **[A]** Add `custom_button` action → configure label + URL → widget shows CTA button in chat
- **[A]** Add `slack_message` action → configure Slack webhook URL → on trigger, message posted to Slack
- **[A]** Add `web_search` action → bot queries DuckDuckGo for unknown topics
- **[A]** Add `calendly` action → configure Calendly URL → widget renders scheduling link
- **[A]** Add `cal.com` action → configure Cal.com URL → widget renders scheduling link
- **[A]** Add `zapier` outbound webhook → configure URL → webhook fired on conversation events

---

## 4. Knowledge Sources

### 4.1 Website / URL Crawling
- **[A]** Add URL with "this page only" depth → single page indexed
- **[A]** Add URL with "full site" → sitemap parsed → multiple pages queued
- **[A]** Add invalid URL → validation error
- **[A]** Add URL that redirects → follows redirect, indexes destination

### 4.2 File Upload
- **[A]** Upload PDF → text extracted → chunked → embedded → status: ready
- **[A]** Upload DOCX → indexed
- **[A]** Upload TXT → indexed
- **[A]** Upload CSV → indexed
- **[A]** Upload unsupported file type → rejected with error

### 4.3 Paste Text / Q&A
- **[A]** Paste free-form text → indexed as knowledge source
- **[A]** Paste Q&A format (`Q: ... / A: ...`) → parsed correctly → chatbot answers using it

### 4.4 Third-Party Integrations
- **[A]** Connect Notion (OAuth) → select page → ingest → ready
- **[A]** Connect Google Drive (OAuth) → select file → ingest → ready
- **[A]** Connect Dropbox → select file → ingest → ready
- **[A]** Connect Zendesk → configure credentials → ingest articles → ready
- **[A]** Connect Salesforce → configure credentials → ingest knowledge articles → ready

### 4.5 Source Management
- **[A]** Delete a source → chunks removed from vector store → chatbot no longer uses it
- **[A]** Re-index an existing source → fresh embedding replaces old
- **[A]** View source status list — all sources with queued/indexing/ready/failed states

---

## 5. Chat / Widget (End User)

### 5.1 Basic Conversation
- **[C]** Open widget on website → welcome message displayed
- **[C]** Send question answered by KB → AI responds with relevant answer
- **[C]** Send question not in KB → bot escalates (or says it can't help)
- **[C]** Long conversation (10+ turns) → context maintained

### 5.2 Streaming (SSE)
- **[C]** Bot response streams token-by-token → no full-page wait
- **[C]** Done event includes `sources[]` → citations rendered at end of response

### 5.3 Escalation
- **[C]** Ask a complex question below confidence threshold → conversation escalated → appears in Exceptions Queue
- **[C]** Ask question with negative sentiment → triggers sentiment escalation
- **[C]** Explicitly say "I want to talk to a human" → explicit escalation trigger

### 5.4 Voice / Dictation
- **[C]** Click mic button in widget → speak question → transcribed into text field → send

### 5.5 Message Feedback
- **[C]** After bot response, click thumbs up → feedback recorded
- **[C]** Click thumbs down → feedback recorded
- **[C]** Feedback visible in DB / admin (per message)

### 5.6 Cross-Session Persistence
- **[A]** Enable `persist_conversation` on chatbot → end user returns → conversation_id restored from localStorage → conversation continues

### 5.7 Shareable Link
- **[C]** Open shareable link (no embed) → full-page chat interface → conversation works identically to widget

### 5.8 Auto-Open Delay
- **[A]** Set auto_open_delay to 5 seconds → widget stays closed for 5 sec then opens automatically
- **[A]** Set to 0 → opens immediately

### 5.9 Quick Replies
- **[C]** Bot offers quick reply buttons → click one → sent as message → normal flow continues

### 5.10 Message Copy
- **[C]** Click copy button on a bot message → message content copied to clipboard

---

## 6. Exceptions Queue

### 6.1 Queue List
- **[B]** Open Exceptions → see escalated conversations sorted newest first
- **[B]** Each item shows: contact name, escalation reason tag, confidence score, time, message preview, status
- **[B]** Unread count badge visible in sidebar nav
- **[B]** Filter queue by escalation reason → only matching items shown
- **[B]** Filter by chatbot → only that chatbot's escalations shown
- **[B]** Filter by status (open/in progress/resolved) → correct items shown
- **[B]** Sort by "highest value (lead score)" → high-score leads at top

### 6.2 Conversation Detail
- **[B]** Open conversation → full message thread with per-message confidence score badges
- **[B]** Escalation event shown as divider with reason
- **[B]** Right panel shows contact name, email, company, lead score, tags
- **[B]** Suggested action AI-generated → shows context-aware recommendation
- **[B]** Reply to user → message sent
- **[B]** Mark as resolved → conversation moves out of queue → resolution logged
- **[B]** Escalate to team member (if RBAC allows) → assigned to another member

### 6.3 Outcome Tagging
- **[B]** Tag conversation as "resolved" / "escalated" / "churned" / "upgraded" / "bug filed"
- **[B]** Outcome badge visible on conversation
- **[B]** Filter conversations by outcome

---

## 7. Dashboard (Resolution Rate)

### 7.1 Primary KPI
- **[B]** Dashboard shows autonomous resolution rate % with trend (↑/↓)
- **[B]** Color coding: green >75%, amber 50-75%, red <50%
- **[B]** Switch chatbot via selector → rate updates for that chatbot
- **[B]** Change date range (7d / 30d / 90d) → metric recalculates

### 7.2 Escalation Breakdown
- **[B]** Horizontal bar chart shows % per escalation reason
- **[B]** Click escalation reason bar → Exceptions Queue filtered to that reason

### 7.3 Resolution Rate Trend Chart
- **[B]** Line chart shows weekly resolution rate for last 12 weeks
- **[B]** KB article approval events annotated on chart as vertical markers

### 7.4 Summary Stats
- **[B]** Total chats, resolved, escalated, KB articles added this week — all correct

### 7.5 Intelligence Highlights
- **[B]** "3 new knowledge gaps detected" card visible → click → goes to Gap Report
- **[B]** "12 high-score leads this week" card → click → goes to Lead Feed
- **[B]** Topic spike card visible when anomaly detected → click → Topics dashboard
- **[B]** Sentiment alert card shown when threshold triggered → click → Sentiment view

---

## 8. Knowledge Base & Gap Detection

### 8.1 Sources Tab
- **[A]** View all sources with status (indexed/failed) and last updated
- **[A]** Delete source → confirmed removed

### 8.2 Articles Tab
- **[A]** View AI-drafted KB articles
- **[A]** Edit article in rich text editor → save draft
- **[A]** Approve article → published + re-indexed into vector store → toast confirms

### 8.3 Gap Report
- **[B]** Header shows: gaps detected this week, gaps resolved, Knowledge Velocity indicator
- **[B]** List of gap clusters sorted by frequency (highest first)
- **[B]** Each cluster card shows: cluster name, frequency, trend, status, "View draft" button
- **[B]** Filter gaps by status (new / draft ready / pending approval / resolved)
- **[B]** Click cluster → expand → see example user queries + AI-drafted article
- **[B]** Approve draft → "Article published — chatbot is now smarter" toast → status becomes "resolved"
- **[B]** Edit draft → full-page editor opens → edit content → "Approve & Publish"
- **[B]** Reject draft → cluster archived → optional rejection note added
- **[B]** After approval, chatbot answers previously-unanswered questions

---

## 9. Intelligence — Leads

### 9.1 Lead Feed
- **[B]** Open Intelligence → Leads → list sorted by score (highest first)
- **[B]** Each card shows: contact name/company, score badge (red/yellow/grey), top 2-3 signals, conversation snippet, CRM status
- **[B]** Filter by score threshold (e.g. >60) → only high-intent leads shown
- **[B]** Filter by date range, chatbot
- **[B]** Sort by recency, company

### 9.2 Lead Detail
- **[B]** Click lead → signal breakdown table (signal, weight, detected/not)
- **[B]** Scoring rationale visible (1-2 sentence AI summary)
- **[B]** Contact info (name, email, company) shown if captured
- **[B]** "Push to CRM" (HubSpot) → choose CRM → pre-filled data → confirm → pushed → status: `pushed`
- **[B]** "Push to CRM" (Salesforce) → same flow
- **[B]** "View full conversation" link → opens read-only conversation view
- **[B]** Tag lead as `contacted` / `not a fit` / `converted`

### 9.3 Bulk Push
- **[B]** Select multiple leads → bulk push to CRM → all pushed, status updated

---

## 10. Intelligence — Topics

### 10.1 Topic Overview
- **[B]** Open Intelligence → Topics → grid of auto-generated topic cluster cards
- **[B]** Each card shows: topic name, volume, trend badge (📈/📉/stable), sparkline, top 2 example questions
- **[B]** Anomaly alert banner shown when a topic spiked >40%
- **[B]** Change time period (7d/30d/90d) → cards update
- **[B]** Sort cards by volume / trend / alphabetical

### 10.2 Topic Drill-Down
- **[B]** Click topic card → volume trend chart + conversation list
- **[B]** Each conversation row: contact, date, resolution status, preview
- **[B]** Click conversation → read-only view opens
- **[B]** Export conversation list as CSV

---

## 11. Intelligence — Sentiment

### 11.1 Sentiment Overview
- **[B]** Sentiment score trend line chart (scale -1 to +1) with green/amber/red zones
- **[B]** Alert threshold line shown on chart (default -0.3)
- **[B]** Past alert events annotated as markers on chart
- **[B]** Aggregate stats: average sentiment, % positive/neutral/negative, trend vs previous period
- **[B]** Alert history list below chart

### 11.2 Sentiment Drill-Down
- **[B]** Click chart point → conversations from that date, sorted by sentiment (most negative first)
- **[B]** Click conversation → read-only view

### 11.3 Alert Configuration
- **[B]** Adjust threshold slider → save → new threshold applies to future alerts
- **[B]** Toggle Slack alert channel → alert fires to Slack when triggered
- **[B]** Toggle email alert → alert fires to email
- **[B]** Set frequency: immediate vs daily digest

### 11.4 Segment-Level Sentiment
- **[B]** Toggle "By Chatbot" → horizontal bar chart of sentiment per chatbot
- **[B]** Toggle "By Contact" → horizontal bar chart of sentiment per contact segment

---

## 12. Intelligence — Feature Requests

### 12.1 Feature Request Feed
- **[B]** Open Intelligence → Feature Requests → list sorted by volume
- **[B]** Each card shows: feature name, request count, trend badge, example quote, PM push status
- **[B]** Anomaly banner when new cluster surges
- **[B]** Filter by status (pushed / not pushed) or trend

### 12.2 Feature Request Detail
- **[B]** Click cluster → volume trend chart + up to 10 verbatim user quotes
- **[B]** "Push to Jira" → select project → pre-filled title + description → create issue → success with issue URL
- **[B]** "Push to Linear" → same flow
- **[B]** Cluster marked as `pushed` after successful PM push

---

## 13. Team & RBAC

### 13.1 Invitations
- **[A]** Invite team member by email → invitation email sent
- **[D]** Accept invitation → account created/linked → lands on workspace with member role
- **[A]** Invite with `admin` role → invitee has admin permissions
- **[A]** Revoke invitation before it's accepted → invite invalidated

### 13.2 Role Enforcement
- **[D]** Member role → cannot access billing settings
- **[D]** Member role → cannot delete workspace
- **[D]** Member role → can view conversations and exceptions
- **[A]** Owner can change team member roles
- **[D]** Member cannot escalate conversation to themselves (only to others)

### 13.3 Audit Logging
- **[A]** Perform actions (invite user, approve KB article, push to CRM) → entries appear in audit log with timestamp, actor, action

---

## 14. Billing & Credits

### 14.1 Plan Selection
- **[A]** View available plans (Free / Starter / Professional / Agency / Enterprise)
- **[A]** Upgrade from Free to Professional → Stripe checkout → subscription active
- **[A]** Toggle annual billing → discounted price shown → checkout at annual price
- **[A]** Downgrade plan → downgrade queued for next billing cycle

### 14.2 Credit Usage
- **[A]** View credits balance (balance, used, limit, plan)
- **[A]** Plan usage indicator shows % of monthly conversations used
- **[A]** Credits exhausted → new conversations get fallback response + flag to upgrade

### 14.3 Auto-Recharge
- **[A]** Enable auto-recharge → configure threshold and top-up amount → credits auto-purchased when balance hits threshold

### 14.4 BYOK Usage Breakdown
- **[A]** BYOK enabled → usage breakdown shows platform-fee-only billing separate from provider costs

---

## 15. Workspace Settings

### 15.1 General Settings
- **[A]** Update workspace name → saved + reflected in UI
- **[A]** Upload workspace logo → used in widget + dashboard header
- **[A]** Change timezone → reflected in intelligence report scheduling

### 15.2 Data Retention
- **[A]** Set data retention to 90 days → conversations older than 90 days purged by nightly Celery task
- **[A]** Set to null (no retention limit) → no purging

### 15.3 White-Labeling
- **[A]** Configure custom domain for widget → widget served from custom domain
- **[A]** Set brand name → "Powered by Pulse" replaced with custom brand
- **[A]** Upload brand logo for widget header

### 15.4 API Keys
- **[A]** Generate API key → key shown once (copy prompt)
- **[A]** Revoke API key → subsequent API calls with that key return 401

---

## 16. Integrations

### 16.1 HubSpot
- **[A]** Connect HubSpot → OAuth flow → connected
- **[A]** Push lead to HubSpot → contact created in HubSpot with conversation summary
- **[A]** HubSpot flush (batch push) → all pending leads pushed

### 16.2 Salesforce
- **[A]** Connect Salesforce → configure credentials → connected
- **[A]** Push lead to Salesforce → lead/contact created
- **[A]** Salesforce AI action fires on trigger

### 16.3 Jira / Linear
- **[A]** Connect Jira → OAuth → project list loaded
- **[A]** Connect Linear → OAuth → team list loaded
- **[A]** Push feature request cluster to Jira/Linear → issue created → link shown

### 16.4 Slack
- **[A]** Connect Slack (OAuth) → bot added to workspace
- **[A]** Slack Events API configured → incoming Slack messages handled as conversations
- **[A]** Slack bot replies in channel when escalated
- **[A]** Sentiment alert fires to configured Slack channel

### 16.5 WhatsApp / Messenger / Instagram
- **[A]** Configure Meta webhook verify token → GET challenge verified
- **[A]** Send message via WhatsApp → handled as conversation → bot replies via WhatsApp API
- **[A]** Same flows for Messenger and Instagram

### 16.6 Shopify
- **[A]** Connect Shopify → OAuth flow → ScriptTag injected
- **[A]** Order webhook received → HMAC verified → processed
- **[A]** Shopify AI action fires on Shopify order events

### 16.7 Notion / Google Drive / Dropbox
- **[A]** Connect Notion → OAuth → select page → ingest as knowledge source
- **[A]** Connect Google Drive → OAuth → select file → ingest
- **[A]** Connect Dropbox → OAuth → select file → ingest

### 16.8 Zapier Outbound Webhooks
- **[A]** Configure outbound webhook URL → conversation event fires → webhook received with HMAC signature

---

## 17. GDPR / Privacy

### 17.1 GDPR Banner
- **[C]** Widget shows GDPR consent banner on first load
- **[C]** Accept consent → conversations allowed + consent recorded
- **[C]** Decline → widget non-functional until consent given (or alternative configured)

### 17.2 Contact Data Deletion
- **[A]** Delete contact → all conversations + personal data removed from DB

---

## 18. Public API

### 18.1 Widget Config
- **[E]** `GET /api/v1/widget/{chatbot_id}/config` → returns widget config without auth
- **[C]** Widget fetches this endpoint on load → correct config applied

### 18.2 Public Chat (SSE)
- **[E]** `POST /api/v1/public/chat` → SSE stream → token-by-token response
- **[E]** Rate limit applied → 429 after threshold exceeded
- **[C]** Allowed domains header checked → cross-origin rejected if domain not allowed

### 18.3 Authenticated API (Developer)
- **[E]** Valid API key in `Authorization: Bearer` → 200 on protected endpoints
- **[E]** No/invalid API key → 401
- **[E]** Cross-workspace access attempt → 403 (tenant isolation enforced)
- **[E]** `GET /health` → 200 with no auth

---

## 19. Multi-Tenant Isolation (Security)

- **[E]** Workspace A token cannot access Workspace B resources (conversations, chatbots, leads)
- **[E]** Workspace A cannot read Workspace B's knowledge sources
- **[E]** Workspace A cannot push to Workspace B's CRM integration
- **[E]** Public chat endpoint is chatbot-scoped — not cross-workspace pollutable

---

## 20. Notifications & Proactive Intelligence Push

- **[B]** New high-score lead detected → Slack DM + email alert sent
- **[B]** Sentiment drops below threshold → Slack channel + email alert
- **[B]** Topic spike anomaly detected → alert pushed
- **[B]** Weekly digest email sent (nightly batch) with resolution rate, new gaps, top leads
- **[B]** In-app notification shows unread badge for new exceptions

---

## Priority Order for Initial Testing Run

| Priority | Area | Why |
|----------|------|-----|
| P0 | Auth + Onboarding | Nothing works without this |
| P0 | Widget chat (SSE) | Core product loop |
| P0 | Exceptions Queue | Core human interface |
| P1 | Knowledge source ingestion | Powers all AI responses |
| P1 | Gap Detection + KB approval | Self-improvement loop |
| P1 | Dashboard (resolution rate) | Primary KPI |
| P2 | Lead intelligence | Core differentiator |
| P2 | Topic + Sentiment intelligence | Core differentiator |
| P2 | Billing + Credits | Revenue path |
| P3 | Integrations (HubSpot, Slack, Meta) | Expansion |
| P3 | Team/RBAC + SSO | Enterprise readiness |
