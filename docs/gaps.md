# Pulse — Feature Gaps

Two gap sources combined: (1) Phase 1 spec commitments not yet built, (2) Chatbase competitive parity gaps.

**Chatbase data verified live:** chatbase.co pricing, docs, changelog — March 2026.

Last updated: 2026-03-08 (session 10 — P2 sprint)

---

## Priority Legend

| Code | Meaning |
|---|---|
| **P0** | Blocks sales / breaks core use cases — fix immediately |
| **P1** | Competitive parity / Phase 1 spec commitment — next sprint |
| **P2** | Growth phase — meaningful retention impact |
| **P3** | Scale / enterprise — future roadmap |

---

## 1. Phase 1 Spec Gaps (committed, not built)

These were explicitly listed as Phase 1 MVP requirements in `pulse_dev_handover.md`.

### 1.1 Authentication & Access Control

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P1 | **SSO / SAML** | §1.2 — "Required — even if hidden behind higher tier" | ~~Not implemented at all. Only email + Google OAuth exist.~~ **DONE (session 9):** OIDC SSO — `sso_configs` table (Fernet-encrypted client_secret); `GET /auth/sso/check` domain lookup; `GET /auth/sso/authorize` OIDC discovery + Redis state + IdP redirect; `GET /auth/sso/callback` code exchange + userinfo + find-or-create Agent + Pulse JWT; `GET/PUT/DELETE /workspaces/{id}/sso` admin config CRUD; SSO settings page with discovery URL help; `/auth/sso/complete` token ingestion page; login page SSO email input. Covers Okta, Microsoft Entra, Google Workspace, Auth0. |
| P1 | **RBAC** | §1.2 — "Full role-based access control required" | ~~`agents` table exists but no roles, no permissions, no role assignment UI.~~ **DONE (session 2):** owner/admin/member roles on `WorkspaceMembership`; admin gate on invite endpoints. SSO/SAML still missing. |
| P1 | **Workspace invitations** | §1.2 — "email-based workspace invitations as default" | ~~No invite endpoint, no invite email, no invite UI.~~ **DONE (session 2):** token-based invites, email send, team settings page, accept-invite flow. |

### 1.2 RAG Pipeline

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P1 | **Notion ingestion** | §5.1 — source type list | Not implemented. (Chatbase: live, all plans.) |
| P1 | **CSV ingestion** | §5.1 — source type list | ~~Not implemented.~~ **DONE (session 4):** `csv_extractor.py` reads DictReader rows into key: value text; pipeline routes `.csv` file uploads through it; dropzone accepts `text/csv`. |
| P1 | **Q&A pair ingestion** | §5.1 — source type list | ~~Not implemented.~~ **DONE (session 4):** `createDocumentFromText` fixed to send `raw_content` + correct `source_type: "qa"`; `AddSourceModal` passes `knowledge_base_id` through. End-to-end verified. |
| P1 | **Sitemap crawl** | §5.1 — source type list | ~~PARTIAL (session 2).~~ **DONE (session 4):** `sitemap_extractor.py` fetches sitemap XML, recurses into sitemap indexes (cycle-safe), returns up to 200 URLs. Pipeline fans out: creates one child `url` document per URL and queues each for ingestion. Parent document status set to `indexed`. |
| P1 | **Text snippet / plain text paste** | §5.1 — source type list | ~~Not implemented.~~ **DONE (session 4):** Same fix as Q&A — `createDocumentFromText` now correctly sends `source_type: "text"` and `raw_content`. Wiring verified end-to-end. |
| P1 | **Auto-sync / re-crawl** | §5.1 — "Re-ingests sources on schedule (daily/weekly) or on-demand" | ~~No scheduled re-crawl.~~ **DONE (pre-session 2):** `sync_stale_documents` Celery beat task wired. **Session 2:** `sync_frequency` field (manual/daily/weekly/monthly) added to Document model + sources UI dropdown. |
| P1 | **Configurable confidence threshold per chatbot** | §5.1 — "Threshold is configurable per chatbot by workspace admin" | ~~Hardcoded at ~0.65. No field in chatbot settings UI.~~ **DONE (session 3):** Full "AI Behavior" section in SettingsTab — confidence threshold slider, temperature, retrieval_top_k, provider/model picker, reranking toggles. Backed by existing PUT /llm-config endpoint. |
| P2 | **Cross-session conversation memory** | §5.1 — "Optional persistent cross-session memory (configurable)" | In-session context works. No persistence across sessions / return visits. |
| P2 | **Source citations rendered in chat UI** | §5.1 — "Every response cites the source article/document" | ~~RAG prompt instructs LLM to output `[1]` references. Chat bubble renders plain text only — citations not clickable.~~ **DONE (session 3):** RAG engine loads Document title+source_url for each retrieved chunk; sources propagate through ResolutionEvent → ChatEvent → SSE done event; widget fixes `parsed.token` → `parsed.data` streaming bug; `renderMarkdownWithSources` replaces `[1]` markers with styled superscript links and appends a footnotes section. |

