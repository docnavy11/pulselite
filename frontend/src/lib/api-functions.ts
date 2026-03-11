import { api } from "./api";
import { getTokens } from "./auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import {
  Action,
  ActionCreate,
  ActionUpdate,
  AutoConfigResponse,
  Chatbot,
  CrawlJobSummary,
  CrawlResponse,
  CrawlStatusResponse,
  KnowledgeBase,
  Document,
  Article,
  Conversation,
  Message,
  WidgetConfig,
  GapCluster,
  GapClusterDetail,
  DashboardData,
  SentimentData,
  Invite,
  IntegrationConfig,
  BillingPlan,
  CreditBalance,
  OnboardingState,
  UsageBreakdown,
  SegmentSentimentItem,
  Webhook,
  LLMSettings,
  OpenRouterModel,
} from "./types";

// Chatbot CRUD
export function getChatbots(workspaceId: string) {
  return api.get<Chatbot[]>(`/api/v1/workspaces/${workspaceId}/chatbots`);
}

export function getChatbotStats(workspaceId: string) {
  return api.get<Record<string, { conversations_30d: number; resolution_rate: number; last_active: string | null }>>(
    `/api/v1/workspaces/${workspaceId}/chatbots/stats/summary`
  );
}

export function getChatbot(workspaceId: string, id: string) {
  return api.get<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${id}`);
}

export function createChatbot(workspaceId: string, data: { name: string; tone?: string }) {
  return api.post<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots`, data);
}

export function updateChatbot(workspaceId: string, id: string, data: Partial<Chatbot>) {
  return api.put<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${id}`, data);
}

export function deleteChatbot(workspaceId: string, id: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}/chatbots/${id}`);
}

export function updateLLMConfig(
  workspaceId: string,
  chatbotId: string,
  data: {
    llm_provider?: string;
    llm_model?: string;
    temperature?: number;
    max_tokens?: number;
    confidence_threshold?: number;
    retrieval_top_k?: number;
    use_reranking?: boolean;
    use_hybrid_retrieval?: boolean;
  },
) {
  return api.put<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/llm-config`, data);
}

export function duplicateChatbot(workspaceId: string, chatbotId: string) {
  return api.post<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/duplicate`);
}

export function startCrawl(workspaceId: string, url: string, maxPages: number, chatbotId?: string) {
  return api.post<CrawlResponse>(`/api/v1/workspaces/${workspaceId}/crawl`, { url, max_pages: maxPages, chatbot_id: chatbotId });
}

export function getCrawlStatus(workspaceId: string, jobId: string) {
  return api.get<CrawlStatusResponse>(`/api/v1/workspaces/${workspaceId}/crawl/${jobId}`);
}

export function getLatestCrawlForChatbot(workspaceId: string, chatbotId: string) {
  return api.get<CrawlStatusResponse | null>(`/api/v1/workspaces/${workspaceId}/crawl?chatbot_id=${chatbotId}`);
}

export function getCrawlHistory(workspaceId: string, chatbotId: string) {
  return api.get<CrawlJobSummary[]>(`/api/v1/workspaces/${workspaceId}/crawl/history?chatbot_id=${chatbotId}`);
}

export function runAutoconfig(workspaceId: string, chatbotId: string, knowledgeBaseId: string) {
  return api.post<AutoConfigResponse>(
    `/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/autoconfig`,
    { knowledge_base_id: knowledgeBaseId },
  );
}

// Knowledge Base
export function getKnowledgeBases(workspaceId: string, chatbotId?: string) {
  const params = chatbotId ? `?chatbot_id=${chatbotId}` : "";
  return api.get<KnowledgeBase[]>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases${params}`,
  );
}

export function createKnowledgeBase(
  workspaceId: string,
  data: { name: string; kb_type: string; chatbot_id?: string },
) {
  return api.post<KnowledgeBase>(
    `/api/v1/workspaces/${workspaceId}/knowledge-bases`,
    data,
  );
}

// Documents
export function getDocuments(workspaceId: string, knowledgeBaseId: string) {
  return api.get<Document[]>(
    `/api/v1/workspaces/${workspaceId}/documents?knowledge_base_id=${knowledgeBaseId}`,
  );
}

export function createDocumentFromUrl(
  workspaceId: string,
  data: { source_url: string; title?: string; knowledge_base_id?: string; source_type?: string },
) {
  return api.post<Document>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    { source_type: "url", ...data },
  );
}

export function updateDocument(
  workspaceId: string,
  documentId: string,
  data: { sync_frequency?: string; title?: string },
) {
  return api.patch<Document>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}`,
    data,
  );
}

