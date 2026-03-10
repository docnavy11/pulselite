# Chatbase Complete Feature List — Pulse Priority & Tier Mapping

**Document Purpose:** Exhaustive mapping of every Chatbase feature to Pulse build priorities and pricing tiers.
**Audience:** Engineering team — sprint planning and roadmap sequencing.
**Last Updated:** March 2026
**Source:** chatbase.co, help.chatbase.co, API docs, G2/Capterra, Reddit, Product Hunt, chatimize.com, lindy.ai, eesel.ai, featurebase.app, pagergpt.ai, chatbase.myprosandcons.com, changelogs

## Priority Definitions
| Code | Label | Timeline | Criteria |
|------|-------|----------|----------|
| P0 | MVP Critical | Pre-launch | Product doesn't work without this |
| P1 | Launch Essential | Launch + 4 weeks | Core value prop, primary use cases |
| P2 | Growth Phase | Months 3–8 | Retention, expansion, competitive parity |
| P3 | Scale Phase | Months 8–14 | Enterprise readiness, full platform |
| SKIP | Do Not Build | Never (v1) | Enterprise-only, rarely used by SMB, out of scope |

## Pulse Tier Definitions
| Tier | Price | Conv/mo | Primary User |
|------|-------|---------|-------------|
| Free | $0 | 100 | Lead generation, evaluation |
| Starter | $49 | 2,000 | Micro-SaaS, solopreneurs |
| Professional | $149 | 10,000 | SMB SaaS (primary target) |
| Agency | $299 | 50,000 | Agencies, white-label |
| Enterprise | Custom | Unlimited | Mid-market, compliance-heavy |

---

## Section 1: Chatbot Builder & Configuration
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Chatbot creation wizard | Step-by-step guided creation flow: name your bot, upload data source, configure behavior, deploy. No-code, completes in under 5 minutes from signup. | All | P0 | Free | Core onboarding UX; must match Chatbase speed-to-first-bot |
| Chatbot naming | Assign a custom display name to the chatbot (shown in widget header and shareable link). Name can be changed at any time without affecting embed code. | All | P0 | Free | Trivial to implement; critical for branding |
| System prompt / instructions | Freeform text field where the user defines the chatbot personality, tone, scope restrictions, and behavioral rules. Injected as system message in every LLM call. Character limit varies by plan. | All | P0 | Free | Core behavior control; higher char limits = better control |
| Personality & tone configuration | Preset or custom tone selectors (professional, friendly, concise, etc.) that pre-populate the system prompt template. Reduces onboarding friction for non-technical users. | All | P0 | Free | Can implement as prompt templates; reduces time-to-value |
| Welcome message / initial message | First message the chatbot sends automatically when a user opens the widget. Configured per-chatbot. Supports plain text. | All | P0 | Free | Critical for user engagement on first open |
| Fallback message configuration | Custom message shown when the bot cannot answer a question (low confidence or out-of-scope). Configured per-chatbot to match brand voice. | All | P0 | Free | Essential; prevents cold generic error responses |
| Confidence threshold setting | Slider or numeric input that sets the minimum retrieval confidence score before the bot answers vs. falls back. Allows tuning between recall and precision. | All | P0 | Starter | Key quality lever; expose in advanced settings |
| Suggested questions / quick replies | Up to N pre-configured questions shown as clickable chips on widget open. Reduces user friction and guides intent. Configurable per-chatbot. | All | P0 | Free | Implement as chip array below welcome message |
| Smart follow-up buttons | After a bot response, dynamically suggested follow-up question chips based on the current conversation context. Different from static suggested questions. | Hobby+ | P1 | Starter | Improves engagement; can generate via LLM post-response |
| Temperature / creativity setting | Numeric slider (0.0–1.0 or 0–2) controlling LLM response randomness. Low = factual/deterministic; high = creative/varied. Exposed in advanced model settings. | All | P1 | Starter | Standard LLM param; document clearly for non-technical users |
| Response length control | Setting to prefer short/medium/long responses, injected into system prompt as instruction. Not a hard token limit — guides style rather than truncating. | All | P1 | Starter | Important for customer support (concise) vs. documentation (detailed) use cases |
| Language setting override | Force the bot to always respond in a specific language regardless of the user input language. Alternative to auto-detect mode. | All | P1 | Starter | Critical for single-language businesses; separate from multi-language auto-detect |
| Test chat interface | Embedded live chat window inside the dashboard for testing the bot with different inputs before deployment. Shows actual bot responses with source attribution. | All | P0 | Free | Must have; blocks deployment confidence without it |
| Copy embed code button | One-click copy of the JS snippet or iframe code for website embedding. Available immediately after bot creation. | All | P0 | Free | Small UX detail; zero engineering effort, high perceived value |
| Character count display | Real-time display of how many characters of training data have been uploaded vs. the plan limit. Updates on each source addition. | All | P0 | Free | Critical for plan limit awareness; prevents surprise blocks |
| Multiple chatbots per account | Create and manage multiple distinct chatbots under one account. Each has independent knowledge base, settings, and deployment. Limit varies by plan: 1 (Free/Hobby), 2 (Standard), 3 (Pro). | All | P0 | Free/Starter/Professional | OPPORTUNITY: Pulse allows 5+ chatbots on Starter vs. Chatbase 1 |
| Chatbot duplication / cloning | Copy an existing chatbot (settings + data sources) to use as a starting point for a new bot. Saves setup time for similar use cases. | Not confirmed | P2 | Starter | Not confirmed in Chatbase; good differentiation |
| Chatbot deletion | Permanently delete a chatbot and all associated data. Free plan bots auto-deleted after 14 days of inactivity. | All | P0 | Free | Implement with confirmation dialog + data deletion warning |
| Bot activity timeout (Free plan) | Free plan chatbots are automatically deleted after 14 days of inactivity. Paid plan bots persist indefinitely. | Free | P0 | Free | Implement as warning notification before deletion |

---

## Section 2: Knowledge Base & Data Ingestion
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| PDF file upload | Upload PDF documents as training data. Chatbase extracts text content via PDF parser, chunks it, vectorizes it, and stores in vector DB. File size limits apply per plan. | All | P0 | Free | Standard RAG data source; use PyMuPDF or pdfplumber |
| Word document upload (DOCX) | Upload .docx Microsoft Word files. Text extracted including paragraphs, headings, tables. Images/diagrams are ignored. | All | P0 | Free | Use python-docx for extraction |
| Plain text file upload (TXT) | Upload .txt files. Raw text ingested, split into chunks, vectorized. Simplest data source type. | All | P0 | Free | Trivial to implement |
| Website URL crawl | Enter a URL and Chatbase crawls the page (and optionally sub-pages) to extract text content. Uses HTTP GET + HTML parsing, stripping nav/footer/script elements. | All | P0 | Free | Use Playwright or BeautifulSoup; respect robots.txt |
| Sitemap ingestion | Provide an XML sitemap URL and Chatbase automatically discovers and crawls all listed pages. More reliable than recursive crawl for large sites. | All | P0 | Free | Parse sitemap.xml, batch crawl listed URLs |
| Individual page URL ingestion | Add specific page URLs one-by-one (not full domain crawl). Good for targeting specific documentation pages without ingesting irrelevant content. | All | P0 | Free | Simple URL list input |
| Q&A pair ingestion | Manually enter question-answer pairs directly. Stored as structured knowledge, often retrieved with higher confidence than unstructured text. Ideal for FAQs. | All | P0 | Free | Store as special chunk type with high retrieval weight |
| Plain text paste | Copy-paste raw text directly into a text area. Immediately chunked and vectorized. Zero file handling required. | All | P0 | Free | Simplest possible data entry method |
| Notion integration (data source) | Connect Notion workspace and select pages/databases to ingest as training data. Uses Notion API with OAuth or token. Pages auto-synced on schedule. | All | P0 | Starter | Use Notion SDK; handle nested pages and databases |
| Zendesk ticket ingestion | Ingest historical Zendesk support tickets as training data. Bot learns from real resolved conversations. Higher-tier feature (Pro+). | Pro/Enterprise | P2 | Professional | High-value feature; requires Zendesk API integration |
| Salesforce ticket ingestion | Ingest Salesforce case/ticket history as training data. Bot learns from CRM interactions. | Pro/Enterprise | P2 | Professional | Requires Salesforce API; complex OAuth flow |
| Character limit — Free plan | 400,000 characters (~400KB) of training data. Approximately 200–300 pages of text. Resets when data is removed and replaced. | Free | P0 | Free | Implement hard limit with real-time counter in dashboard |
| Character limit — paid plans | 11,000,000 characters (~33MB) of training data for all paid plans (Hobby, Standard, Pro). Same cap across all paid tiers. | Hobby/Standard/Pro | P0 | Starter/Professional/Agency | OPPORTUNITY: Pulse can differentiate by offering more chars on higher tiers |
| Training links limit — Free plan | Maximum 10 source URLs on Free plan. Prevents abuse of the crawler. | Free | P0 | Free | Implement as URL count hard limit |
| Training links — paid plans | Unlimited source URLs on all paid plans. | Hobby/Standard/Pro | P0 | Starter | Standard for paid tiers |
| Auto-retrain every 24 hours | Scheduled job that automatically re-crawls all connected URL sources and refreshes the vector DB with updated content. Critical for keeping bots current. | Pro/Enterprise (implied from RSC data) | P1 | Professional | Implement as Celery beat scheduled task per-bot |
| Manual retrain / refresh | User-triggered button to immediately re-crawl and re-index all sources without waiting for the scheduled cycle. | All | P0 | Free | Simple trigger for the indexing pipeline |
| Detect content gaps | Automated analysis that identifies questions users asked which the knowledge base failed to answer. Surfaces as actionable list in dashboard. | Pro/Enterprise | P1 | Professional | Core intelligence feature; aligns with Pulse RAG gap detection |
| Detect conflicting sources | Automated detection of contradictory information across multiple data sources (e.g., two pages with different pricing). Flags for human review. | Pro/Enterprise | P2 | Professional | High-value quality assurance feature |
| Suggestions feature | Surfaces the specific questions the chatbot struggled to answer (low confidence or fell back). Shown in dashboard as list with frequency. Helps users identify KB gaps. | Hobby+ | P1 | Starter | Critical for KB improvement loop; easy to implement from failed retrievals |
| Source document management | View, rename, delete, and re-order individual data sources in the knowledge base. See character count per source. | All | P0 | Free | Simple CRUD UI for data sources |
| Chunking strategy (internal) | Text split into chunks of ~1,000–1,500 characters with overlap for context continuity. Uses semantic sentence-aware splitting. Users cannot configure chunk size in Chatbase. | All (not exposed) | P1 | Free | Expose chunk size setting in Pulse as differentiator |
| Vector embedding model | Uses OpenAI text-embedding-ada-002 or equivalent for converting chunks to vectors. Not user-configurable in Chatbase. | All (internal) | P0 | Free | Implement with Qdrant as vector store per Pulse stack |