### 1.3 Living Knowledge Base

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P2 | **Knowledge Velocity metric** | §5.2 — "Weekly KB improvement rate: gaps closed vs. new gaps opened" | ~~Data exists in gap_events and gap_clusters. Not surfaced anywhere in the UI.~~ **DONE (session 3):** Dashboard endpoint now queries `AutonomousResolutionStats.knowledge_velocity` (latest record); surfaced as an orange Flame card on the dashboard page when > 0. |

### 1.4 Intelligence Layer

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P1 | **Competitive Intelligence module** | §5.4.6 — one of the 7 mandatory intelligence modules | ~~No frontend page exists.~~ **DONE (session 2):** `/intelligence/competitive` page showing competitor mentions, churn risk, and expansion signals from `IntelligenceSignal`. All 7 intelligence modules now have UI. |
| P1 | **Topic + sentiment anomaly alerts** | §5.4.4 §5.4.5 — "Alert when topic spikes / sentiment drops below threshold" | ~~`send_alerts.py` Celery task exists. No UI for configuring alert thresholds. Triggers not wired.~~ **DONE (session 4):** `alert_min_confidence` threshold field added to Slack and Email integration config; `send_alerts.py` reads threshold and skips low-confidence conversations below it. UI in integrations settings page. |
| P2 | **Segment-level sentiment** | §5.4.5 — "Sentiment by customer segment / company / contact" | ~~Workspace-level trend only.~~ **DONE (session 10):** `GET /sentiment-by-segment?days=N&segment=chatbot|contact` endpoint; horizontal BarChart in sentiment page with By Chatbot / By Contact toggle and color-coded bars. |
| P2 | **Real-time lead scoring per message** | §5.4.1 — "Score updated per message during conversation (0–100)" | Post-conversation scoring exists. No real-time per-message scoring during chat. |
| P2 | **Conversation outcome tagging** | §0 — "Every conversation tagged: resolved/escalated/churned/upgraded" | ~~Fields exist in `conversation_analysis`. Not displayed on conversations page.~~ **DONE (session 10):** `OutcomeBadge` component on conversations page; outcome filter dropdown (client-side); `outcome` query param on `GET /conversations` backend endpoint. |

### 1.5 Integrations

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P1 | **Slack escalation alerts** | §5.3 + §5.6 — "Notify team when escalation arrives (configurable)" | ~~Alert threshold config has no UI. Not confirmed firing.~~ **DONE (session 4):** Threshold config UI in integrations settings; `send_alerts.py` wired to read threshold before firing. Confirmed end-to-end via code trace. |
| P1 | **Email escalation alerts** | §5.3 + §5.6 | ~~Service exists, wiring unclear.~~ **DONE (session 4):** Same fix as Slack — threshold config UI added for Email integration; task fires via existing email service. |
| P1 | **CRM push on lead threshold** | §5.6 — "Auto-push lead data to HubSpot at threshold" | ~~`flush_lead_score` never called — scores were computed but never flushed or pushed.~~ **DONE (session 4):** `flush_lead_score.delay()` now called after each conversation turn in `resolution_service.py`. HubSpot push fires at lead threshold as designed. |
| P1 | **Jira / Linear feature request push** | §5.6 — "Push feature request clusters to PM tool" | `linear_jira.py` exists. Wiring confirmed via code trace — fires from `analyze_feature_requests` task. Considered done. |
| P1 | **Weekly intelligence digest (Slack + email)** | §5.4 — "Proactive push: weekly digest" | `weekly_digest.py` Celery beat task confirmed wired. Considered done (no gaps found in wiring). |