export function createDocumentFromText(
  workspaceId: string,
  data: { raw_content: string; title?: string; content_type?: "plain" | "qa"; knowledge_base_id: string },
) {
  const { content_type, raw_content, title, knowledge_base_id } = data;
  const source_type = content_type === "qa" ? "qa" : "text";
  return api.post<Document>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    { source_type, raw_content, title, knowledge_base_id },
  );
}

export function createDocumentFromFile(
  workspaceId: string,
  file: File,
  knowledgeBaseId: string,
) {
  const formData = new FormData();
  formData.append("file", file);
  return api.postFormData<Document>(
    `/api/v1/workspaces/${workspaceId}/documents/upload?knowledge_base_id=${knowledgeBaseId}`,
    formData,
  );
}

export function deleteDocument(workspaceId: string, documentId: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}/documents/${documentId}`);
}

export function reindexDocument(workspaceId: string, documentId: string) {
  return api.post<Document>(`/api/v1/workspaces/${workspaceId}/documents/${documentId}/reindex`);
}

// Articles
export function getArticles(workspaceId: string) {
  return api.get<Article[]>(
    `/api/v1/workspaces/${workspaceId}/articles`,
  );
}

export function getArticle(workspaceId: string, articleId: string) {
  return api.get<Article>(`/api/v1/workspaces/${workspaceId}/articles/${articleId}`);
}

export function createArticle(
  workspaceId: string,
  data: { title: string; body?: string },
) {
  return api.post<Article>(
    `/api/v1/workspaces/${workspaceId}/articles`,
    data,
  );
}

export function updateArticle(
  workspaceId: string,
  articleId: string,
  data: Partial<Pick<Article, "title" | "body" | "collection_id">>,
) {
  return api.put<Article>(`/api/v1/workspaces/${workspaceId}/articles/${articleId}`, data);
}

export function deleteArticle(workspaceId: string, articleId: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}/articles/${articleId}`);
}

export function publishArticle(workspaceId: string, articleId: string) {
  return api.put<Article>(`/api/v1/workspaces/${workspaceId}/articles/${articleId}/publish`);
}

// Conversations
export function getConversations(
  workspaceId: string,
  filters?: { status?: string; chatbot_id?: string; date_from?: string; date_to?: string },
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.chatbot_id) params.set("chatbot_id", filters.chatbot_id);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  const qs = params.toString();
  return api.get<Conversation[]>(
    `/api/v1/workspaces/${workspaceId}/conversations${qs ? `?${qs}` : ""}`,
  );
}

export function getConversation(workspaceId: string, conversationId: string) {
  return api.get<Conversation>(
    `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}`,
  );
}

export function getMessages(workspaceId: string, conversationId: string) {
  return api.get<Message[]>(
    `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
  );
}

export function updateConversationStatus(
  workspaceId: string,
  conversationId: string,
  status: string,
) {
  return api.put<Conversation>(
    `/api/v1/workspaces/${workspaceId}/conversations/${conversationId}`,
    { status },
  );
}

// Widget Config
export function getWidgetConfig(workspaceId: string, chatbotId: string) {
  return api.get<WidgetConfig>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/widget-config`);
}

export function updateWidgetConfig(workspaceId: string, chatbotId: string, config: WidgetConfig) {
  return api.put<WidgetConfig>(
    `/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/widget-config`,
    config,
  );
}

export function getPublicWidgetConfig(chatbotId: string) {
  return api.get<WidgetConfig & { display_name?: string }>(
    `/api/v1/widget/${chatbotId}/config`,
  );
}

// Gap Clusters
export function getGapClusters(
  workspaceId: string,
  filters?: { status?: string },
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  const qs = params.toString();
  return api.get<GapCluster[]>(
    `/api/v1/workspaces/${workspaceId}/gap-clusters${qs ? `?${qs}` : ""}`,
  );
}

export function getGapClusterDetail(workspaceId: string, clusterId: string) {
  return api.get<GapClusterDetail>(
    `/api/v1/workspaces/${workspaceId}/gap-clusters/${clusterId}`,
  );
}

export function approveGapCluster(workspaceId: string, clusterId: string) {
  return api.post<void>(
    `/api/v1/workspaces/${workspaceId}/gap-clusters/${clusterId}/approve`,
  );
}