---

## Section 3: AI Models & Configuration
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| GPT-4o Mini model | OpenAI GPT-4o Mini — lightweight, fast, cheap. 1 credit/response. Default for Free plan. Good for straightforward Q&A. | All | P0 | Free | Cost-efficient default for free tier |
| GPT-4o model | OpenAI GPT-4o — flagship model, strong reasoning. 10 credits/response (estimated). Available on Hobby+. | Hobby+ | P0 | Starter | Primary quality model for most SMB use cases |
| GPT-5 / GPT-5.x models | OpenAI GPT-5, GPT-5.1, GPT-5.2, GPT-5 Mini, GPT-5 Nano — latest generation models (2026). Available on higher plans. Significant capability improvement. | Standard/Pro | P2 | Professional | Add as they become GA; position as competitive advantage |
| GPT-OSS models | Open-source GPT models (GPT-OSS-120B, GPT-OSS-20B) — likely OpenAI's open weights. Available on Pro+. | Pro/Enterprise | P3 | Agency | For privacy-conscious or self-hosted enterprise use cases |
| o4 Mini model | OpenAI o4 Mini — reasoning-optimized model. Good for complex multi-step queries. | Pro/Enterprise | P2 | Professional | Position for technical documentation and complex support |
| Claude 4.5 Sonnet / Haiku / Opus | Anthropic Claude 4.5 family — strong instruction following, large context window. Haiku = fast/cheap, Sonnet = balanced, Opus = powerful. | Standard/Pro | P1 | Professional | Critical for users preferring Anthropic; 1 credit for Sonnet/Haiku tier |
| Claude 4.6 Sonnet / Opus | Anthropic Claude 4.6 — latest Claude generation (2026). Available on Pro/Enterprise. | Pro/Enterprise | P2 | Professional | Update model list as Anthropic releases |
| Gemini 2.5 Flash / Pro | Google Gemini 2.5 family — Flash is fast/cheap (1 credit), Pro is more capable. Excellent for multilingual use cases. | Standard/Pro | P1 | Professional | Gemini excels at multilingual; 1 credit = very cost-efficient |
| Gemini 3.x models | Google Gemini 3 Flash, Gemini 3.1 Pro — next-gen Gemini (2026). Latest available in Pro tier. | Pro/Enterprise | P2 | Agency | Add as they become GA |
| DeepSeek-V3 / R1 | DeepSeek open-source models — V3 for general use, R1 for reasoning. Privacy-friendly alternative to OpenAI. | Pro/Enterprise | P2 | Professional | Strong demand from privacy-conscious users; OPPORTUNITY to offer BYOAK |
| Llama 4 Scout / Maverick | Meta Llama 4 family — open-source models deployable self-hosted. Scout = efficient, Maverick = powerful. | Pro/Enterprise | P3 | Enterprise | Enterprise self-hosted compliance use case |
| Kimi K2 model | Moonshot AI Kimi K2 — strong multilingual model particularly for Chinese language support. | Pro/Enterprise | P3 | Enterprise | Niche use case for Asian market expansion |
| CommandR+ model | Cohere CommandR+ — designed for RAG use cases, strong retrieval augmentation. | Pro/Enterprise | P2 | Professional | Well-suited for knowledge base chatbot use case |
| Per-model credit cost system | Differential credit pricing: premium models (GPT-4, Claude Opus) cost 20 credits/response; mid-tier models (GPT-4 mini) cost 10; efficient models (Gemini, Claude Sonnet) cost 1. Prevents abuse while supporting model choice. | All | P0 | Free | Implement credit multiplier system per model; publish cost table clearly |
| Model switching without rebuild | User can change the LLM model for a chatbot at any time in settings without re-uploading training data. The knowledge base (vector embeddings) is model-agnostic. | All | P0 | Free | Embeddings are separate from completion model; trivial to switch |
| Model availability per plan | Free plan restricted to basic models (GPT-4o Mini only). Advanced models unlocked progressively on paid plans. | Plan-gated | P0 | Free | Implement model tier gates in plan config |
| BYOAK (Bring Your Own API Key) | NOT available in Chatbase. Users must use Chatbase's API key allocation. Major user complaint — power users want to use their own OpenAI/Anthropic keys. | Not available | P1 | Starter | MAJOR DIFFERENTIATION OPPORTUNITY for Pulse; implement as Starter+ feature |

---