### 1.6 Widget

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P1 | **Lead capture pre-chat form** | §5.5 — "Collect visitor name/email before first message" | ~~Not implemented.~~ **DONE (session 2):** `lead_capture_enabled` + `lead_capture_fields` in widget config; pre-chat form rendered in widget before first message; AI-triggered via `collect_lead` action; `/public/chat/lead` endpoint creates/finds Contact. |
| P1 | **GDPR cookie consent banner** | §1.6 + §5.5 — "Configurable consent banner before widget initializes" | ~~Widget has no consent gate before initializing.~~ **DONE (session 4):** `gdpr_consent_enabled` + `gdpr_consent_text` fields in widget config; consent banner overlays widget on first open; decline closes widget; accept persists to localStorage (no re-prompt on return); input locked during banner; configurable per chatbot from Customize page. |
| P2 | **Conversation persistence across sessions** | §5.5 — "Optional — remember user across sessions (configurable)" | Widget forgets conversation on page reload or return visit. |

### 1.7 Non-Functional Requirements

| Priority | Feature | Spec Reference | What's Missing |
|---|---|---|---|
| P2 | **Configurable data retention** | §1.7 — "Configurable per workspace. Automated purging beyond retention window." | ~~No UI, no backend purge job.~~ **DONE (session 10):** `data_retention_days` on workspaces (Alembic migration); `GET/PUT /workspaces/{id}/data-retention` endpoints; daily `purge_old_data` Celery beat task; Data Retention settings page with radio options (forever/90/180/365/custom). |
| P2 | **BYOK usage / cost breakdown** | §1.3 — "Users in BYOK mode see API usage/cost breakdown (model calls, estimated cost)" | ~~Credit balance visible. No per-model usage breakdown for BYOK users.~~ **DONE (session 10):** `GET /billing/usage?days=30` — token aggregation by model from messages, per-model cost lookup (`MODEL_COSTS` dict), daily time series with zero-filled gaps; billing page: total tokens + estimated cost stats, daily BarChart, model breakdown table. |
| P3 | **Audit logging** | §1.6 — SOC 2 requirement: "All admin actions and data access logged" | ~~Not implemented.~~ **DONE (session 10):** `audit_logs` table (actor, action, resource, ip, metadata JSONB); `log_audit()` helper; instrumented chatbot CRUD, KB, invitations, workspace, SSO, API keys; `GET /audit-logs` with pagination + action filter; audit log viewer page at `/settings/audit-logs`. |
| P3 | **SOC 2 Type II** | §1.6 — "Target compliance. Design with SOC 2 controls in mind." | GDPR only. SOC 2 not addressed. (Chatbase: SOC 2 certified, badge on site.) |

---

## 2. Chatbase Competitive Parity Gaps

**Verified live on chatbase.co, March 2026.** Features are only listed here if confirmed present in their pricing page, docs, or changelog — not assumptions.

### 2.1 Chatbase Pricing (verified)

| Plan | Monthly | Annual (per month) | Credits | Agents | AI Actions/agent |
|---|---|---|---|---|---|
| Free | $0 | $0 | 50 | 1 | 0 |
| Hobby | $40 | $32 | 500 | 1 | 5 |
| Standard | $150 | $120 | 4,000 | 1 | 8 |
| Pro | $500 | $400 | 15,000 | 1 | 12 |
| Enterprise | Custom | Custom | Unlimited | Higher | Higher |

Note: 1 agent per plan by default. Extra agents: $300/agent/year add-on.

Add-ons: Auto-recharge credits ($40/1,000 credits), Extra agents ($300/agent/year), Remove branding ($1,188/year).

### 2.2 Data Sources (verified)

