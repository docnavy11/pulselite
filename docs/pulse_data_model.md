# 🗄️ Pulse — Validated Data Model
## Based on live API research: Intercom, Chatwoot, Chatbase, Crisp, Zendesk
### Version 1.0 — March 2026

> **Status:** Engineering-ready schema reference
> **Sources:** Intercom API docs (developers.intercom.com), Chatwoot db/schema.rb (GitHub), Chatbase docs, Crisp API, Zendesk API
> **Full research:** /a0/usr/workdir/data_model_research.md

---

## 0. Key Findings vs. Prior Assumptions

The following assumptions in our earlier data model were WRONG or incomplete — corrected here:

| Prior Assumption | Reality (from research) | Impact on Pulse |
|---|---|---|
| Conversation status: open/closed/resolved | **Intercom**: open/closed/snoozed (NOT resolved) | Intercom compat layer must use snoozed, not resolved |
| Message role: user/assistant | **Intercom** part_type: comment/note/assignment/close/open/snooze/transfer | author_type field is richer than expected |
| lifecycle_stage as a REST API field | **NOT in Intercom REST API** — internal UI only | Cannot rely on this field in compat layer |
| Simple article → collection hierarchy | **Intercom**: collection → section → article (3 levels) | Need parent_type + parent_id on articles |
| Agent has a role field | **Intercom Admin**: no role in REST API, only has_inbox_seat bool | Simplify agent model |
| Tags are simple string labels | **Intercom**: applied_by audit object (who + when) | Add applied_by to tags junction table |
| Ticket = Conversation variant | **Intercom**: Ticket is a SEPARATE entity with own state machine | Pulse needs a Ticket model separate from Conversation |
| Custom attributes as jsonb blob | **Intercom**: pre-declared via Data Attributes API, typed | Need DataAttribute schema table |
| Events are nested objects | **Intercom**: flat metadata ONLY — no nested objects | Events table must enforce flat structure |

---

## 1. Core Entities — Organizational