## Section 4: Chat Widget & Embed
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| JavaScript snippet embed | Primary embed method: a <script> tag added to website HTML that loads the chat widget asynchronously. Does not block page load. Single line of code. | All | P0 | Free | Standard chat widget embed pattern |
| iFrame embed | Alternative embed using <iframe> to contain the full chat interface. Better for isolation from parent page CSS. Generates a URL to the hosted chat page. | All | P0 | Free | Generate iframe URL pointing to hosted chat page |
| Chat bubble / launcher button | Floating circular button in bottom-right corner of the page. On click, opens the chat panel. Standard chat widget UX pattern. | All | P0 | Free | CSS-positioned fixed element |
| Widget position configuration | Setting to choose widget position: bottom-right (default), bottom-left. | All | P0 | Free | Simple CSS positioning option |
| Widget color customization | Primary color picker that sets the chat bubble color, send button, and user message bubble background. Hex color input or color picker. | All | P0 | Free | CSS variable injection or inline styles |
| Avatar / icon customization | Upload a custom image for the chatbot avatar shown in the widget header and next to bot messages. Replaces default Chatbase logo. | All | P0 | Free | Image upload, stored as CDN URL |
| Widget header name display | The chatbot display name shown in the widget header bar. Configured via the chatbot name field. | All | P0 | Free | Simple text config |
| Background color customization | Set the background color of the chat widget panel. Separate from the primary/accent color. | All | P0 | Free | Separate CSS variable for background |
| User message bubble color | Customize the background color of user-sent messages inside the chat. Default is the primary color. | All | P0 | Free | CSS variable |
| Bot message bubble color | Customize the background color / text of bot responses. Default is white/light gray. | All | P0 | Free | CSS variable |
| Font customization | Choose from a set of supported web fonts for the widget text. Limited to system/web-safe fonts or a curated list. Custom fonts not supported. | All | P1 | Starter | Load Google Fonts or allow font-family input |
| Placeholder text | Customize the placeholder text inside the message input field (default: "Ask a question..."). Supports any string. | All | P0 | Free | Trivial textarea placeholder config |
| Welcome message display | Initial message displayed in the chat window on open, before the user sends any message. Animates in to simulate bot typing. | All | P0 | Free | Displayed as first bot message in thread |
| Auto-show pop-up (delay trigger) | Configure the widget to automatically expand/pop open after N seconds on page load. Useful for proactive engagement without user clicking. Timer-based, configurable per-chatbot. | All | P1 | Starter | setTimeout trigger in widget JS |
| Custom CSS override | NOT confirmed in Chatbase. Some competitors allow custom CSS injection for full widget restyling. | Not confirmed | P2 | Professional | DIFFERENTIATION OPPORTUNITY: Add as Professional feature |
| Mobile responsiveness | Chat widget automatically adapts to mobile screen sizes. Opens as full-screen overlay on mobile rather than corner panel. | All | P0 | Free | CSS media queries + full-screen mobile layout |
| Widget auto-open on mobile | Option to disable auto-open pop-up specifically on mobile (to avoid intrusive UX on small screens). | All | P1 | Starter | Separate mobile/desktop trigger settings |
| Powered by Chatbase branding | Default footer text in widget: "Powered by Chatbase". Visible to all end users. Removed via add-on. | Free/Hobby/Standard/Pro | P0 | Free | Show Pulse branding on Free; remove on Starter+ as competitive advantage |
| Remove branding (add-on) | Paid add-on at $39/month to remove "Powered by Chatbase" footer from the widget. Not included in any base plan. | Add-on ($39/mo) | P1 | Starter | PULSE ADVANTAGE: Include branding removal in Starter plan ($49) |
| Allowed domains restriction | Whitelist specific domains that are permitted to embed the chatbot widget. Prevents unauthorized embedding by others copying the script tag. | All | P1 | Starter | Simple domain allowlist check on widget load |

---

## Section 5: Conversation Interface
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Real-time streaming responses | Bot responses stream word-by-word as they are generated, rather than waiting for full completion. Dramatically improves perceived response time. | All | P0 | Free | SSE (Server-Sent Events) or WebSocket streaming from LLM |
| Typing indicator | Animated dots ("...") shown while the bot is generating a response. Standard UX pattern to indicate processing. | All | P0 | Free | Show animation while waiting for first token |
| Conversation history (within session) | Within a single browser session, the full conversation thread is preserved and sent as context to the LLM for multi-turn dialogue. | All | P0 | Free | Standard chat context window; truncate at token limit |
| Conversation history (cross-session) | Optionally persist chat history across browser sessions (via localStorage or server-side session). Allows users to continue previous conversations. | Not confirmed | P2 | Professional | Requires server-side session storage with user identifier |
| Markdown rendering | Bot responses support Markdown formatting: bold, italic, bullet lists, numbered lists, headers. Rendered as HTML in the widget. | All | P0 | Free | Use markdown-it or marked.js for rendering |
| Code block rendering | Code snippets in bot responses rendered in a styled <code> block with monospace font and optional syntax highlighting. | All | P1 | Starter | Add highlight.js for syntax highlighting |
| Hyperlink rendering | URLs in bot responses auto-linked or explicitly linked with anchor text. Links open in new tab. | All | P0 | Free | Standard markdown link rendering |
| Message copy button | Button on each bot message to copy the response text to clipboard. Shown on hover. | All | P1 | Starter | Clipboard API implementation |
| Thumbs up/down feedback | Per-message feedback buttons allowing users to rate bot responses. Data feeds into analytics and quality review. | Not confirmed | P2 | Professional | DIFFERENTIATION: Add as data source for intelligence layer |
| Emoji support in messages | Users can send emoji characters in their messages. Bot responses may include emoji if the model generates them. | All | P0 | Free | Unicode support in text input and rendering |
| File sharing in chat | Users can share files (images, PDFs) in the chat interface. NOT confirmed in Chatbase (text-only). | Not confirmed | P3 | Enterprise | Complex feature; low priority for v1 |
| Character limit per user message | Limit on the length of a single user message to prevent abuse and manage token costs. | All (implied) | P1 | Free | Implement maxLength on textarea |
| Source citation in responses | Display the source document name/URL that the bot used to generate its answer. Builds trust. Chatbase does this in test chat but not confirmed in embedded widget. | Partial | P1 | Starter | Show source links below response; configurable toggle |
| Conversation thread view (full-screen) | Custom help page that renders the chat as a full-page ChatGPT-style interface rather than a corner widget. Available as a hosted URL. | All | P1 | Starter | Separate hosted URL route for full-screen chat |

---

## Section 6: Lead Generation & Forms
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Lead capture form (built-in) | Native form inside the chat widget that collects visitor information. Shown before, during, or at a specific point in conversation. Collects name, email, phone. | All | P0 | Free | Core feature for SMB use case |
| Name field collection | Collect visitor first/last name via lead form. Stored as lead metadata. | All | P0 | Free | Standard form field |
| Email address collection | Collect visitor email address via lead form. Primary identifier for CRM. | All | P0 | Free | Validate email format before submission |
| Phone number collection | Collect visitor phone number via lead form. Optional field. | All | P0 | Free | Optional field with format hint |
| Form display timing — always | Lead form appears at every chat session until user has submitted. No ability to configure when it appears in Chatbase. Noted as intrusive by users. | All | P0 | Free | PULSE IMPROVEMENT: Add timing control (before/after N messages/on exit) |
| Form display timing control | NOT available in Chatbase. No option to show form before, after N messages, or on exit intent. Major UX complaint. | Not available | P1 | Starter | DIFFERENTIATION: Configurable trigger timing |
| Lead data storage | Submitted leads stored in Chatbase backend, viewable in the Leads overview dashboard. Persist indefinitely. | All | P0 | Free | Database table: leads (chatbot_id, name, email, phone, timestamp, session_id) |
| Leads overview dashboard | Dedicated section in the dashboard listing all collected leads with name, email, phone, timestamp, and conversation link. | All | P0 | Free | Simple data table with sorting and filtering |
| Lead export (CSV) | Export all leads to CSV file from the Leads overview. | Not confirmed (via API/Zapier) | P1 | Starter | Standard data export |
| Email notification on new lead | Email alert sent to account owner when a new lead is captured. | Not confirmed | P1 | Starter | DIFFERENTIATION: Webhook + email trigger |
| Lead export via Zapier/Make | Route lead data to any CRM (HubSpot, Salesforce, Pipedrive) via Zapier or Make automation. | Hobby+ | P1 | Starter | Standard webhook/Zapier integration |
| Lead export via Webhook | Send lead data as JSON POST to a specified webhook URL on capture event. | Hobby+ | P1 | Starter | Simple HTTP POST on form submission |
| Lead duplicate detection | NOT confirmed in Chatbase. No deduplication of leads by email across sessions. | Not available | P2 | Professional | Implement email-based dedup on capture |
| User segmentation by lead fields | NOT available in Chatbase. Cannot segment leads by custom fields or tags. | Not available | P3 | Professional | Add in Phase 3 |

---

## Section 7: Human Handoff & Escalation
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Built-in live chat (human takeover) | NOT available in Chatbase. No native agent inbox or live chat handoff. Must use third-party integration. Major limitation noted by multiple reviewers. | Not available | P2 | Professional | MAJOR DIFFERENTIATION for Pulse: build native inbox |
| Zendesk handoff (via AI Action) | Chatbase AI Action that creates a Zendesk support ticket and escalates to Zendesk Sunshine live chat when triggered. Configured as an AI Action, not a dedicated handoff feature. | All (requires AI Action setup) | P1 | Professional | Implement as Zendesk AI Action + Sunshine integration |
| Escalation trigger via natural language | Escalation conditions defined in plain English in the system prompt (e.g., "if the user asks to speak to a human, escalate to Zendesk"). No visual trigger builder. | All | P1 | Starter | Detect escalation intent via LLM classification in conversation loop |
| Negative sentiment escalation | Bot automatically flags conversations with negative sentiment and can trigger escalation to human agent. Pro plan feature. | Pro/Enterprise | P2 | Professional | Implement as sentiment score threshold trigger |
| Email fallback | NOT a dedicated feature in Chatbase. Can be approximated via Zapier routing lead/conversation data to email. | Zapier workaround | P1 | Starter | Implement as native email notification + transcript send |
| Crisp integration (handoff) | NOT confirmed in current Chatbase (was in older versions). Users must use Zapier for Crisp handoff. | Via Zapier | P2 | Professional | Low priority; Zendesk is primary |
| Intercom integration (handoff) | NOT a native Chatbase integration. Can be configured via Zapier or Make. | Via Zapier | P2 | Professional | Many Pulse target users will be on Intercom |
| Conversation transcript on handoff | When escalating to a human agent, the full conversation transcript is included so the agent has context. | Not confirmed (Zendesk AI Action) | P1 | Professional | Critical for handoff quality; include in escalation payload |