| Priority | Feature | Chatbase Status |
|---|---|---|
| P1 | **Sitemap crawl** | Live — all plans. Full site crawl + sitemap XML + individual URLs. Include/exclude path filters. |
| P1 | **Text Snippets** | Live — all plans. Rich text editor (bold, lists, links, headings). |
| P1 | **Q&A pair ingestion** | Live — all plans. Multiple question variants per answer, usage metrics per Q&A. |
| P1 | **Notion integration** | Live — all plans. Auto-retrains on Notion changes (Standard+). ~~Not implemented.~~ **DONE (session 7):** OAuth flow (`/oauth/notion/authorize` + `/oauth/notion/callback`) stores bot token in `IntegrationConfig`; `notion_extractor.py` fetches page content via Notion API (recursive block traversal); `notion` source type added to ingestion pipeline; "Connect Notion" button on integrations settings page. |
| P1 | **Auto-retrain every 24h** | Live — Standard+ only. Covers websites, Notion, and remote storage (Google Drive, Dropbox). |
| P2 | **Zendesk ticket ingestion** | ~~Live — Pro only.~~ **DONE (session 10):** OAuth flow with subdomain input; `zendesk_extractor.py` fetches all Help Center articles, strips HTML, cursor pagination; pipeline fans out one Document per article; integrations page ZendeskConnectButton; AddSourceModal Zendesk tab. |
| P2 | **Salesforce ticket ingestion** | ~~Live — Pro only.~~ **DONE (session 10):** OAuth flow (access_token Fernet-encrypted, instance_url plain); `salesforce_extractor.py` SOQL Knowledge__kav query with fallback to KnowledgeArticleVersion; fan-out one Document per article; `salesforce_contact_lookup` + `salesforce_create_case` AI actions; integrations page card + AddSourceModal tab. |
| P2 | **Google Drive / Dropbox** | ~~Not fully launched.~~ **DONE (session 10):** Google Drive — OAuth (drive.readonly, offline), extractor exports Docs as text, lists folders, auto-refreshes tokens. Dropbox — OAuth (offline), `dropbox_extractor.py` recursive folder listing with cursor pagination, filters .txt/.md/.csv/.rst under 1MB; both have AddSourceModal tabs + integrations page cards. |

### 2.3 AI Actions — Confirmed Live (all plans with action limits)

Chatbase's "AI Actions" framework lets the bot take real actions mid-conversation, not just answer questions. **Pulse has zero agentic capability.** Verified actions:

| Priority | Action | What It Does |
|---|---|---|
| P1 | **Collect Leads** | ~~Not implemented.~~ **DONE (session 2):** `collect_lead` action type triggers pre-chat form or inline form mid-conversation via AI function calling. |
| P1 | **Escalate to Human** | Creates a ticket with conversation summary in Zendesk, Salesforce, Intercom, Freshdesk, or Zoho Desk. This is Chatbase's entire "human handoff" — no native queue UI. Pulse has native Exceptions Queue instead. |
| P1 | **Custom Action (webhook)** | ~~Not implemented.~~ **DONE (session 2):** `webhook` action type — AI fires POST to configured HTTPS URL mid-conversation. UI for creating/managing actions in chatbot settings. |
| P1 | **Calendly** | Show available slots and book meetings directly in chat. ~~Not implemented.~~ **DONE (session 7):** `calendly` action type — admin pastes scheduling URL in action config; widget renders booking link button; no OAuth required. |
| P1 | **Cal.com** | Same as Calendly, for Cal.com accounts. ~~Not implemented.~~ **DONE (session 7):** `calcom` action type — identical to Calendly, reuses `showCustomButton` widget method. |
| P1 | **Slack Action** | Send a message to a Slack channel when triggered during conversation (e.g. notify team of new lead). ~~Not implemented.~~ **DONE (session 6):** `slack_message` action type — fires POST to configured Slack webhook URL mid-conversation; configurable message template; UI in AI Actions settings. |
| P1 | **Custom Button** | Display clickable buttons that redirect users to specific URLs. ~~Not implemented.~~ **DONE (session 6):** `custom_button` action type — widget renders `<a>` element with configurable label + URL; AI triggers it mid-conversation. |
| P1 | **Web Search** | Real-time web search for answers outside the KB (e.g. current weather, news). ~~Not implemented.~~ **DONE (session 6):** `web_search` action type — calls DuckDuckGo Instant Answer API (no key required); results injected as LLM context; tool spec built with `query` parameter for OpenAI function calling. |
| P2 | **Stripe Actions** | ~~Requires Stripe OAuth.~~ **DONE (session 10):** `stripe_get_invoices` + `stripe_subscription_status` action types; customer search by email → invoices/subscriptions via Stripe API; secret_key added to SENSITIVE_FIELDS (Fernet-encrypted); Stripe card in integrations settings. |
| P2 | **Salesforce Actions** | Salesforce-specific actions (contact lookup, case creation, etc.). |
| P2 | **Shopify Actions** | ~~Not implemented.~~ **DONE (session 10):** `shopify_order_status` action — extracts order number, queries Admin API, returns status summary; `shopify_storefront` action — returns custom_button shape; both wired into build_tools_for_chatbot() and actions UI. |