export function dismissGapCluster(workspaceId: string, clusterId: string) {
  return api.post<void>(
    `/api/v1/workspaces/${workspaceId}/gap-clusters/${clusterId}/dismiss`,
  );
}

// Dashboard
export function getDashboardData(
  workspaceId: string,
  range: string,
  chatbotId?: string,
) {
  const params = new URLSearchParams({ range });
  if (chatbotId) params.set("chatbot_id", chatbotId);
  return api.get<DashboardData>(
    `/api/v1/workspaces/${workspaceId}/dashboard?${params}`,
  );
}

// Sentiment
export function getSentimentTrends(workspaceId: string, range: string) {
  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
  return api
    .get<{ data: { date: string; avg_sentiment: number | null; count: number }[] }>(
      `/api/v1/workspaces/${workspaceId}/sentiment-trends?days=${days}`,
    )
    .then((r) => {
      const points = r.data.filter((d) => d.avg_sentiment !== null);
      const scores = points.map((d) => ({ date: d.date, score: d.avg_sentiment! }));
      const avg = scores.length
        ? scores.reduce((s, d) => s + d.score, 0) / scores.length
        : 0;
      const positive = scores.filter((d) => d.score >= 0.3).length;
      const negative = scores.filter((d) => d.score <= -0.3).length;
      const trend =
        scores.length >= 2
          ? scores[scores.length - 1].score - scores[0].score
          : 0;
      return {
        data_points: scores,
        avg_sentiment: parseFloat(avg.toFixed(3)),
        positive_pct: scores.length ? (positive / scores.length) * 100 : 0,
        negative_pct: scores.length ? (negative / scores.length) * 100 : 0,
        trend: parseFloat(trend.toFixed(3)),
        alerts: [],
      } as SentimentData;
    });
}


// Integrations
export function getIntegrations(workspaceId: string) {
  return api.get<IntegrationConfig[]>(
    `/api/v1/workspaces/${workspaceId}/integrations`,
  );
}

export function updateIntegration(
  workspaceId: string,
  integrationId: string,
  config: Record<string, unknown>,
) {
  return api.put<IntegrationConfig>(
    `/api/v1/workspaces/${workspaceId}/integrations/${integrationId}`,
    config,
  );
}

export function testIntegration(workspaceId: string, integrationId: string) {
  return api.post<{ success: boolean; message: string }>(
    `/api/v1/workspaces/${workspaceId}/integrations/${integrationId}/test`,
  );
}

// Billing
export function getBillingPlans() {
  return api.get<BillingPlan[]>("/api/v1/billing/plans");
}

export function createCheckoutSession(workspaceId: string, planId: string, interval: "monthly" | "annual" = "monthly") {
  const origin = typeof window !== "undefined" ? window.location.origin : BASE_URL;
  return api.post<{ url: string }>(`/api/v1/workspaces/${workspaceId}/billing/checkout`, { plan: planId, interval, success_url: origin + "/settings/billing", cancel_url: origin + "/settings/billing" });
}

export function createPortalSession(workspaceId: string) {
  const origin = typeof window !== "undefined" ? window.location.origin : BASE_URL;
  return api.post<{ url: string }>(`/api/v1/workspaces/${workspaceId}/billing/portal`, { return_url: origin + "/settings/billing" });
}

export function getCreditsBalance(workspaceId: string) {
  return api.get<{ balance: number; used_this_month: number }>(
    `/api/v1/workspaces/${workspaceId}/credits/balance`,
  ).then((r) => ({
    balance: r.balance,
    usage_this_month: r.used_this_month ?? 0,
    usage_history: [],
  }) as CreditBalance);
}

// Onboarding
export function getOnboardingState(workspaceId: string) {
  return api.get<OnboardingState>(
    `/api/v1/workspaces/${workspaceId}/onboarding`,
  );
}

export function updateOnboardingStep(
  workspaceId: string,
  step: number,
  data: Record<string, unknown>,
) {
  return api.put<OnboardingState>(
    `/api/v1/workspaces/${workspaceId}/onboarding/step/${step}`,
    data,
  );
}

export function completeOnboarding(workspaceId: string) {
  return api.post<void>(
    `/api/v1/workspaces/${workspaceId}/onboarding/complete`,
  );
}

// GDPR
export function requestDataExport(workspaceId: string) {
  return api.post<{ export_id: string; status: string }>(
    `/api/v1/workspaces/${workspaceId}/export`,
  );
}