---

## Section 8: Analytics & Reporting
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Chats per day chart | Time-series line chart showing total conversation volume by day over a selected date range. Available on all plans. | All | P0 | Free | Standard timeseries visualization |
| Chats by country | Geographic breakdown of where chatbot users are located, based on IP geolocation. Bar chart or map visualization. | All | P1 | Starter | Use MaxMind GeoIP or IP-API for geolocation |
| Chat logs viewer | Full conversation history browser. Shows each session with timestamp, all messages, and bot responses. Filterable by date. | All | P0 | Free | Database-backed conversation log with pagination |
| Date range filter | Analytics date picker to filter all metrics by custom date range (today, last 7 days, last 30 days, custom). | All | P0 | Free | Standard date range picker |
| Per-chatbot analytics | Each chatbot has its own separate analytics dashboard. Metrics not aggregated across bots by default. | All | P0 | Free | Filter all analytics queries by chatbot_id |
| Message credit usage tracking | Dashboard showing how many message credits have been consumed in the current billing period, broken down by model or date. | All | P0 | Free | Critical for plan management; show usage vs. limit |
| Sentiment analysis | Pro plan feature: automated analysis of conversation sentiment (positive/negative/neutral) across all chats. Shown as trend over time and per-conversation score. | Pro/Enterprise | P1 | Professional | CORE PULSE INTELLIGENCE: use LLM or VADER/RoBERTa |
| Topics analysis | Pro plan feature: automated clustering of conversations by topic/theme. Shows which subjects users are most frequently asking about. Key for knowledge base prioritization. | Pro/Enterprise | P1 | Professional | CORE PULSE INTELLIGENCE: BERTopic clustering |
| Activity tracking | Pro plan feature: overall activity dashboard combining conversation volume, credit usage, lead captures, and escalations in one view. | Pro/Enterprise | P1 | Professional | Dashboard aggregation view |
| Unanswered questions report | List of questions the bot failed to answer (fallback responses). Sourced from low-confidence retrievals. Helps identify knowledge gaps. | Hobby+ (Suggestions feature) | P1 | Starter | Link to Pulse gap detection intelligence module |
| Resolution rate tracking | NOT available in Chatbase. No metric for what % of conversations were resolved vs. escalated. | Not available | P2 | Professional | DIFFERENTIATION: Core Pulse analytics metric |
| CSAT / satisfaction rating | NOT available in Chatbase. No post-conversation customer satisfaction survey. | Not available | P2 | Professional | DIFFERENTIATION: Add thumbs up/down or 1–5 star post-chat |
| Fallback rate | NOT available in Chatbase. No metric for how often the bot falls back vs. answers successfully. | Not available | P2 | Professional | DIFFERENTIATION: Expose as primary quality metric |
| Custom dashboard | NOT available in Chatbase. No ability to create custom reports, widgets, or KPI dashboards. | Not available | P3 | Agency | Low priority v1; consider Phase 3 |
| Export conversation logs (CSV) | NOT confirmed as native feature. Conversations accessible via API. | Via API | P1 | Starter | Add CSV export to conversation log UI |
| User location map | Visual world map showing geographic distribution of chatbot users. Enhancement of chats by country data. | Not confirmed | P2 | Professional | Nice visualization; d3.js or mapbox |
| Competitive intelligence mentions | NOT available in Chatbase. Conversations not analyzed for competitor mentions. | Not available | P2 | Professional | CORE PULSE INTELLIGENCE MODULE: detect competitor mentions |

---

## Section 9: Integrations
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Zapier integration | Official Chatbase Zapier app. Allows triggering Zaps on chatbot events (new lead, new conversation, escalation). Connects to 5,000+ apps with no code. | Hobby+ | P1 | Starter | Implement Zapier trigger via webhooks; submit to Zapier marketplace |
| Make (Integromat) integration | Official Make scenario builder. Similar to Zapier but more powerful for complex multi-step workflows. | Hobby+ | P1 | Starter | Implement via webhook triggers same as Zapier |
| Zendesk integration | Native AI Action: create Zendesk tickets, enable live chat via Zendesk Sunshine. Requires Zendesk API credentials configured in Chatbase AI Actions. | All (AI Action) | P1 | Professional | Full Zendesk API integration for ticket creation + Sunshine |
| Stripe integration | Native AI Action: allows bot to answer billing questions and update payment information via Stripe API. Requires Stripe API key in AI Actions config. | All (AI Action) | P2 | Professional | Stripe API integration; handle PCI-DSS considerations |
| Calendly integration | Native AI Action: bot can check availability and book appointments directly via Calendly API. | All (AI Action) | P1 | Professional | Calendly API v2 integration |
| Cal.com integration | Native AI Action: open-source Calendly alternative for appointment booking. | All (AI Action) | P1 | Professional | Cal.com API; good for privacy-conscious users |
| Slack integration | Dual purpose: (1) Deploy bot as Slack bot for internal team Q&A; (2) AI Action to send Slack messages/notifications. | Hobby+ | P1 | Starter | Slack Events API + Bot Token |
| Tavily web search integration | Native AI Action: bot can search the web in real-time via Tavily API to answer questions about current events or information not in its knowledge base. | All (AI Action) | P2 | Professional | Tavily API integration; important for time-sensitive queries |
| WhatsApp Business integration | Deploy chatbot on WhatsApp Business via WhatsApp Business API (Meta). Users can chat with the bot on WhatsApp. | Hobby+ | P1 | Professional | Meta Business API; requires WhatsApp Business account |
| Facebook Messenger integration | Deploy chatbot on Facebook Messenger via Meta Developer API. Bot responds to Messenger conversations. | Hobby+ | P1 | Professional | Meta Messenger Platform API |
| Instagram integration | Deploy chatbot on Instagram Direct Messages via Meta API. Available as a deployment channel. | Hobby+ | P1 | Professional | Meta Instagram Messaging API |
| WordPress plugin | Official WordPress plugin for one-click embed without touching code. Available from WordPress plugin repository. | Hobby+ | P1 | Starter | Publish WP plugin; wrap JS snippet |
| Shopify integration | Embed chatbot on Shopify store. Accessible via Shopify App Store. Includes e-commerce context (order status, product questions). | Hobby+ | P1 | Professional | Shopify App Store listing + theme script inject |
| Notion (data source) | Notion used as a training data source (not a two-way integration). Connect Notion workspace, select pages to ingest. | All | P0 | Starter | OAuth with Notion API |
| Salesforce integration | Not a full CRM integration. Salesforce ticket ingestion for training (Pro+). Lead routing to Salesforce via Zapier. | Pro+ (training) / Zapier | P2 | Professional | Full Salesforce AI Action planned as Pro feature |
| HubSpot integration | NOT native. Lead routing to HubSpot via Zapier only. | Via Zapier | P2 | Professional | Native HubSpot integration is major OPPORTUNITY for Pulse |
| API (custom integrations) | Full REST API allowing custom integrations with any system. Available Hobby+. | Hobby+ | P0 | Starter | Core developer feature |
| Webhooks | Send event data (new lead, new message, escalation) to any endpoint via HTTP POST. Used for custom integrations. | Hobby+ | P1 | Starter | Implement event webhook system |

---