### 2.4 Chatbot Configuration (verified)

| Priority | Feature | Chatbase Status |
|---|---|---|
| P0 | **Suggested questions / quick replies** | ~~Not implemented.~~ **DONE (session 2):** `quick_replies` config field; widget renders chip buttons after each bot message. Chatbase now supports nested suggested messages (Mar 2026) — flat chips only in Pulse. |
| P1 | **Chatbot duplication** | Live — all plans. One-click duplicate (Jan 2026). ~~Not implemented.~~ **DONE (session 3):** `POST /{chatbot_id}/duplicate` copies all settings, system prompt, LLM config, and widget config; Duplicate button in chatbot detail header routes to new chatbot. |
| P1 | **Response length / temperature controls** | Standard settings in playground. |
| P1 | **Personality presets** | Tone templates that pre-populate system prompt. ~~Not implemented.~~ **DONE (session 5):** 5 presets (Professional, Friendly, Concise, Technical, Empathetic) in chatbot SettingsTab; dropdown pre-fills system prompt textarea. |

### 2.5 Chat Widget (verified from docs/pricing)

| Priority | Feature | Chatbase Status |
|---|---|---|
| P0 | **iFrame embed** | Live — JS snippet + iFrame both available. |
| P0 | **Markdown rendering** | Live — bold, headers, lists, links render in chat. |
| P1 | **Allowed domains restriction** | Live — restrict widget to whitelisted domains. ~~Not implemented.~~ **DONE (session 5):** `allowed_domains` in WidgetConfig; backend checks Origin header on `/public/chat` and returns 403 if not in allowlist (subdomain-aware); comma-separated input on Customize page. |
| P1 | **Auto-show pop-up trigger** | Live — auto-open widget after N seconds. ~~Not implemented.~~ **DONE (session 5):** `auto_open_delay` field in WidgetConfig; widget schedules `setTimeout` on mount; configurable number input on Customize page. |
| P1 | **Source citation rendering** | Confirmed in their docs as a feature. ~~Not implemented.~~ **DONE (session 3):** Superscript `[1]` links + footnotes section in widget. See §1.2 above. |
| P1 | **Message copy button** | Live. ~~Not implemented.~~ **DONE (session 5):** Copy button (⎘) on assistant messages; visible on hover; uses `navigator.clipboard`. |
| P1 | **Thumbs up / down feedback** | Live on paid plans. ~~Not implemented.~~ **DONE (session 5):** 👍/👎 buttons on assistant messages; fire-and-forget POST to `/messages/{id}/feedback`; `message_feedback` DB table (migration); `workspace_id` added to widget config response so widget can construct the endpoint URL. |
| P1 | **Voice / dictation input** | Live — Feb 5, 2026. Customers can speak instead of type. Available on website widget, agent page, WhatsApp, Instagram, Messenger. **Not in our research doc — new feature.** ~~Not implemented.~~ **DONE (session 6):** Mic button in widget input area using `SpeechRecognition` / `webkitSpeechRecognition`; hidden on unsupported browsers; red active indicator while listening; transcript appended to input field. |
| P2 | **Custom CSS override** | ~~Live — advanced widget customization.~~ **DONE (session 10):** `custom_css` field in WidgetConfig; injected as second `<style>` element in shadow root after default styles; textarea in Customize page; null = no override. |
| P2 | **Cross-session conversation history** | ~~Live on paid plans.~~ **DONE (session 10):** `persist_conversation` boolean in WidgetConfig; widget stores `conversation_id` in localStorage (keyed by chatbot ID) when enabled; restored on next open; `null` = always fresh. Toggle on Customize page. |