export function deleteWorkspace(workspaceId: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}`);
}

export function getWorkspaces() {
  return api.get<import("./types").Workspace[]>("/api/v1/workspaces");
}

export function createWorkspace(name: string) {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return api.post<import("./types").Workspace>("/api/v1/workspaces", { name, slug });
}

export async function exportConversationsCSV(workspaceId: string): Promise<void> {
  const tokens = getTokens();
  const response = await fetch(
    `${BASE_URL}/api/v1/workspaces/${workspaceId}/conversations/export`,
    { headers: tokens ? { Authorization: `Bearer ${tokens.access_token}` } : {} },
  );
  if (!response.ok) throw new Error("Export failed");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "conversations.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function getAutoRecharge(workspaceId: string) {
  return api.get<{
    auto_recharge_enabled: boolean;
    auto_recharge_threshold: number;
    auto_recharge_amount: number;
  }>(`/api/v1/workspaces/${workspaceId}/billing/auto-recharge`);
}

export function updateAutoRecharge(
  workspaceId: string,
  data: { auto_recharge_enabled: boolean; auto_recharge_threshold: number; auto_recharge_amount: number },
) {
  return api.put(`/api/v1/workspaces/${workspaceId}/billing/auto-recharge`, data);
}

export function getUsageBreakdown(workspaceId: string, days = 30) {
  return api.get<UsageBreakdown>(
    `/api/v1/workspaces/${workspaceId}/billing/usage?days=${days}`,
  );
}

// Webhooks
export type { Webhook } from "./types";

export function getWebhooks(workspaceId: string) {
  return api.get<Webhook[]>(`/api/v1/workspaces/${workspaceId}/webhooks`);
}

export function createWebhook(
  workspaceId: string,
  data: { url: string; event_types: string[]; secret?: string },
) {
  return api.post<Webhook>(`/api/v1/workspaces/${workspaceId}/webhooks`, data);
}

export function deleteWebhook(workspaceId: string, webhookId: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}/webhooks/${webhookId}`);
}

// Invites / Team
export async function getInvites(workspaceId: string): Promise<Invite[]> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/invites`);
  return data as Invite[];
}

export async function createInvite(workspaceId: string, email: string, role: string): Promise<Invite> {
  const data = await api.post(`/api/v1/workspaces/${workspaceId}/invites`, { email, role });
  return data as Invite;
}

export async function deleteInvite(workspaceId: string, inviteId: string): Promise<void> {
  await api.delete(`/api/v1/workspaces/${workspaceId}/invites/${inviteId}`);
}

// Data retention
export async function getDataRetention(workspaceId: string): Promise<{ data_retention_days: number | null }> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/data-retention`);
  return data as { data_retention_days: number | null };
}

export async function updateDataRetention(workspaceId: string, days: number | null): Promise<void> {
  await api.put(`/api/v1/workspaces/${workspaceId}/data-retention`, { data_retention_days: days });
}

// Sentiment by segment
export async function getSentimentBySegment(
  workspaceId: string,
  segment: "chatbot" | "contact",
  days = 30,
): Promise<SegmentSentimentItem[]> {
  const data = await api.get(
    `/api/v1/workspaces/${workspaceId}/sentiment-by-segment?days=${days}&segment=${segment}`,
  );
  return ((data as { data: SegmentSentimentItem[] }).data) ?? [];
}

// LLM Settings (OpenRouter BYOK)
export async function getLLMSettings(workspaceId: string): Promise<LLMSettings> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/llm-settings`);
  return data as LLMSettings;
}

export async function updateLLMSettings(
  workspaceId: string,
  data: { openrouter_api_key?: string; allowed_models: string[] },
): Promise<LLMSettings> {
  const result = await api.put(`/api/v1/workspaces/${workspaceId}/llm-settings`, data);
  return result as LLMSettings;
}

export async function getOpenRouterModels(workspaceId: string): Promise<{ models: OpenRouterModel[] }> {
  const data = await api.get(`/api/v1/workspaces/${workspaceId}/llm-settings/models`);
  return data as { models: OpenRouterModel[] };
}

// Actions
export function getActions(workspaceId: string, chatbotId: string) {
  return api.get<Action[]>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions`);
}

export function createAction(workspaceId: string, chatbotId: string, data: ActionCreate) {
  return api.post<Action>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions`, data);
}

export function updateAction(workspaceId: string, chatbotId: string, actionId: string, data: ActionUpdate) {
  return api.put<Action>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions/${actionId}`, data);
}

export function deleteAction(workspaceId: string, chatbotId: string, actionId: string) {
  return api.delete<void>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/actions/${actionId}`);
}