## Section 10: API & Developer Tools
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| REST API access | Full REST API for programmatic interaction with Chatbase. Create chatbots, manage knowledge base, send messages, retrieve conversations. Requires API key. Available Hobby+. | Hobby+ | P0 | Starter | Core developer feature; document all endpoints |
| API key management | Generate, view, revoke API keys from the dashboard. API keys authenticate all API requests. One key per account (not per-bot). | Hobby+ | P0 | Starter | Simple API key generation in settings |
| Chat endpoint (send message) | POST /api/v1/chatbot/{id}/message — Send a user message to a specific chatbot and receive the AI response. Supports conversation history via session_id. | Hobby+ | P0 | Starter | Core API endpoint |
| Create chatbot endpoint | POST /api/v1/chatbot — Create a new chatbot programmatically with name, system prompt, and initial configuration. | Hobby+ | P1 | Starter | CRUD API for chatbot management |
| Update chatbot endpoint | PATCH /api/v1/chatbot/{id} — Update chatbot configuration (system prompt, model, settings) via API. | Hobby+ | P1 | Starter | CRUD API |
| Delete chatbot endpoint | DELETE /api/v1/chatbot/{id} — Delete a chatbot and all associated data. | Hobby+ | P1 | Starter | CRUD API |
| Upload document endpoint | POST /api/v1/chatbot/{id}/data-sources — Upload a file or URL to add to the knowledge base programmatically. | Hobby+ | P1 | Starter | Multipart file upload or URL submission via API |
| Delete data source endpoint | DELETE /api/v1/chatbot/{id}/data-sources/{source_id} — Remove a specific data source. | Hobby+ | P1 | Starter | CRUD API |
| Get conversation logs endpoint | GET /api/v1/chatbot/{id}/conversations — Retrieve conversation history with pagination and date filters. | Hobby+ | P1 | Starter | Expose conversation data via API |
| Get leads endpoint | GET /api/v1/chatbot/{id}/leads — Retrieve collected leads as JSON array. Supports pagination. | Hobby+ | P1 | Starter | Lead data API access |
| Streaming support | The chat API supports streaming responses via SSE (Server-Sent Events), returning tokens as they are generated rather than waiting for completion. | Hobby+ | P0 | Starter | Critical for good UX in API-mode deployments |
| API rate limits | Rate limiting applied per API key. Specific limits not publicly documented; varies by plan. Overage results in 429 errors. | Plan-dependent | P1 | Starter | Implement rate limiter (e.g., 60 req/min Starter, 300 req/min Pro) |
| SDKs / client libraries | No official SDKs confirmed for Chatbase. API used directly via HTTP. | Not confirmed | P2 | Professional | DIFFERENTIATION: Publish Python + JS SDKs |
| API documentation | Chatbase API documented at chatbase.co/docs/developer-guides/api-integration. Covers auth, endpoints, request/response formats, examples. | Hobby+ | P0 | Free | Good docs = lower support burden |
| Webhook event system | Subscribe to events (new_message, new_lead, escalation, low_confidence) and receive POST notifications to a URL. | Hobby+ | P1 | Starter | Event-driven integration pattern |

---

## Section 11: Deployment Channels
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Website embed (JS snippet) | Deploy via JavaScript snippet added to website <head> or before </body>. Minimal performance impact, works with any website builder. | All | P0 | Free | Primary deployment method |
| Website embed (iFrame) | Deploy via iframe embed for platforms that don't allow script injection. Full isolation from parent page styles. | All | P0 | Free | Secondary embed method |
| Shareable public link | Each chatbot gets a unique hosted URL (chatbase.co/chatbot/{id}) for sharing without embedding. Opens full-screen chat interface in browser. | All | P0 | Free | Hosted route for each bot |
| Custom domain (shareable link) | Replace the chatbase.co/chatbot/{id} URL with a custom domain (e.g., chat.yourcompany.com). Add-on at $59/month. | Add-on ($59/mo) | P2 | Professional | Custom subdomain mapping via DNS CNAME |
| Slack bot deployment | Deploy chatbot as a Slack bot in a workspace. Team members interact with the bot directly in Slack channels or DMs. | Hobby+ | P1 | Starter | Slack Events API + Slash commands |
| WhatsApp Business deployment | Deploy chatbot on WhatsApp Business. End users send messages to a WhatsApp Business number and receive bot responses. | Hobby+ | P1 | Professional | Meta WhatsApp Business API; requires business phone number |
| Facebook Messenger deployment | Deploy chatbot on a Facebook Business Page Messenger. Users send messages to the Page inbox and receive bot responses. | Hobby+ | P1 | Professional | Meta Messenger Platform |
| Instagram Direct deployment | Deploy chatbot to respond to Instagram Direct Messages sent to a business Instagram account. | Hobby+ | P1 | Professional | Meta Instagram Messaging API |
| API-only mode | Use Chatbase purely via API without any visual widget. Allows developers to build completely custom front-end chat interfaces while using Chatbase as the AI backend. | Hobby+ | P1 | Starter | Position for developer/headless use cases |
| WordPress deployment | Dedicated WordPress plugin for one-click installation. No code required. Adds chatbot to all pages or specific pages. | Hobby+ | P1 | Starter | WP plugin repo submission |
| Shopify deployment | Shopify App Store app for adding chatbot to Shopify storefronts. Handles theme injection automatically. | Hobby+ | P1 | Professional | Shopify Partner Program required |
| Phone / SMS channel | NOT available in Chatbase. No phone or SMS deployment channel. | Not available | P3 | Enterprise | OPPORTUNITY: Twilio integration for SMS |
| Email channel | NOT available in Chatbase. No email-based bot responses. | Not available | P3 | Enterprise | Complex; low priority |

---

## Section 12: Customization & Branding
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Chatbot display name | Set the name shown in the widget header (e.g., "Support Bot", "Aria", "Ask Acme"). Separate from the account-level bot name. | All | P0 | Free | Simple text field in widget config |
| Avatar image upload | Upload a custom square image (PNG/JPG) to use as the chatbot avatar in the widget header and message bubbles. Recommended: 64x64px or higher. | All | P0 | Free | Image upload to CDN |
| Primary / accent color | Main color used for the chat bubble launcher, send button, and user message backgrounds. Hex code input or color picker. | All | P0 | Free | CSS variable: --primary-color |
| Bot message text color | Set the text color for bot responses. Important for accessibility (contrast ratio). | All | P0 | Free | CSS variable |
| Widget border radius | Control the roundness of the widget corners. Ranges from sharp (0px) to fully rounded. | Not confirmed | P2 | Professional | CSS variable: --border-radius |
| Initial greeting message | The first message the bot sends when the widget is opened. Customizable per-chatbot. Supports emojis and basic formatting. | All | P0 | Free | Displayed as first message in thread on open |
| Input placeholder text | Customize the placeholder text inside the message text area. Default: "Ask a question...". | All | P0 | Free | Placeholder attribute config |
| Footer text / attribution | Default: "Powered by Chatbase". Removed via $39/month add-on. Cannot customize to a different text (only remove). | All | P0 | Free | Remove for Pulse Starter+; allow custom footer text on Professional |
| Custom domain for hosted chat | Map your own domain (e.g., chat.acme.com) to the Chatbase-hosted shareable chat URL. Requires DNS CNAME setup. Add-on $59/month. | Add-on ($59/mo) | P2 | Professional | DNS CNAME pointing to Pulse infrastructure |
| Remove Chatbase branding | Paid add-on ($39/mo) to remove the "Powered by Chatbase" footer. Not included in any subscription tier — must be purchased separately even on Pro ($500/mo). | Add-on ($39/mo) | P1 | Starter | MAJOR PULSE ADVANTAGE: Include in Starter ($49/mo) |
| Custom CSS injection | NOT confirmed in Chatbase. No ability to inject custom CSS to fully restyle the widget. | Not available | P2 | Professional | Add as Professional feature; expose CSS variable overrides |
| White-label (full branding removal) | No Chatbase branding anywhere in the widget, hosted chat, or shareable links. Only achievable via custom domain + branding removal add-ons combined. Total add-on cost: $98/month on top of subscription. | Add-on ($39+$59/mo) | P1 | Agency | Include in Agency tier: full white-label as standard |
| Chatbot personality presets | NOT confirmed in Chatbase. No pre-built personality templates. Users define everything via system prompt. | Not available | P1 | Starter | DIFFERENTIATION: Add 10+ industry-specific personality templates |

---