### 2.6 Deployment Channels (verified from pricing table)

All confirmed live (Hobby+):

| Priority | Channel | Notes |
|---|---|---|
| P1 | **WhatsApp Business** | Live. Voice notes supported (dictation). ~~Not implemented.~~ **DONE (session 8):** `whatsapp.py` webhook handler; verifies Meta challenge; decrypts stored Fernet token; routes text messages through resolution pipeline; replies via WhatsApp Cloud API. ChannelWebhookCard in integrations settings page for phone_number_id + access_token config. |
| P1 | **Facebook Messenger** | Live. ~~Not implemented.~~ **DONE (session 8):** `messenger.py` webhook handler; page_id routing; decrypts page_access_token; replies via Messenger Send API. |
| P1 | **Instagram Direct** | Live. ~~Not implemented.~~ **DONE (session 8):** `instagram.py` webhook handler; account_id routing; replies via Instagram Messaging API (same Send API endpoint as Messenger). |
| P1 | **Slack bot deployment** | Live — deploy chatbot AS a Slack bot (separate from Slack Action). ~~Not implemented.~~ **DONE (session 7):** OAuth flow installs bot into Slack workspace; `POST /slack/events` verifies HMAC signature, handles `url_verification` challenge, routes DMs + mentions through `handle_message` resolution pipeline, posts reply via `chat.postMessage`; "Connect Slack Bot" card on integrations settings page. |
| P1 | **WordPress plugin** | Live. |
| P1 | **Shopify** | Live — native integration with full AI Actions (Feb 2026). ~~Not implemented.~~ **DONE (session 8):** `shopify_oauth.py` — OAuth authorize/callback with shop fixation attack guard, stores encrypted access_token, injects Pulse widget via Shopify ScriptTag API, stubs order webhook; ShopifyConnectButton on integrations settings page with shop domain input. |
| P2 | **Custom domain for shareable link** | Live — add-on or higher plans. Not implemented. |

### 2.7 Analytics (verified from pricing + docs)

| Priority | Feature | Chatbase Status |
|---|---|---|
| P0 | **Basic analytics** | Live — Hobby+. Conversations per day, activity tracking. |
| P1 | **Advanced analytics** | Live — Pro+. Includes sentiment analysis, topics analysis, unanswered questions. |
| P1 | **Per-chatbot conversation log** | Live — Activity tab per agent, with date range filter. ~~Date range filter missing.~~ **DONE (session 5):** From/To date inputs on Conversations page; `date_from`/`date_to` query params threaded through `getConversations` → backend `list_conversations` service. |
| P1 | **Sources suggestions** | Live — Pro+. Suggests what to add to KB based on unanswered questions. |
| P2 | **Chats by country** | ~~In advanced analytics (Pro+).~~ **DONE (session 10):** `country_code`/`country_name` on conversations; `geoip.py` via ip-api.com (private IPs skipped); resolved on new conversation creation; `GET /analytics/chats-by-country?days=N`; Geography intelligence page with BarChart + flag emoji table. |

### 2.8 Integrations (confirmed in pricing comparison table)

All listed below confirmed live (Standard+):

Stripe, Zendesk, Salesforce, Intercom, HubSpot, Zoho Desk, Freshdesk, Sunshine (Zendesk), Zapier, Shopify, Slack, WhatsApp, Messenger, Instagram, Calendly, WordPress.

| Priority | Notable gap for Pulse |
|---|---|
| P1 | **Zapier** — native integration (Standard+). ~~Not implemented.~~ **DONE (session 6):** `workspace_webhooks` table + CRUD endpoints (`GET/POST/DELETE /workspaces/{id}/webhooks`); HMAC-signed payloads (`X-Pulse-Signature`); fires on `conversation.created`, `conversation.escalated`, `conversation.resolved`, `message.feedback`; Webhooks settings page + sidebar link. |
| P1 | **Intercom** — can push/handoff to Intercom (Standard+) |
| P1 | **HubSpot** — Pulse has partial push; Chatbase has full integration |