### 1.1 workspaces
```sql
CREATE TABLE workspaces (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  TEXT NOT NULL,
  slug                  TEXT UNIQUE NOT NULL,          -- subdomain / URL slug
  plan                  TEXT DEFAULT 'free',           -- free | starter | professional | agency | enterprise
  plan_conversation_cap INTEGER DEFAULT 100,
  timezone              TEXT DEFAULT 'UTC',
  primary_language      TEXT DEFAULT 'en',
  intercom_app_id       TEXT,                          -- for compat layer: their Intercom app ID
  webhook_secret        TEXT,                          -- HMAC-SHA1 secret (Intercom uses SHA1, not SHA256!)
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.2 agents (= Intercom Admin = Chatwoot User)
```sql
CREATE TABLE agents (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  email                 TEXT NOT NULL,
  name                  TEXT NOT NULL,
  display_name          TEXT,
  avatar_url            TEXT,
  has_inbox_seat        BOOLEAN DEFAULT TRUE,          -- Intercom: has_inbox_seat (not a role field)
  availability          TEXT DEFAULT 'online',        -- online | offline | busy (Chatwoot pattern)
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, email)
);
```

### 1.3 teams
```sql
CREATE TABLE teams (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE team_members (
  team_id               UUID NOT NULL REFERENCES teams(id),
  agent_id              UUID NOT NULL REFERENCES agents(id),
  priority_level        INTEGER DEFAULT 1,            -- Intercom: admin_priority_level per member
  PRIMARY KEY (team_id, agent_id)
);
```

### 1.4 inboxes (= Chatwoot Inbox = Intercom implicit channel)
```sql
CREATE TABLE inboxes (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  channel_type          TEXT DEFAULT 'web_widget',
  -- channel_type enum: web_widget | api | email | whatsapp | slack | telegram | sms
  -- (Chatwoot supports 11 types; we start with 3: web_widget | api | email)
  channel_config        JSONB DEFAULT '{}',           -- channel-specific config
  is_inbox_seat_required BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 2. Contact & Identity Model

### 2.1 contacts (= Intercom Contact = Chatwoot Contact)
```sql
CREATE TABLE contacts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),

  -- Identity
  email                 TEXT,
  phone                 TEXT,
  name                  TEXT,
  avatar_url            TEXT,

  -- Role/Type
  -- Intercom: role = 'user' | 'lead'
  -- Chatwoot: contact_type = visitor(0) | lead(1) | customer(2)
  -- Pulse unifies both:
  contact_type          TEXT DEFAULT 'visitor',
  -- contact_type enum: visitor | lead | customer

  -- Lifecycle (NOT a REST API field in Intercom — derived internally)
  lifecycle_stage       TEXT DEFAULT 'unknown',
  -- lifecycle_stage enum: unknown | presales | trial | active | churned

  -- External IDs for integrations
  intercom_id           TEXT,                         -- Intercom contact ID for compat
  crm_contact_id        TEXT,                         -- HubSpot / Salesforce ID
  external_id           TEXT,                         -- product DB user ID

  -- Enrichment
  company_id            UUID REFERENCES companies(id),
  location              TEXT,
  browser               TEXT,
  os                    TEXT,
  last_seen_at          TIMESTAMPTZ,
  signed_up_at          TIMESTAMPTZ,
  last_contacted_at     TIMESTAMPTZ,

  -- AI-native additions
  lead_score            INTEGER DEFAULT 0,            -- 0-100, updated by Lead Intelligence module
  lead_tier             TEXT,                         -- hot | warm | cold
  churn_risk            TEXT,                         -- low | medium | high
  expansion_potential   TEXT,                         -- low | medium | high

  -- Custom attributes (typed, Intercom-compatible)
  custom_attributes     JSONB DEFAULT '{}',

  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(workspace_id, email),
  UNIQUE(workspace_id, intercom_id)
);
```

### 2.2 companies
```sql
CREATE TABLE companies (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  domain                TEXT,
  industry              TEXT,
  company_size          INTEGER,
  monthly_spend         NUMERIC(12,2),
  plan                  TEXT,                         -- their pricing plan (nested object in Intercom)
  intercom_id           TEXT,                         -- Intercom company ID
  external_id           TEXT,
  custom_attributes     JSONB DEFAULT '{}',
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Intercom uses silent UPSERT on POST /companies (no 409 on duplicate)
-- Pulse replicates this: upsert on (workspace_id, external_id) or (workspace_id, domain)
```

### 2.3 contact_events (= Intercom Data Events)
```sql
CREATE TABLE contact_events (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  contact_id            UUID NOT NULL REFERENCES contacts(id),
  event_name            TEXT NOT NULL,               -- e.g. 'signed_up', 'upgraded', 'churned'
  -- CRITICAL: Intercom enforces FLAT metadata — no nested objects allowed
  metadata              JSONB DEFAULT '{}',           -- flat key-value only, no nesting
  created_at            TIMESTAMPTZ DEFAULT NOW()     -- Intercom uses Unix seconds; store as TIMESTAMPTZ
);
-- Normalization note: Intercom = Unix seconds, Crisp = Unix ms, Zendesk = ISO 8601
-- Always store as TIMESTAMPTZ internally; normalize at ingestion
```

### 2.4 data_attributes (= Intercom Data Attributes)
```sql
CREATE TABLE data_attributes (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  model                 TEXT NOT NULL,               -- contact | company | conversation
  name                  TEXT NOT NULL,
  label                 TEXT,
  data_type             TEXT NOT NULL,
  -- data_type enum: string | integer | float | boolean | date | list
  description           TEXT,
  options               JSONB,                       -- for list type: array of allowed values
  archived              BOOLEAN DEFAULT FALSE,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, model, name)
);
-- CRITICAL: Intercom silently ignores custom attributes not pre-declared via Data Attributes API
-- Pulse compat layer must enforce this same behavior
```

### 2.5 segments
```sql
CREATE TABLE segments (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  filter_rules          JSONB NOT NULL,               -- dynamic filter definition
  person_type           TEXT DEFAULT 'contact',      -- contact | lead
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3. Conversation Model

### 3.1 conversations
```sql
CREATE TABLE conversations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  inbox_id              UUID REFERENCES inboxes(id),
  chatbot_id            UUID REFERENCES chatbots(id),

  -- Participants
  contact_id            UUID REFERENCES contacts(id),
  assignee_id           UUID REFERENCES agents(id),   -- NULL = unassigned / bot-only
  team_id               UUID REFERENCES teams(id),    -- NULL = no team routing

  -- State machine
  -- Intercom: open | snoozed | closed
  -- Chatwoot: open(0) | resolved(1) | pending(2) | snoozed(3)
  -- Zendesk: new | open | pending | hold | solved | closed
  -- Pulse unified (Intercom-compatible primary, Chatwoot-compatible secondary):
  status                TEXT DEFAULT 'open',
  -- status enum: open | pending | snoozed | resolved | closed
  -- NOTE: 'open' and 'closed' are the Intercom-compatible values
  -- 'resolved' is Chatwoot/Zendesk compatible (maps to 'closed' in Intercom output)
  snoozed_until         TIMESTAMPTZ,                  -- Intercom: snoozed_until
  waiting_since         TIMESTAMPTZ,                  -- Intercom: waiting_since (conversation aging)

  -- Priority
  priority              TEXT DEFAULT 'normal',
  -- Intercom: priority | not_priority (binary)
  -- Chatwoot: low(0) | medium(1) | high(2) | urgent(3)
  -- Pulse uses: urgent | high | normal | low (maps to both)

  -- Channel
  channel               TEXT DEFAULT 'chat',
  -- channel enum: chat | email | whatsapp | slack | telegram | sms | api

  -- Routing / Context
  lifecycle_stage       TEXT DEFAULT 'unknown',       -- presales | postsales | unknown
  source_url            TEXT,                         -- page URL where conversation started
  source_title          TEXT,

  -- AI-native fields
  confidence_avg        FLOAT,                        -- avg AI confidence across all RAG calls
  outcome               TEXT,
  -- outcome enum: resolved_autonomously | escalated_to_human | churned | upgraded | bug_filed | abandoned
  ai_participated       BOOLEAN DEFAULT TRUE,         -- Intercom: ai_agent_participated
  escalation_reason     TEXT,
  -- escalation_reason enum: sentiment | complexity | account_value | compliance | explicit_request | low_confidence
  autonomous_resolved   BOOLEAN DEFAULT FALSE,        -- TRUE if AI resolved with no human touch

  -- SLA (Intercom has sla_applied object)
  sla_policy_id         UUID,                         -- nullable; Phase 3
  first_response_at     TIMESTAMPTZ,
  resolved_at           TIMESTAMPTZ,

  -- Statistics (Intercom has statistics sub-object)
  stats                 JSONB DEFAULT '{}',
  -- stats keys: first_response_time_seconds, resolution_time_seconds, reopens_count

  -- External IDs
  intercom_id           TEXT,
  external_id           TEXT,

  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 messages (= Intercom ConversationPart = Chatwoot Message)
```sql
CREATE TABLE messages (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id       UUID NOT NULL REFERENCES conversations(id),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),

  -- Authorship
  -- Intercom part_type: comment | note | assignment | close | open | snooze | away_mode_assignment | transfer
  -- Intercom author.type: admin | user | bot | operator
  -- Chatwoot message_type: incoming(0) | outgoing(1) | activity(2) | template(3)
  -- Pulse unifies:
  message_type          TEXT NOT NULL,
  -- message_type enum: incoming | outgoing | activity | note | template
  author_type           TEXT NOT NULL,
  -- author_type enum: contact | agent | bot | system
  -- Maps to Intercom: contact=user, agent=admin, bot=bot, system=operator
  author_id             UUID,                         -- contact_id OR agent_id depending on author_type

  -- Intercom part_type (for compat layer output mapping)
  part_type             TEXT,
  -- part_type enum: comment | note | assignment | close | open | snooze | transfer | activity

  -- Content
  content               TEXT,
  content_type          TEXT DEFAULT 'text',
  -- content_type enum: text | html | input_text | cards | input_select | image
  -- (Chatwoot has 13 content types; we start with core 4)
  attachments           JSONB DEFAULT '[]',

  -- Delivery status
  status                TEXT DEFAULT 'sent',
  -- status enum: sent | delivered | read | failed
  seen_at               TIMESTAMPTZ,
  delivered_at          TIMESTAMPTZ,

  -- AI-native fields
  confidence_score      FLOAT,                        -- RAG confidence for this specific AI message
  retrieval_log_id      UUID,                         -- FK to retrieval_logs
  is_fallback           BOOLEAN DEFAULT FALSE,        -- TRUE if AI used fallback response

  -- External IDs
  intercom_part_id      TEXT,

  created_at            TIMESTAMPTZ DEFAULT NOW()
);
-- CRITICAL: Intercom caps ConversationParts at 150 per conversation
-- Pulse must handle pagination/archiving of long conversations
```

### 3.3 tags + junction table
```sql
CREATE TABLE tags (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  color                 TEXT DEFAULT '#6366f1',
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, name)
);

CREATE TABLE conversation_tags (
  conversation_id       UUID NOT NULL REFERENCES conversations(id),
  tag_id                UUID NOT NULL REFERENCES tags(id),
  applied_by_agent_id   UUID REFERENCES agents(id),  -- Intercom: applied_by audit field
  applied_at            TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (conversation_id, tag_id)
);
```

### 3.4 tickets (= Intercom Ticket — SEPARATE from conversations)
```sql
-- CRITICAL FINDING: Intercom Ticket is NOT the same as a Conversation
-- Tickets have their own state machine and type taxonomy
CREATE TABLE tickets (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  conversation_id       UUID REFERENCES conversations(id), -- optional link to source conversation
  contact_id            UUID REFERENCES contacts(id),
  assignee_id           UUID REFERENCES agents(id),
  team_id               UUID REFERENCES teams(id),

  -- Ticket state machine (Intercom: ticket_state.category)
  ticket_state          TEXT DEFAULT 'submitted',
  -- ticket_state enum: submitted | in_progress | waiting_on_customer | resolved

  -- Ticket type (Intercom: ticket_type.category)
  ticket_type_category  TEXT DEFAULT 'customer',
  -- ticket_type_category enum: customer | back_office | tracker

  title                 TEXT,
  description           TEXT,
  custom_attributes     JSONB DEFAULT '{}',

  intercom_ticket_id    TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Knowledge Base Model

### 4.1 chatbots
```sql
CREATE TABLE chatbots (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  slug                  TEXT,

  -- Persona
  display_name          TEXT DEFAULT 'Assistant',
  avatar_url            TEXT,
  system_prompt         TEXT,
  tone                  TEXT DEFAULT 'professional',  -- professional | friendly | technical | custom
  language              TEXT DEFAULT 'en',

  -- AI Config
  llm_provider          TEXT DEFAULT 'openai',        -- openai | anthropic | google
  llm_model             TEXT DEFAULT 'gpt-4o-mini',
  byoak                 TEXT,                         -- encrypted user API key (nullable = use platform key)
  temperature           FLOAT DEFAULT 0.3,
  max_tokens            INTEGER DEFAULT 1000,
  confidence_threshold  FLOAT DEFAULT 0.65,           -- below = escalate + log gap

  -- Retrieval config
  retrieval_top_k       INTEGER DEFAULT 5,
  use_reranking         BOOLEAN DEFAULT TRUE,
  use_hybrid_retrieval  BOOLEAN DEFAULT TRUE,

  -- Lifecycle routing
  presales_kb_id        UUID,                         -- FK to knowledge_bases
  postsales_kb_id       UUID,                         -- FK to knowledge_bases

  -- Fallback behavior
  fallback_type         TEXT DEFAULT 'escalate',      -- escalate | message | collect_email
  fallback_message      TEXT,

  is_active             BOOLEAN DEFAULT TRUE,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 knowledge_bases
```sql
CREATE TABLE knowledge_bases (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  chatbot_id            UUID REFERENCES chatbots(id),
  name                  TEXT NOT NULL,
  kb_type               TEXT DEFAULT 'general',       -- general | presales | postsales
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.3 documents (KB sources)
```sql
CREATE TABLE documents (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  knowledge_base_id     UUID NOT NULL REFERENCES knowledge_bases(id),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),

  source_type           TEXT NOT NULL,
  -- Chatbase source.type enum: url | file | text | sitemap | notion | qa
  -- Pulse extends: url | file | text | sitemap | notion | qa | google_drive | api_endpoint | youtube

  source_url            TEXT,                         -- for url/sitemap types
  file_path             TEXT,                         -- for file type
  raw_content           TEXT,                         -- for text/qa type

  title                 TEXT,
  status                TEXT DEFAULT 'pending',       -- pending | processing | indexed | failed | stale
  chunk_count           INTEGER DEFAULT 0,
  last_indexed_at       TIMESTAMPTZ,
  next_sync_at          TIMESTAMPTZ,                  -- for auto-sync/re-crawl
  sync_frequency        TEXT DEFAULT 'weekly',        -- daily | weekly | manual

  metadata              JSONB DEFAULT '{}',
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.4 articles (= Intercom Articles = Chatwoot Article)
```sql
CREATE TABLE article_collections (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  name                  TEXT NOT NULL,
  description           TEXT,
  icon                  TEXT,
  parent_id             UUID REFERENCES article_collections(id), -- for section hierarchy
  -- Intercom: collection → section → article (3 levels via parent_type + parent_id)
  collection_type       TEXT DEFAULT 'collection',   -- collection | section
  order_index           INTEGER DEFAULT 0,
  intercom_id           TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE articles (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  knowledge_base_id     UUID REFERENCES knowledge_bases(id),
  collection_id         UUID REFERENCES article_collections(id),
  author_id             UUID REFERENCES agents(id),

  title                 TEXT NOT NULL,
  description           TEXT,                         -- SEO description
  body                  TEXT,                         -- HTML content (Intercom preserves HTML fidelity)
  slug                  TEXT,

  -- Intercom state enum: published | draft
  -- Pulse extends: published | draft | archived | ai_draft_pending
  state                 TEXT DEFAULT 'draft',

  -- AI-native fields
  is_ai_drafted         BOOLEAN DEFAULT FALSE,        -- auto-drafted from gap cluster
  gap_cluster_id        UUID,                         -- source gap cluster
  approved_by           UUID REFERENCES agents(id),
  approved_at           TIMESTAMPTZ,

  -- Stats
  views_count           INTEGER DEFAULT 0,
  helpful_count         INTEGER DEFAULT 0,
  not_helpful_count     INTEGER DEFAULT 0,

  -- Intercom parent fields
  parent_id             TEXT,                         -- Intercom collection/section ID
  parent_type           TEXT,                         -- collection | section
  intercom_id           TEXT,

  language              TEXT DEFAULT 'en',
  order_index           INTEGER DEFAULT 0,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. AI-Native Intelligence Tables

### 5.1 retrieval_logs (THE foundational AI-native table)
```sql
CREATE TABLE retrieval_logs (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  chatbot_id            UUID NOT NULL REFERENCES chatbots(id),
  conversation_id       UUID REFERENCES conversations(id),
  message_id            UUID REFERENCES messages(id),

  -- The RAG call
  query                 TEXT NOT NULL,               -- user's query as sent to vector search
  query_embedding_model TEXT DEFAULT 'text-embedding-3-small',

  -- Retrieval results
  confidence_score      FLOAT NOT NULL,              -- max score from top-k results (0.0-1.0)
  confidence_avg        FLOAT,                       -- avg score across top-k
  retrieved_chunk_ids   UUID[],                      -- array of Qdrant chunk IDs
  reranked             BOOLEAN DEFAULT FALSE,

  -- Outcome
  threshold_triggered   BOOLEAN GENERATED ALWAYS AS (confidence_score < 0.65) STORED,
  escalated            BOOLEAN DEFAULT FALSE,
  response_generated   BOOLEAN DEFAULT TRUE,

  -- Latency
  retrieval_ms          INTEGER,
  generation_ms         INTEGER,

  created_at            TIMESTAMPTZ DEFAULT NOW()
);
-- Index on threshold_triggered for gap detection queries
CREATE INDEX idx_retrieval_logs_gap ON retrieval_logs(workspace_id, threshold_triggered, created_at);
```

### 5.2 gap_events
```sql
CREATE TABLE gap_events (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  retrieval_log_id      UUID NOT NULL REFERENCES retrieval_logs(id),
  query                 TEXT NOT NULL,
  confidence_score      FLOAT NOT NULL,
  gap_cluster_id        UUID,                         -- FK set after BERTopic clustering run
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.3 gap_clusters
```sql
CREATE TABLE gap_clusters (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  chatbot_id            UUID REFERENCES chatbots(id),
  topic_label           TEXT NOT NULL,               -- BERTopic-generated label
  topic_keywords        TEXT[],                      -- extracted keywords
  gap_count             INTEGER DEFAULT 0,           -- number of gap_events in cluster
  representative_query  TEXT,                        -- most representative query
  status                TEXT DEFAULT 'open',
  -- status enum: open | draft_ready | approved | resolved | dismissed
  draft_article_id      UUID REFERENCES articles(id),
  resolved_at           TIMESTAMPTZ,
  resolution_impact     FLOAT,                       -- delta in resolution rate after fix
  clustered_at          TIMESTAMPTZ DEFAULT NOW(),
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.4 intelligence_signals
```sql
CREATE TABLE intelligence_signals (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  conversation_id       UUID NOT NULL REFERENCES conversations(id),
  contact_id            UUID REFERENCES contacts(id),

  signal_type           TEXT NOT NULL,
  -- signal_type enum:
  -- lead_hot | lead_warm | feature_request | competitor_mention |
  -- churn_risk | expansion_opportunity | bug_report | complaint

  confidence            FLOAT,                       -- LLM confidence in this signal (0.0-1.0)
  payload               JSONB NOT NULL DEFAULT '{}', -- signal-specific data
  -- payload examples:
  -- feature_request: {"feature": "CSV export", "verbatim": "we really need CSV", "priority_signal": true}
  -- competitor_mention: {"competitor": "Intercom", "context": "switching from", "sentiment": "negative"}
  -- lead_hot: {"score": 87, "signals": ["asked pricing", "mentioned team"], "crm_pushed": true}

  actioned              BOOLEAN DEFAULT FALSE,       -- has this been pushed to CRM/Jira/etc
  actioned_at           TIMESTAMPTZ,
  dismissed             BOOLEAN DEFAULT FALSE,

  created_at            TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_signals_type ON intelligence_signals(workspace_id, signal_type, created_at);
```

### 5.5 topic_clusters
```sql
CREATE TABLE topic_clusters (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  chatbot_id            UUID REFERENCES chatbots(id),
  label                 TEXT NOT NULL,               -- BERTopic-generated
  keywords              TEXT[],
  conversation_count    INTEGER DEFAULT 0,
  volume_trend          JSONB DEFAULT '{}',           -- {"week_ago": 12, "two_weeks_ago": 8, "delta_pct": 50}
  anomaly_detected      BOOLEAN DEFAULT FALSE,
  anomaly_type          TEXT,                        -- spike | drop | new_topic
  date_range_start      DATE,
  date_range_end        DATE,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.6 lead_scores
```sql
CREATE TABLE lead_scores (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  contact_id            UUID NOT NULL REFERENCES contacts(id),
  conversation_id       UUID NOT NULL REFERENCES conversations(id),

  score                 INTEGER NOT NULL DEFAULT 0,  -- 0-100
  tier                  TEXT,                        -- hot(>80) | warm(50-79) | cold(<50)
  signals               JSONB DEFAULT '[]',          -- array of signal objects that contributed
  crm_pushed            BOOLEAN DEFAULT FALSE,
  crm_pushed_at         TIMESTAMPTZ,
  slack_alerted         BOOLEAN DEFAULT FALSE,

  scored_at             TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.7 conversation_analysis (post-conversation LLM extraction)
```sql
CREATE TABLE conversation_analysis (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  conversation_id       UUID NOT NULL UNIQUE REFERENCES conversations(id),

  -- 15-field async extraction via GPT-4o-mini
  sentiment_score       FLOAT,                       -- -1.0 to 1.0
  sentiment_label       TEXT,                        -- positive | neutral | negative | mixed
  intent_primary        TEXT,                        -- main intent of the conversation
  intent_secondary      TEXT[],
  outcome_category      TEXT,                        -- resolved | unresolved | escalated | abandoned
  lead_intent           TEXT,                        -- none | low | medium | high
  feature_requests      TEXT[],
  bug_reports           TEXT[],
  competitor_mentions   TEXT[],
  expansion_signals     TEXT[],
  churn_signals         TEXT[],
  topics                TEXT[],
  customer_effort_score FLOAT,                       -- 1-5 estimated from conversation
  summary               TEXT,                        -- 2-sentence conversation summary
  action_items          TEXT[],                      -- recommended follow-up actions

  llm_model             TEXT DEFAULT 'gpt-4o-mini',
  processing_ms         INTEGER,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.8 autonomous_resolution_stats (the primary KPI tracking table)
```sql
CREATE TABLE autonomous_resolution_stats (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID NOT NULL REFERENCES workspaces(id),
  chatbot_id            UUID REFERENCES chatbots(id),
  period_date           DATE NOT NULL,               -- day-level granularity

  total_conversations   INTEGER DEFAULT 0,
  autonomously_resolved INTEGER DEFAULT 0,
  escalated_to_human    INTEGER DEFAULT 0,
  abandoned             INTEGER DEFAULT 0,
  resolution_rate       FLOAT GENERATED ALWAYS AS
    (CASE WHEN total_conversations > 0
     THEN autonomously_resolved::FLOAT / total_conversations
     ELSE 0 END) STORED,

  avg_confidence_score  FLOAT,
  knowledge_velocity    FLOAT,                       -- gaps_closed / new_gaps for this period
  documentation_debt    INTEGER,                     -- open gap_clusters count

  UNIQUE(workspace_id, chatbot_id, period_date)
);
```

---

## 6. Cross-Platform Status Mapping (Intercom Compatibility Layer)

```
Pulse Status     → Intercom Output  → Chatwoot Output  → Zendesk Output
─────────────────────────────────────────────────────────────────────────
open             → open             → open (0)          → open
pending          → open             → pending (2)       → pending
snoozed          → snoozed          → snoozed (3)       → on-hold
resolved         → closed           → resolved (1)      → solved
closed           → closed           → resolved (1)      → closed
```

## 7. Author Type Mapping (Intercom Compatibility Layer)

```
Pulse author_type  → Intercom author.type  → Chatwoot message_type
──────────────────────────────────────────────────────────────────
contact            → user                  → incoming (0)
agent              → admin                 → outgoing (1)
bot                → bot                   → outgoing (1) [channel: api]
system             → operator              → activity (2)
```

## 8. Timestamp Normalization (CRITICAL — 4 different formats in the wild)

```python
# All external timestamps MUST be normalized to TIMESTAMPTZ at ingestion
def normalize_timestamp(value, source_platform: str) -> datetime:
    if source_platform == 'intercom':   # Unix seconds integer
        return datetime.fromtimestamp(value, tz=UTC)
    elif source_platform == 'crisp':    # Unix milliseconds
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    elif source_platform in ('zendesk', 'chatbase'):  # ISO 8601 string
        return datetime.fromisoformat(value)
    else:  # Chatwoot / internal — already Rails datetime / ISO
        return datetime.fromisoformat(value)
```

## 9. 10 Critical Intercom API Gotchas (Engineering Must-Knows)

1. **HMAC-SHA1** for webhook signatures — NOT SHA-256. Most modern webhook libraries default to SHA-256. Must specify SHA1.
2. **POST /companies is a silent UPSERT** — no 409 on duplicate. Upsert behavior on `external_id`.
3. **POST /tags is OVERLOADED** — same endpoint for create and apply. No separate endpoints.
4. **Custom attributes silently ignored** if not pre-declared via Data Attributes API. Must declare schema first.
5. **ConversationParts capped at 150** per conversation. Need pagination/archiving strategy for long conversations.
6. **Events use Unix timestamps** — not ISO 8601. Normalize at ingestion.
7. **team_assignee_id is string-prefixed** — not a plain integer. Handle as string.
8. **lifecycle_stage is NOT a REST API field** — internal Intercom UI only. Do not expose in compat layer.
9. **Flat event metadata only** — no nested objects in event `metadata`. Enforce this constraint.
10. **Rate limit: hard cap at 1,000 req/min** — target 800 as safety buffer.

---

## 10. Tables Reference Summary

| Table | Mode | Purpose |
|---|---|---|
| workspaces | All | Multi-tenant root |
| agents | Intercom+ | Human team members |
| teams | Intercom+ | Agent groups |
| inboxes | Intercom+ | Channel configuration |
| contacts | All | Unified customer identity |
| companies | Intercom+ | Company accounts |
| contact_events | Intercom+ | Behavioral event tracking |
| data_attributes | Intercom+ | Custom attribute schema declarations |
| segments | Intercom+ | Dynamic contact groups |
| conversations | All | Core conversation entity |
| messages | All | Individual messages/parts |
| tags | Intercom+ | Conversation labels |
| conversation_tags | Intercom+ | Tag junction with audit |
| tickets | Phase 3 | Formal ticket entity (separate from conversations) |
| chatbots | All | Bot configuration |
| knowledge_bases | All | KB container |
| documents | All | KB source documents |
| article_collections | Intercom+ | Collection/section hierarchy |
| articles | Intercom+ | KB articles (human + AI-drafted) |
| retrieval_logs | AI-native | Every RAG call logged — foundational |
| gap_events | AI-native | Low-confidence retrievals |
| gap_clusters | AI-native | BERTopic-clustered gaps |
| intelligence_signals | AI-native | Lead/feature/competitor/churn signals |
| topic_clusters | AI-native | BERTopic conversation clusters |
| lead_scores | AI-native | Per-conversation lead scoring |
| conversation_analysis | AI-native | Async LLM post-conversation extraction |
| autonomous_resolution_stats | AI-native | Primary KPI tracking table |

**Total tables: 27** (Chatbase mode uses ~8, full Intercom-compat mode uses ~22, AI-native full uses all 27)