## Section 13: Multi-Language Support
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Auto-detect visitor language | Bot automatically detects the language of the user message and responds in the same language. No configuration required. Works because LLMs are multilingual by nature. | All | P0 | Free | LLMs inherently multilingual; add "respond in user language" to system prompt |
| 80+ languages supported | Chatbase marketing claims support for 80+ languages. Quality varies significantly by language — works best for English, Spanish, French, German, Portuguese, Italian, Dutch, Japanese, Korean, Chinese. | All | P1 | Free | Dependent on underlying LLM language support |
| Respond in visitor language | When auto-detect is enabled, the bot responds in whatever language the user writes in, even if the knowledge base is entirely in English. | All | P0 | Free | Built-in LLM behavior; document clearly |
| Force specific language | Override auto-detect and force the bot to always respond in a configured language (e.g., always reply in English regardless of user input language). | All | P1 | Starter | Inject "Always respond in [language]" into system prompt |
| Interface language (widget) | The widget UI text (placeholder, buttons, header) language. In Chatbase, the interface defaults to English and does not localize widget chrome. | Not confirmed | P2 | Professional | DIFFERENTIATION: Localize widget UI strings for top 10 languages |
| Multi-language knowledge base | Knowledge base can contain documents in multiple languages. RAG retrieves the most relevant chunks regardless of language. | All | P1 | Starter | Works naturally with multilingual embeddings |
| Language quality note | Chatbase multi-language identified as a weakness in user reviews — responses in non-English languages are less accurate and sometimes mix languages. Quality gap vs. native-language competitors. | All | P2 | Professional | OPPORTUNITY: Use Gemini models (stronger multilingual) as default for non-English |

---

## Section 14: Team & Workspace
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Single user account (Free/Hobby) | Free and Hobby plans limited to 1 user (account owner only). No ability to add team members. | Free/Hobby | P0 | Free | Single-user mode as default |
| Team seats — Standard plan | Standard plan includes 3 human agent seats. Seats can view conversation logs and manage chatbot settings. | Standard | P1 | Professional | Invite-by-email system; simple role assignment |
| Team seats — Pro plan | Pro plan includes 5 team member seats. Additional seats available at $25/seat/month. | Pro | P1 | Professional | Per-seat overage billing |
| Team seat add-on | Additional team seats purchasable at $25/seat/month on Pro plan. | Pro add-on | P2 | Professional | Per-seat billing |
| Role: Owner | Account owner has full access: billing, all chatbots, all settings, user management, API keys. | All | P1 | Starter | Standard role system |
| Role: Admin | NOT confirmed in Chatbase. No documented admin vs. member role distinction. | Not confirmed | P2 | Professional | OPPORTUNITY: Add granular RBAC |
| Role: Member / Agent | Team members can view conversations and leads but may have limited settings access. Specific permissions not documented. | Standard/Pro | P1 | Professional | Define clear permission matrix |
| Chatbot sharing between members | All team members can access all chatbots within the account. No per-chatbot access restriction. | Standard/Pro | P1 | Professional | Account-level access model |
| Shared inbox / live chat (team) | NOT available in Chatbase. No shared team inbox for handling escalated conversations. | Not available | P2 | Professional | MAJOR PULSE DIFFERENTIATOR: Build native shared inbox |
| Role-based access control (RBAC) | NOT confirmed in Chatbase. No granular permission settings per role or per chatbot. | Not available | P3 | Enterprise | Add in Enterprise tier |
| Workspace concept | Single workspace per account. No multi-workspace or client isolation within one account. | All | P2 | Agency | OPPORTUNITY: Multi-workspace for Agency tier |

---

## Section 15: White-Label & Agency
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Branding removal from widget | Remove "Powered by Chatbase" from widget footer. Purchased as $39/month add-on. NOT included in any plan by default — even the $500/month Pro plan shows Chatbase branding unless add-on purchased. | Add-on ($39/mo) | P1 | Starter | PULSE ADVANTAGE: Include in Starter; make branding removal default on paid plans |
| Custom domain for chat interface | Replace chatbase.co/chatbot/{id} URL with your own domain. Add-on at $59/month. Requires DNS setup. | Add-on ($59/mo) | P2 | Professional | DNS CNAME routing |
| No agency dashboard | NOT available. Chatbase has no dedicated agency mode, no client management interface, no client-separate billing. Major gap for agency use case. | Not available | P2 | Agency | MAJOR DIFFERENTIATION: Build agency dashboard with client sub-accounts |
| No client management | Agency users cannot manage separate client accounts from one dashboard. Must create separate Chatbase accounts per client. Significant friction. | Not available | P2 | Agency | Multi-workspace feature addresses this |
| No reseller features | No white-label reseller program, no margin on client seats, no branded billing portal. | Not available | P3 | Agency | Phase 3 feature |
| No client-facing reports | No ability to generate branded PDF/web reports for clients showing chatbot performance. | Not available | P3 | Agency | Add branded report export in Agency tier |

---

## Section 16: Voice Features
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Voice agent mode | Chatbase has referenced voice agent capability in marketing materials ("voice agent" mentioned in earlier product descriptions). Current UI reviews suggest text-only interface with no confirmed voice widget. Status: likely in beta or limited rollout. | Uncertain/Beta | P3 | Enterprise | MONITOR: Voice AI growing rapidly; may be confirmed feature by 2026 |
| Text-to-speech (TTS) | Convert bot text responses to audio output. NOT confirmed as current Chatbase feature. | Not confirmed | P3 | Enterprise | ElevenLabs or OpenAI TTS API integration |
| Speech-to-text (STT) | Allow users to speak instead of type. NOT confirmed as current Chatbase feature. | Not confirmed | P3 | Enterprise | Whisper API or Web Speech API |
| Voice-specific settings | NOT confirmed in Chatbase. No voice persona, speed, or pitch settings available. | Not confirmed | P3 | Enterprise | Low priority v1 |
| Phone call handling | NOT available. No phone number, IVR replacement, or call routing. | Not available | SKIP | — | Out of scope for v1 |

---

## Section 17: Agentic / Function Calling
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| AI Actions framework | The core agentic capability in Chatbase: define discrete actions the bot can take (call an API, create a ticket, book an appointment) triggered by conversation context. Each action has a name, description, and API endpoint. | All | P1 | Professional | Implement as Tool/Function Calling via OpenAI function calling API |
| AI Action limit per chatbot | Number of AI Actions configurable per chatbot: 0 (Free), 5 (Hobby), 10 (Standard), 15 (Pro). | Plan-gated | P1 | Professional | Implement action limit per bot tied to plan |
| Built-in Calendly action | Pre-built AI Action: bot checks Calendly availability and books appointments. User configures Calendly API key and event type. No code required. | All (AI Action) | P1 | Professional | Calendly API v2 endpoint integration |
| Built-in Cal.com action | Pre-built AI Action: same as Calendly but using Cal.com (open source alternative). | All (AI Action) | P1 | Professional | Cal.com API integration |
| Built-in Stripe action | Pre-built AI Action: bot retrieves billing information and can update payment details via Stripe API. Useful for SaaS billing self-service. | All (AI Action) | P2 | Professional | Stripe API; careful with PCI scope |
| Built-in Zendesk action | Pre-built AI Action: creates Zendesk support tickets from conversations and initiates Zendesk Sunshine live chat handoff. | All (AI Action) | P1 | Professional | Zendesk API integration |
| Built-in Slack action | Pre-built AI Action: sends a Slack message to a specified channel. Used for internal notifications (e.g., new lead alert, escalation notice). | All (AI Action) | P1 | Starter | Slack Incoming Webhooks or Bot API |
| Built-in Tavily web search action | Pre-built AI Action: bot can query the live web via Tavily search API to answer questions about current events or information not in its knowledge base. | All (AI Action) | P2 | Professional | Tavily API integration |
| Custom API action | Define a custom AI Action that calls any external REST API endpoint with configurable parameters. Allows integration with proprietary systems (e.g., order lookup, account status). | Hobby+ | P1 | Professional | Core of the agentic framework; implement JSON schema for action definition |
| Action configuration UI | Dashboard UI for defining AI Actions: action name, description (used by LLM to decide when to trigger), API endpoint URL, HTTP method, headers, body parameters. | Hobby+ | P1 | Professional | Form-based action builder in dashboard |
| Action trigger via LLM reasoning | The LLM autonomously decides which action to call based on conversation context and action descriptions. Uses OpenAI function calling or tool use API pattern. | Hobby+ | P1 | Professional | Standard OpenAI tools/function calling implementation |
| Logged-in user personalization | Feature confirmed in RSC data: bot can identify logged-in users and retrieve their personal information (account details, history) from connected systems. Enables personalized responses. | Pro/Enterprise | P2 | Professional | Requires user authentication token passing to chatbot session |
| Action execution logging | Log all AI Action calls (which action, parameters used, response, timestamp) for debugging and audit. | Not confirmed | P2 | Professional | Critical for debugging agentic behavior |

---