### 2.9 Security & Enterprise (verified from pricing + changelog)

| Feature | Chatbase Status |
|---|---|
| **SSO** | Live — Enterprise only (Jan 26, 2026) |
| **White-labeling** | ~~Enterprise plan + "Remove Powered By" add-on.~~ **DONE (session 10):** `white_label_enabled` on workspace; widget suppresses Powered by Pulse badge when enabled; GET/PUT `/white-label` endpoints; toggle in billing settings. |
| **Audit logs** | Enterprise only |
| **SLAs** | Enterprise only |
| **SOC 2** | SOC 2 badge confirmed on site |
| **GDPR** | Live — all plans |
| **2FA** | ~~Live — all plans.~~ **DONE (session 10):** TOTP via pyotp; Fernet-encrypted secret; setup/verify/disable endpoints; login 202 flow; QR code setup page at /settings/security. |
| **Allowed domains** | Live — whitelist domains that can embed the widget |

### 2.10 Billing / Plan Features (verified)

| Priority | Feature | Chatbase Status |
|---|---|---|
| P1 | **Annual discount** | 20% off all plans — confirmed live. ~~Not implemented.~~ **DONE (session 3):** `PLAN_PRICES_ANNUAL` dict added; `interval` param threaded through CheckoutRequest → billing service → Stripe checkout; monthly/annual toggle UI on billing page shows 20% discounted prices and yearly savings. |
| P1 | **Auto-recharge credits** | ~~Live add-on — $40/1,000 credits, fires when balance drops below threshold.~~ **DONE (session 4):** `auto_recharge_enabled/threshold/amount` columns on workspaces (migration applied); `trigger_auto_recharge` Celery task creates Stripe InvoiceItem + Invoice + pays; fires from `debit_credits()` when balance crosses threshold (with concurrency guard + idempotency key); GET+PUT endpoints; billing settings UI with enable toggle, threshold input, amount dropdown. |
| P1 | **Plan usage indicator** | Confirmed (workspace Usage page in docs). ~~Not implemented.~~ **DONE (session 3):** Plan badge in sidebar bottom (above user avatar) shows plan name, links to billing, and shows "Upgrade for more features" on free tier. |

---

## 3. Features Chatbase Does NOT Have (Pulse Advantages)

These are real differentiators that Chatbase lacks entirely. Important not to lose sight of these.

| Feature | Pulse Has | Chatbase Has |
|---|---|---|
| **Autonomous Resolution Rate** | Primary KPI, tracked per chatbot over time | Not tracked. Chatbase just shows conversation counts. |
| **Exceptions Queue** | Full UI with contact context, AI suggested action, reply interface, resolve flow | Just "Escalate to Human" action that creates a ticket in external CRM. No native queue. |
| **Gap cluster auto-draft** | AI drafts KB article for each gap cluster → human approves | "Sources suggestions" (Pro+) shows what to add, but does not draft articles. |
| **Topic clustering (BERTopic)** | Full topic intelligence with trend data and drill-down | "Topics analysis" in Advanced analytics (Pro+). Basic vs. Pulse's full intelligence module. |
| **Lead intelligence scoring** | Per-contact scoring with hot/warm/cold tiers, full signal taxonomy | "Collect Leads" is just a form — captures name/email, no scoring. |
| **Feature request clustering** | Extracts + clusters product feature requests from conversations | Not present. |
| **Competitive intelligence** | Extracts competitor mentions, stores as signals (no UI yet) | Not present. |
| **BYOK encryption (Fernet)** | Customer API keys encrypted at rest | Unknown — Chatbase likely stores keys but encryption details not public. |
| **Living KB self-improvement loop** | Conversation fails → gap logged → cluster → draft → approve → reindex → resolution improves | No closed loop. Sources suggestions is manual, not auto-drafted. |

---

## 4. Quick-Win Gaps (highest ROI, lowest effort)

Features where the hard work is already done:

| Effort | Feature | Why Easy |
|---|---|---|
| Low | ~~**Competitive Intelligence page**~~ | ~~Data in `intelligence_signals` with `signal_type = "competitor_mention"`. Frontend page only.~~ **DONE (session 2).** |
| Low | ~~**Source citations in widget**~~ | ~~RAG prompt already outputs `[1]`. Widget needs to parse and render as document links.~~ **DONE (session 3).** |
| Low | ~~**Confidence threshold field in chatbot settings**~~ | ~~Backend accepts it via PUT `/llm-config`. Just add a UI field.~~ **DONE (session 3):** Full AI Behavior section with all LLM config fields. |
| Low | ~~**Knowledge Velocity metric on dashboard**~~ | ~~gap_events and gap_clusters tables have all required data.~~ **DONE (session 3).** |
| Low | ~~**Annual billing toggle**~~ | ~~Stripe supports annual intervals. UI toggle + price config only.~~ **DONE (session 3).** |
| Low | ~~**Plan usage indicator**~~ | ~~Credits balance API exists. Surface it prominently in sidebar or dashboard header.~~ **DONE (session 3):** Plan badge in sidebar. |
| Medium | ~~**Q&A pair ingestion**~~ | ~~New document type in ingestion pipeline. Backend + UI work.~~ **DONE (session 4).** |
| Medium | ~~**Sitemap ingestion**~~ | ~~Parse sitemap.xml → extract URLs → queue existing URL ingestion pipeline per URL.~~ **DONE (session 4).** |
| Medium | ~~**Text snippet source type**~~ | ~~Simpler than file upload — just a text field that creates a document record.~~ **DONE (session 4).** |
| Medium | ~~**Suggested questions / quick replies in widget**~~ | ~~Widget config field + render chip buttons before first message.~~ **DONE (session 2).** |
| Medium | ~~**Markdown rendering in widget**~~ | ~~Add `marked` (2kb) to widget bundle, replace plain text render.~~ **DONE (pre-session 2):** `renderMarkdownLite` already in use. |
| Medium | ~~**Conversation export CSV**~~ | ~~Backend: stream query to CSV. Frontend: download button on conversations page.~~ **DONE (session 5):** `GET /conversations/export` streaming endpoint; one-click "Export CSV" button on Conversations page. |

---

## 5. Newly Discovered Chatbase Features (not in prior research)

These were shipped by Chatbase after our research doc was written. Not in `chatbase_full_feature_list.md`.

| Feature | Launched | What It Is |
|---|---|---|
| **Voice / dictation input** | Feb 5, 2026 | Users can speak instead of type. Works on widget, agent page, WhatsApp, Instagram, Messenger. Voice notes on social channels. |
| **Nested suggested messages** | Mar 4, 2026 | Hierarchical quick reply buttons — group related topics under a parent (e.g. "Orders" → Track / View / Update billing). Much more powerful than flat quick replies. |
| **Native Shopify integration** | Feb 24, 2026 | AI Actions specific to Shopify: add to cart, check order status, view cart/orders, change billing address, update billing info. |
| **SSO** | Jan 26, 2026 | Enterprise plan only. |
| ~~**Duplicate agent**~~ | Jan 22, 2026 | ~~Clone existing agent with all settings, sources, and prompts. All plans.~~ **DONE (session 3):** POST /duplicate endpoint + Duplicate button on detail page. |
| **Contacts management** | Ongoing | Chatbase has a "Contacts" section in the sidebar — manages captured leads and contacts. |

---

## 6. Explicitly Deferred (out of scope for Phase 1–2)

Do not build these now. Listed to prevent scope creep debates.

| Feature | Deferred To |
|---|---|
| Full shared inbox (traditional helpdesk) | Phase 3 |
| CSAT surveys | Phase 3 |
| Complex routing rules UI | Phase 3 |
| Live human agent as primary flow | Phase 3 |
| Voice / phone channel | Phase 4+ |
| A/B testing for bot responses | Phase 3 |
| Visual flow builder | Phase 3 |
| EU data residency | Enterprise tier |
| HIPAA compliance | Enterprise tier |
| On-premise deployment | Enterprise tier |
| Enterprise physical tenant isolation | Enterprise tier |
| Full Intercom API compatibility layer | Phase 2 |
| Intercom data importer | Phase 2 |
| Customer-facing public help center portal | Phase 2 |
