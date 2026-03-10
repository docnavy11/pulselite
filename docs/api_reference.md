# Pulse API Reference

Base URL: `http://localhost:8000/api/v1`
Interactive docs: `http://localhost:8000/api/docs`

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <access_token>
```

Tokens are obtained from `/auth/login` or `/auth/register`. Access tokens expire after 30 minutes; use `/auth/refresh` with the refresh token to get a new one.

---

## Auth

### POST /auth/register
Register a new account and workspace.

**Body:** `{ email, password, full_name, workspace_name }`
**Returns:** `AuthResponse` — `{ access_token, refresh_token, user, workspace }`

### POST /auth/login
Log in with email + password.

**Body:** `{ email, password }`
**Returns:** `AuthResponse`

### POST /auth/refresh
Exchange a refresh token for a new access token.

**Body:** `{ refresh_token }`
**Returns:** `TokenResponse` — `{ access_token, token_type }`

### GET /auth/google
Initiate Google OAuth flow. Redirects to Google.

### GET /auth/google/callback
OAuth callback — handled by Google redirect. Returns `TokenResponse`.

---

## Workspaces

All data in Pulse is scoped to a workspace. Every authenticated user belongs to one or more workspaces.

### POST /workspaces
Create a new workspace.

**Body:** `{ name }`
**Returns:** `WorkspaceResponse`

### GET /workspaces
List all workspaces the current user belongs to.

**Returns:** `WorkspaceResponse[]`

### GET /workspaces/{workspace_id}
Get a specific workspace.

**Returns:** `WorkspaceResponse`

---

## Chatbots

Prefix: `/workspaces/{workspace_id}/chatbots`

### POST /workspaces/{workspace_id}/chatbots
Create a chatbot.

**Body:** `{ name, description?, knowledge_base_id? }`
**Returns:** `ChatbotResponse`

### GET /workspaces/{workspace_id}/chatbots
List all chatbots in the workspace.

**Returns:** `ChatbotResponse[]`

### GET /workspaces/{workspace_id}/chatbots/{chatbot_id}
Get a specific chatbot.

**Returns:** `ChatbotResponse`

### PUT /workspaces/{workspace_id}/chatbots/{chatbot_id}
Update chatbot name/description.

**Body:** `{ name?, description? }`
**Returns:** `ChatbotResponse`

### DELETE /workspaces/{workspace_id}/chatbots/{chatbot_id}
Delete a chatbot.

**Status:** 204 No Content

### GET /workspaces/{workspace_id}/chatbots/{chatbot_id}/widget-config
Get the widget configuration (colors, position, greeting, etc.).

**Returns:** `WidgetConfig`

### PUT /workspaces/{workspace_id}/chatbots/{chatbot_id}/widget-config
Update widget configuration.

**Body:** `WidgetConfig` — `{ primary_color?, position?, greeting_message?, ... }`
**Returns:** `ChatbotResponse`

### PUT /workspaces/{workspace_id}/chatbots/{chatbot_id}/persona
Update the chatbot's AI persona (name, tone, instructions).

**Body:** `{ persona_name?, persona_instructions?, tone? }`
**Returns:** `ChatbotResponse`

### PUT /workspaces/{workspace_id}/chatbots/{chatbot_id}/llm-config
Update the LLM model/provider/temperature settings.

**Body:** `{ model?, provider?, temperature? }`
**Returns:** `ChatbotResponse`

---

## Knowledge Bases

Prefix: `/workspaces/{workspace_id}/knowledge-bases`

### POST /workspaces/{workspace_id}/knowledge-bases
Create a knowledge base.

**Body:** `{ name, chatbot_id }`
**Returns:** `KnowledgeBaseResponse`

### GET /workspaces/{workspace_id}/knowledge-bases
List knowledge bases.

**Returns:** `KnowledgeBaseResponse[]`

### GET /workspaces/{workspace_id}/knowledge-bases/{kb_id}
Get a knowledge base.

**Returns:** `KnowledgeBaseResponse`

### DELETE /workspaces/{workspace_id}/knowledge-bases/{kb_id}
Delete a knowledge base and all its documents.

**Status:** 204 No Content

---

## Documents

Prefix: `/workspaces/{workspace_id}/documents`

### POST /workspaces/{workspace_id}/documents
Ingest a document from a URL.

**Body:** `{ url, knowledge_base_id, title? }`
**Returns:** `DocumentResponse`

### POST /workspaces/{workspace_id}/documents/upload
Upload a file (PDF, TXT, DOCX, etc.).

**Form data:** `file` + `knowledge_base_id`
**Returns:** `DocumentResponse`

### GET /workspaces/{workspace_id}/documents
List documents (optionally filter by `knowledge_base_id`).

**Query params:** `knowledge_base_id?`
**Returns:** `DocumentResponse[]`

### DELETE /workspaces/{workspace_id}/documents/{document_id}
Delete a document and its chunks.

**Status:** 204 No Content

### POST /workspaces/{workspace_id}/documents/{document_id}/reindex
Re-ingest and re-embed a document (e.g., after source content changes).

**Returns:** `DocumentResponse`

---

## Articles (Living Knowledge Base)

Prefix: `/workspaces/{workspace_id}/articles`

### POST /workspaces/{workspace_id}/articles
Create an article.

**Body:** `{ title, content, knowledge_base_id }`
**Returns:** `ArticleResponse`

### GET /workspaces/{workspace_id}/articles
List articles.

**Returns:** `ArticleResponse[]`

### GET /workspaces/{workspace_id}/articles/{article_id}
Get an article.

**Returns:** `ArticleResponse`

### PUT /workspaces/{workspace_id}/articles/{article_id}
Update article title/content.

**Body:** `{ title?, content? }`
**Returns:** `ArticleResponse`

### PUT /workspaces/{workspace_id}/articles/{article_id}/publish
Publish a draft article (triggers reindex into vector store).

**Returns:** `ArticleResponse`

### DELETE /workspaces/{workspace_id}/articles/{article_id}
Delete an article.

**Status:** 204 No Content

---

## Chat (Authenticated)

### POST /api/v1/chat
Send a message to a chatbot (streaming SSE).

**Body:** `{ chatbot_id, message, conversation_id? }`
**Returns:** SSE stream — events: `token`, `done`, `error`

```
data: {"type": "token", "data": "Hello"}
data: {"type": "done", "conversation_id": "uuid"}
```

### GET /workspaces/{workspace_id}/conversations
List conversations.

**Returns:** `ConversationResponse[]`

### GET /workspaces/{workspace_id}/conversations/{conversation_id}
Get a conversation.

**Returns:** `ConversationResponse`

### GET /workspaces/{workspace_id}/conversations/{conversation_id}/messages
Get all messages in a conversation.

**Returns:** `MessageResponse[]`

---

## Exceptions Queue

### GET /workspaces/{workspace_id}/exceptions
List escalated conversations requiring human review.

**Query params:** `escalation_reason?`, `chatbot_id?`, `date_from?`, `date_to?`, `limit` (max 100, default 50), `offset`
**Returns:** `{ items: ExceptionItem[], total: number }`

### GET /workspaces/{workspace_id}/exceptions/{conversation_id}
Get full exception detail including messages, contact context, and AI-suggested action.

**Returns:** `{ conversation, messages, contact_context, suggested_action }`

### POST /workspaces/{workspace_id}/exceptions/{conversation_id}/reply
Send a human reply to the customer.

**Body:** `{ message, resolve? }` — if `resolve: true`, also marks conversation as resolved
**Status:** 201 Created

### POST /workspaces/{workspace_id}/exceptions/{conversation_id}/resolve
Mark an escalation as resolved without sending a reply.

**Status:** 200 OK

---

## Gap Clusters (Doc Gaps)

### GET /workspaces/{workspace_id}/gap-clusters
List documentation gap clusters (groups of unanswered questions).

**Query params:** `status_filter?`, `chatbot_id?`, `limit`, `offset`
**Returns:** `GapClusterResponse[]`

### GET /workspaces/{workspace_id}/gap-clusters/{cluster_id}
Get a gap cluster with its representative questions and AI-drafted article.

**Returns:** `GapClusterDetailResponse`

### POST /workspaces/{workspace_id}/gap-clusters/{cluster_id}/approve
Approve the AI-drafted article and publish it to the knowledge base.

**Returns:** 200 OK

### POST /workspaces/{workspace_id}/gap-clusters/{cluster_id}/dismiss
Dismiss a gap cluster (won't reappear).

**Returns:** 200 OK

### PUT /workspaces/{workspace_id}/gap-clusters/{cluster_id}/draft
Edit the AI-drafted article before approving.

**Body:** `{ title?, content? }`
**Returns:** updated draft

---

## Dashboard & Intelligence

### GET /workspaces/{workspace_id}/dashboard
Main dashboard stats: autonomous resolution rate, conversation volumes, escalation breakdown.

**Query params:** `days?` (default 30)
**Returns:** dashboard metrics object

### GET /workspaces/{workspace_id}/topics
Topic clusters from conversation analysis.

**Returns:** topic cluster list

### GET /workspaces/{workspace_id}/topics/{topic_id}
Topic cluster detail with representative messages.

### GET /workspaces/{workspace_id}/sentiment-trends
Sentiment trend data over time.

**Query params:** `days?` (default 30)
**Returns:** `{ data: [{ date, avg_sentiment, count }] }`

### GET /workspaces/{workspace_id}/feature-requests
Feature request clusters extracted from conversations.

**Returns:** feature request cluster list

### GET /workspaces/{workspace_id}/leads
Lead scoring feed — contacts ranked by conversion probability.

**Returns:** lead list with scores and tiers (hot/warm/cold)

### GET /workspaces/{workspace_id}/resolution-stats
Resolution rate time-series data.

**Returns:** `ResolutionStatsResponse[]`

### GET /workspaces/{workspace_id}/retrieval-logs
RAG retrieval debug logs — which chunks were retrieved and their scores.

**Returns:** `RetrievalLogResponse[]`

### GET /workspaces/{workspace_id}/gap-events
Raw gap events (individual unanswered questions before clustering).

**Returns:** `GapEventResponse[]`

### GET /workspaces/{workspace_id}/lead-scores
Detailed lead score records.

**Returns:** `LeadScoreResponse[]`

### GET /workspaces/{workspace_id}/intelligence-signals
Raw intelligence signals extracted from conversations.

**Returns:** `IntelligenceSignalResponse[]`

### GET /workspaces/{workspace_id}/conversations/{conversation_id}/analysis
Full analysis of a specific conversation (topics, sentiment, signals).

**Returns:** `ConversationAnalysisResponse`

### POST /workspaces/{workspace_id}/conversations/{conversation_id}/end
Manually trigger end-of-conversation analysis pipeline.

---

## API Keys

Prefix: `/workspaces/{workspace_id}/api-keys`

### POST /workspaces/{workspace_id}/api-keys
Create an API key (for REST API access from external systems).

**Body:** `{ name }`
**Returns:** `ApiKeyCreatedResponse` — includes the full key (shown once only)

### GET /workspaces/{workspace_id}/api-keys
List API keys (prefix only, not full key).

**Returns:** `ApiKeyResponse[]`

### DELETE /workspaces/{workspace_id}/api-keys/{key_id}
Revoke an API key.

**Status:** 204 No Content

---

## Integrations

Prefix: `/workspaces/{workspace_id}/integrations`

### GET /workspaces/{workspace_id}/integrations
List all integration configs (Slack, Intercom, Zendesk, etc.).

**Returns:** integration list with connection status

### PUT /workspaces/{workspace_id}/integrations/{integration_type}
Configure or update an integration.

**Body:** `{ config }` (integration-specific fields)

### POST /workspaces/{workspace_id}/integrations/{integration_type}/test
Test an integration connection.

**Returns:** `{ success, message }`

### DELETE /workspaces/{workspace_id}/integrations/{integration_type}
Disconnect an integration.

**Status:** 204 No Content

---

## Billing

### GET /billing/plans
List available billing plans (public endpoint, no auth required).

**Returns:** `[{ id, name, price, interval, features, is_popular }]`

### POST /workspaces/{workspace_id}/billing/checkout
Create a Stripe Checkout session to upgrade.

**Body:** `{ plan_id }`
**Returns:** `{ checkout_url }`

### POST /workspaces/{workspace_id}/billing/portal
Create a Stripe Customer Portal session to manage subscription.

**Returns:** `{ portal_url }`

### POST /billing/webhook
Stripe webhook receiver (called by Stripe, not directly by clients).

### GET /workspaces/{workspace_id}/credits/balance
Get AI credit balance and usage.

**Returns:** `{ balance, used, limit, plan }`

### GET /workspaces/{workspace_id}/credits/history
Get credit usage history.

---

## Onboarding

Prefix: `/workspaces/{workspace_id}/onboarding`

### GET /workspaces/{workspace_id}/onboarding
Get onboarding progress.

**Returns:** `{ steps: [{ step_number, completed, completed_at }] }`

### PUT /workspaces/{workspace_id}/onboarding/step/{step_number}
Mark an onboarding step complete.

### POST /workspaces/{workspace_id}/onboarding/complete
Mark onboarding fully complete.

---

## GDPR / Data Management

Prefix: `/workspaces/{workspace_id}`

### POST /workspaces/{workspace_id}/export
Trigger a GDPR data export for the workspace.

**Returns:** `{ export_id }`

### GET /workspaces/{workspace_id}/export/{export_id}/download
Download a completed data export.

### DELETE /workspaces/{workspace_id}/contacts/{contact_id}
Delete a contact and all their data (right to erasure).

### DELETE /workspaces/{workspace_id}
Delete the entire workspace and all associated data.

---

## OpenAI-Compatible Completions

### POST /api/v1/chat/completions
OpenAI-compatible chat completions endpoint for drop-in replacement use.

**Auth:** `X-API-Key` header (workspace API key)
**Body:** OpenAI `ChatCompletionRequest` format
**Returns:** `CompletionResponse`

---

## Public Endpoints (No Auth)

### POST /api/v1/public/chat
Send a message from an embedded widget (rate-limited: 20/min per IP).

**Auth:** `X-API-Key` header (workspace API key)
**Body:** `{ chatbot_id, message, session_id }`
**Returns:** SSE stream (same format as authenticated chat)

### GET /api/v1/widget/{chatbot_id}/config
Get public widget configuration for rendering the chat widget.

**Returns:** `WidgetConfigResponse`

### GET /api/v1/share/{chatbot_id}
Get shareable chatbot page data.

**Returns:** `ShareResponse`

---

## Health

### GET /api/v1/health
Liveness check.

**Returns:** `{ status: "ok" }`

---

## Error Responses

All errors follow this shape:

```json
{ "detail": "Error message" }
```

| Status | Meaning |
|---|---|
| 400 | Bad request / validation error |
| 401 | Missing or invalid token |
| 403 | Authenticated but not authorized for this resource |
| 404 | Resource not found |
| 422 | Request body failed schema validation |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