## Section 18: Security & Compliance
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| SOC 2 Type II certification | Chatbase is SOC 2 Type II certified (confirmed). Covers security, availability, confidentiality controls. Audited annually. | All | P2 | Professional | Target for Phase 3; required for mid-market enterprise sales |
| GDPR compliance | Chatbase is GDPR compliant. Data processing agreements (DPA) available. EU customer data handled per GDPR requirements. Documented at trust.chatbase.co. | All | P1 | Starter | Implement cookie consent, data deletion request flow, DPA template |
| Data not used for model training | Chatbase explicitly does not use customer data (training documents or conversation logs) to train any public AI models. Key privacy guarantee. | All | P0 | Free | Make this a prominent marketing claim |
| Data encryption at rest | Customer training data and conversation logs encrypted at rest using AES-256 or equivalent. | All | P0 | Free | Standard database + storage encryption |
| Data encryption in transit | All data in transit encrypted via TLS 1.2+. Enforced on all API endpoints and widget communications. | All | P0 | Free | Standard HTTPS/TLS configuration |
| Allowed domains (iframe restriction) | Whitelist of domains permitted to embed the chatbot via iframe or JS snippet. Prevents unauthorized use of embed code. | All | P1 | Starter | Referer header check on widget load |
| API key authentication | All API requests authenticated via API key passed in Authorization header. Keys can be revoked instantly. | Hobby+ | P0 | Starter | Standard API key auth |
| IP restriction / rate limiting | Per-session rate limiting to prevent abuse (e.g., 60 messages/hour per IP). Not confirmed as user-configurable in Chatbase. | Not confirmed (internal) | P1 | Starter | Implement as configurable rate limit per chatbot |
| SLA guarantees | Service Level Agreements for uptime and response time. Enterprise plan only. | Enterprise | P3 | Enterprise | 99.9% uptime SLA target |
| HIPAA compliance | NOT confirmed for Chatbase. Not marketed as HIPAA-compliant. | Not confirmed | P3 | Enterprise | OPPORTUNITY: Differentiate for healthcare use cases |
| Data deletion (GDPR right to erasure) | Ability to permanently delete all conversation data and training data for a specific user or account. GDPR right-to-erasure compliance. | All | P1 | Starter | Admin data deletion endpoint |
| Trust center | Chatbase maintains a trust center at trust.chatbase.co with security documentation, certifications, and privacy information. | All | P2 | Professional | Build trust.pulse.co equivalent |
| Enterprise security controls | SSO, SAML, audit logs, IP allowlisting — mentioned for Enterprise plan but specific features not fully documented. | Enterprise | P3 | Enterprise | Standard enterprise security package |

---

## Section 19: Pricing, Limits & Add-ons
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Free plan — $0/month | 1 chatbot, 100 message credits/month, 400,000 character training limit (~400KB), 10 training links max, 1 team member, basic models only (GPT-4o Mini), chatbot deleted after 14 days inactivity. | Free | P0 | Free | Competitive lead gen tool; generous enough to experience value |
| Hobby plan — $40/month | 1 chatbot, 2,000 message credits/month, 11M character limit (~33MB), unlimited training links, 5 AI Actions/chatbot, API access, all integrations, 2 team members. | Hobby | P0 | Starter | Good for solopreneurs; steep at 1 chatbot limit |
| Standard plan — $150/month | 2 chatbots, 12,000 message credits/month, 11M character limit, 10 AI Actions/chatbot, 3 team seats, all integrations. | Standard | P0 | Professional | Primary SMB tier; $150 is mid-market |
| Pro plan — $500/month | 3 chatbots, 40,000 message credits/month, 11M character limit, 15 AI Actions/chatbot, 5 team seats (+$25/seat), advanced analytics (sentiment, topics, activity). | Pro | P0 | Agency | Expensive for only 3 chatbots; opportunity for Pulse |
| Enterprise plan — Custom pricing | Custom chatbot count, custom credits, custom storage, priority support with SLA, dedicated success manager, custom security requirements. | Enterprise | P3 | Enterprise | Direct sales motion; requires custom contract |
| Annual discount — 20% | All paid plans available at 20% discount when billed annually instead of monthly. | All paid | P0 | All | Standard SaaS annual discount |
| Message credit system | Credits are consumed per LLM response. Credit cost varies by model: premium models cost more credits. Free plan: 100 credits/mo. Credits reset monthly. | All | P0 | Free | Core billing mechanism |
| Credit auto-recharge | Purchase auto-recharge credit packs ($14/1,000 credits) that automatically refill when the monthly credit pool is exhausted. Prevents bot downtime. | Add-on | P1 | Starter | Stripe payment + automatic credit refill trigger |
| Extra message credits add-on | Purchase additional monthly credits: $12 per 1,000 credits/month, on top of base plan allocation. | Add-on | P1 | Starter | Usage-based billing component |
| Extra chatbot add-on | Add an additional chatbot beyond the plan limit: $7/chatbot/month. Applied per chatbot. | Add-on | P1 | Starter | Per-unit add-on billing |
| Custom domain add-on | Add a custom domain for the shareable chat link: $59/month. Requires customer to set DNS CNAME. | Add-on | P2 | Professional | DNS-based feature |
| Remove Chatbase branding add-on | Remove "Powered by Chatbase" footer: $39/month. Applies to all chatbots in the account. Not included in any plan. | Add-on | P1 | Starter | PULSE ADVANTAGE: Include in Starter base plan |
| Extra team seat add-on | Additional team seats beyond plan limit: $25/seat/month. Pro plan only. | Pro add-on | P2 | Professional | Per-seat billing |
| Overage handling | When monthly message credits are exhausted, bot stops responding unless auto-recharge is enabled. No automatic overage billing. | All | P0 | Free | Implement credit exhaustion handling + notification |
| Refund policy | NOT confirmed in Chatbase public documentation. | Unknown | P2 | All | Implement 14-day money-back guarantee as standard |

---

## Section 20: Onboarding & UX Flows
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Email/password signup | Standard email + password account creation. Google OAuth also available. No credit card required for free tier. | All | P0 | Free | Standard auth flow |
| Google OAuth login | Sign up and log in with Google account. Faster onboarding, reduces password friction. | All | P0 | Free | NextAuth.js or Supabase Auth |
| No credit card required (Free) | Free plan accessible without credit card. Reduces signup friction for evaluation. | Free | P0 | Free | Critical for top-of-funnel conversion |
| First chatbot creation wizard | After signup, user is immediately guided through creating their first chatbot: name it, upload a data source, configure basic settings, deploy. Designed to complete in under 5 minutes. | All | P0 | Free | Interactive wizard with progress steps |
| Data source upload step | Step 2 of wizard: upload first data source (file or URL). Shows character count after processing. | All | P0 | Free | Core wizard step |
| Test chat step | After creating the chatbot, user is presented with the test chat interface to try their bot before deploying. | All | P0 | Free | Live chat window in dashboard |
| Deploy / embed step | Final wizard step: shows the embed code snippet and integration options for deploying the bot. | All | P0 | Free | Code display with copy button |
| Live in under 10 minutes | Chatbase markets this as the primary time-to-value claim. From signup to live chatbot on website in under 10 minutes with no coding. | All | P0 | Free | Core competitive claim to match or beat |
| Dashboard home / overview | Landing page after login: shows list of chatbots with key stats (message count, leads), quick actions, plan usage overview. | All | P0 | Free | Standard dashboard home |
| Chatbot settings navigation | In-dashboard navigation per chatbot: tabs for Knowledge Base, Settings, Appearance, Integrations, Analytics, Leads. | All | P0 | Free | Tab-based navigation per bot |
| Plan usage indicator | Dashboard element showing current message credit usage (X of Y credits used this month). Visual progress bar. | All | P0 | Free | Progress bar with upgrade CTA |
| Upgrade CTA / upsell prompts | When approaching plan limits, in-app prompts to upgrade plan with clear value messaging. | All | P0 | Free | Triggered by credit usage ≥80% |
| Demo chatbot (pre-trained) | NOT confirmed in Chatbase. No sandbox demo bot for evaluation without creating an account. | Not confirmed | P1 | Free | DIFFERENTIATION: Add public demo bot on marketing site |

---

## Section 21: Notifications & Alerts
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Credit exhaustion notification | Alert (email or in-app) when monthly message credits are running low (e.g., at 80% and 100% usage). Prevents surprise bot downtime. | All | P0 | Free | Email trigger on credit threshold |
| Negative sentiment alert | Pro plan: when a conversation is detected as highly negative sentiment, an alert can be triggered for human review or escalation. | Pro/Enterprise | P2 | Professional | Sentiment threshold trigger + Slack/email notification |
| New lead notification | Email notification to account owner when a new lead (name/email/phone) is captured via the lead form. NOT confirmed in Chatbase — users set this up via Zapier. | Via Zapier | P1 | Starter | DIFFERENTIATION: Include native email notification on lead capture |
| Escalation notification | When the bot escalates a conversation to a human agent, an alert is sent via email or Slack. NOT native in Chatbase. | Via Zapier/Zendesk | P1 | Professional | Native notification on escalation trigger |
| In-app notification bell | NOT confirmed in Chatbase. No in-app notification center for alerts. | Not confirmed | P2 | Professional | Standard notification bell UI pattern |
| Daily/weekly summary emails | NOT confirmed in Chatbase. No scheduled digest emails with chatbot performance summary. | Not confirmed | P2 | Professional | DIFFERENTIATION: Weekly summary email with top metrics |
| Downtime / error alerts | NOT confirmed in Chatbase. No alerting when a chatbot integration breaks or errors spike. | Not confirmed | P2 | Professional | Monitor integration health + alert on errors |

---

## Section 22: Data Management & Export
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| Conversation log access (in-app) | View all conversations via the Chat Logs section. Shows each session with full message thread, timestamp, and user identifier. Available on all plans. | All | P0 | Free | Database-backed conversation viewer with pagination |
| Conversation export (CSV) | Export conversation logs as CSV file. NOT confirmed as native Chatbase feature — accessible via API. | Via API | P1 | Starter | Standard data export button |
| Conversation export (JSON) | Export via API in JSON format. Available to developers via the conversations API endpoint. | Via API (Hobby+) | P1 | Starter | REST API returns JSON; add export endpoint |
| Lead export (CSV) | Export all captured leads (name, email, phone, timestamp) as CSV from Leads overview. | Not confirmed natively (Via Zapier/API) | P1 | Starter | Essential feature for marketing/sales use |
| Knowledge base export | Export training data sources list and content. NOT confirmed in Chatbase. | Not confirmed | P2 | Professional | Allow users to download their own data |
| GDPR data deletion request | User-triggered deletion of all personal data associated with a specific visitor/session. Compliance with GDPR right to erasure. | All (compliance) | P1 | Starter | Admin endpoint + documented process |
| Data retention settings | Configure how long conversation logs are retained before automatic deletion. NOT confirmed in Chatbase. | Not confirmed | P2 | Professional | Configurable retention policy per account |
| Account data export (full) | Export all account data: chatbots, conversations, leads, knowledge base sources. GDPR portability right. | Not confirmed | P2 | Professional | Full account data export package |
| Data storage location | Chatbase stores data on US-based servers (assumed AWS). EU data residency NOT confirmed. | Not confirmed (US) | P3 | Enterprise | OPPORTUNITY: EU data residency option for GDPR-strict enterprises |

---

## Section 23: Changelog / Recently Added Features
| Feature | Description | Chatbase Plan | Pulse Priority | Pulse Tier | Notes |
|---------|-------------|---------------|----------------|------------|-------|
| AI Actions framework launch | Major feature launch: configurable AI Actions replacing simple integrations. Allows bot to take real actions (book meetings, create tickets, process billing). Launched mid-2024. | All | P1 | Professional | Core agentic direction; match as table-stakes |
| Next-gen model support (GPT-5.x, Claude 4.x, Gemini 3.x) | Continuous addition of latest LLM models as they launch. Chatbase adds major models within weeks of release. 2026 RSC confirms: GPT-5.1, GPT-5.2, Claude 4.6, Gemini 3.1 Pro, DeepSeek-R1, Llama 4, Kimi K2. | Plan-gated | P1 | Professional | Model-agnostic architecture enables rapid model additions |
| Zendesk & Salesforce ticket ingestion (training) | Added ability to ingest historical support tickets from Zendesk and Salesforce as training data. Pro/Enterprise. Added 2024–2025. | Pro/Enterprise | P2 | Professional | High-value data source for support bot quality |
| Detect content gaps / conflicting sources | Automated knowledge base quality analysis features added. Identifies gaps and contradictions in training data. | Pro/Enterprise | P1 | Professional | Align with Pulse gap detection intelligence module |
| Sentiment analysis & topic analysis | Advanced analytics features added to Pro plan. Real-time sentiment scoring and topic clustering across conversations. | Pro | P1 | Professional | Core Pulse intelligence layer; build more deeply |
| Logged-in user personalization | Ability for bot to identify authenticated users and retrieve their personal data for personalized responses. Added as Pro feature. | Pro/Enterprise | P2 | Professional | Requires auth token integration from customer app |
| Instagram channel deployment | Added Instagram Direct Messages as a deployment channel. Expands from Facebook Messenger to include Instagram. | Hobby+ | P1 | Professional | Meta API expansion |
| Auto-recharge credits | Added credit auto-recharge add-on to prevent credit exhaustion bot downtime. | Add-on | P1 | Starter | Simple billing mechanism |
| Rebrand: Unlimited → Pro | Plan renamed from "Unlimited" to "Pro" and repriced from $399 to $500/month. Pricing increased significantly across all tiers (Free 20→100 credits, Hobby $19→$40, Standard $99→$150). | 2025–2026 | — | — | Chatbase has SIGNIFICANTLY raised prices; creates opening for Pulse |
| Pricing increase (all tiers) | All Chatbase plans repriced upward: Free (was 20 credits → now 100), Hobby ($19→$40), Standard ($99→$150), Unlimited/Pro ($399→$500). Large price increase creates market opening. | 2025–2026 | — | — | MAJOR OPPORTUNITY: Pulse Starter at $49 vs Chatbase Hobby at $40 (similar price, significantly more features) |

---

## Notable Feature Gaps (Missing from Chatbase — Differentiation Opportunities for Pulse)
| Missing Feature | Why It Matters | Pulse Priority | Notes |
|----------------|----------------|----------------|-------|
| BYOAK (Bring Your Own API Key) | #1 user complaint industry-wide. Power users want to use their own OpenAI/Anthropic keys to control costs and access latest models immediately. | P1 | Build as Starter+ feature: charge platform fee, user provides API key |
| Visual flow builder / conversation designer | No ability to create conditional conversation paths, decision trees, or multi-step guided flows. Competes with Botpress, Voiceflow. | P2 | Add in Phase 3 using React Flow canvas |
| Built-in live chat / shared inbox | Chatbase has NO native human agent interface. Requires Zendesk integration. Massive gap for teams wanting one tool. | P2 | Core Pulse differentiator: native shared inbox |
| Templates library | No pre-built chatbot templates for common use cases (e-commerce, SaaS support, lead gen, healthcare). Zero templates. | P1 | Build 15+ templates at launch; lowers time-to-value |
| Google Drive / SharePoint connector | No ability to ingest docs from Google Drive, SharePoint, Confluence, Dropbox. Only Notion supported. | P2 | Add as Professional feature; major enterprise data source |
| Confluence / Notion-like connectors | Limited to Notion. No Confluence, Coda, GitBook, or other documentation platforms. | P2 | Connectors for top documentation platforms |
| Proactive messaging (triggered outbound) | Cannot send proactive messages to website visitors based on page URL, behavior, or time on page. Text-based reactive only. | P2 | Behavioral trigger system for proactive chat |
| CSAT / satisfaction score | No post-conversation customer satisfaction survey or rating. No way to measure resolution quality from user perspective. | P2 | 1-click thumbs up/down + optional NPS post-chat |
| Custom dashboard / reporting | No ability to build custom KPI dashboards or scheduled reports. Basic fixed metrics only. | P3 | Phase 3 feature |
| Multi-workspace (agency isolation) | No way to manage multiple clients under one account with proper isolation. Agency users must create separate accounts. | P2 | Core Agency tier feature |
| Native HubSpot / Salesforce CRM integration | No native CRM integration. Lead routing requires Zapier. Heavy-friction for CRM-centric sales teams. | P2 | Native HubSpot integration as Professional feature |
| A/B testing for bot responses | No ability to test different system prompts, models, or knowledge base versions against each other. | P3 | Phase 3 intelligence feature |
| Conversation tagging / labeling | No way to manually tag or label conversations (e.g., "billing issue", "bug report"). | P2 | Add taxonomy system for conversation management |
| Phone / SMS channel | No telephone or SMS deployment option. | P3 | Twilio integration as Enterprise feature |
| EU data residency | No confirmed EU data residency option. Problematic for GDPR-strict EU enterprises. | P3 | AWS eu-west infrastructure option |
| HIPAA compliance | Not marketed as HIPAA-compliant. Healthcare chatbot use cases blocked. | P3 | Business Associate Agreement + HIPAA controls |
