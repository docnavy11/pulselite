import { api } from "./api";
import { getTokens } from "./auth";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
import {
  DeploymentConfig,
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
  DocumentContentResponse,
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
  WebhookDelivery,
  LLMSettings,
  OpenRouterModel,
  WorkspaceUsage,
  type AnalysisRunLogResponse,
  type CrawlRunLogResponse,
  type DocumentLogResponse,
  type QAPair,
  type QAPairListResponse,
  type RealtimeState,
  type BackgroundTaskLogResponse,
  type WorkerHealth,
} from "./types";

export async function getDeploymentConfig(): Promise<DeploymentConfig> {
  const response = await fetch(`${BASE_URL}/api/v1/config/deployment`);
  return response.json();
}

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

export function archiveChatbot(workspaceId: string, id: string) {
  return api.post<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${id}/archive`, {});
}

export function unarchiveChatbot(workspaceId: string, id: string) {
  return api.post<Chatbot>(`/api/v1/workspaces/${workspaceId}/chatbots/${id}/unarchive`, {});
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

export function previewCrawl(workspaceId: string, url: string) {
  return api.post<{ urls: string[]; source: string }>(`/api/v1/workspaces/${workspaceId}/crawl/preview`, { url });
}

export function startCrawl(
  workspaceId: string,
  url: string,
  includePaths: string[],
  excludePaths: string[],
  chatbotId?: string,
  kbId?: string,
) {
  return api.post<CrawlResponse>(`/api/v1/workspaces/${workspaceId}/crawl`, {
    url,
    include_paths: includePaths,
    exclude_paths: excludePaths,
    chatbot_id: chatbotId,
    knowledge_base_id: kbId,
  });
}

export function getWorkspaceUsage(workspaceId: string) {
  return api.get<WorkspaceUsage>(`/api/v1/workspaces/${workspaceId}/usage`);
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

export async function getCrawlRunLogs(
  workspaceId: string,
  limit = 50,
  offset = 0,
): Promise<CrawlRunLogResponse> {
  return api.get<CrawlRunLogResponse>(
    `/api/v1/workspaces/${workspaceId}/logs/crawl-runs?limit=${limit}&offset=${offset}`,
  );
}

export async function getDocumentLogs(
  workspaceId: string,
  limit = 50,
  offset = 0,
): Promise<DocumentLogResponse> {
  return api.get<DocumentLogResponse>(
    `/api/v1/workspaces/${workspaceId}/logs/documents?limit=${limit}&offset=${offset}`,
  );
}

export async function getAnalysisRunLogs(
  workspaceId: string,
  limit = 50,
  offset = 0,
): Promise<AnalysisRunLogResponse> {
  return api.get<AnalysisRunLogResponse>(
    `/api/v1/workspaces/${workspaceId}/logs/analysis-runs?limit=${limit}&offset=${offset}`,
  );
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

export function getDocumentContent(workspaceId: string, documentId: string) {
  return api.get<DocumentContentResponse>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}/content`,
  );
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
  filters?: { status?: string; chatbot_id?: string; date_from?: string; date_to?: string; limit?: number; topic?: string },
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.chatbot_id) params.set("chatbot_id", filters.chatbot_id);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.topic) params.set("topic", filters.topic);
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
  filters?: { status?: string; chatbot_id?: string },
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.chatbot_id) params.set("chatbot_id", filters.chatbot_id);
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
  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
  const params = new URLSearchParams({ days: String(days) });
  if (chatbotId) params.set("chatbot_id", chatbotId);
  return api.get<DashboardData>(
    `/api/v1/workspaces/${workspaceId}/dashboard?${params}`,
  );
}

// Sentiment
export function getSentimentTrends(workspaceId: string, range: string, chatbotId?: string) {
  const days = range === "7d" ? 7 : range === "90d" ? 90 : 30;
  const params = new URLSearchParams({ days: String(days) });
  if (chatbotId) params.set("chatbot_id", chatbotId);
  return api
    .get<{ data: { date: string; avg_sentiment: number | null; count: number }[] }>(
      `/api/v1/workspaces/${workspaceId}/sentiment-trends?${params}`,
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
  integrationType: string,
  config: Record<string, unknown>,
) {
  return api.put<IntegrationConfig>(
    `/api/v1/workspaces/${workspaceId}/integrations/${integrationType}`,
    config,
  );
}

export function testIntegration(workspaceId: string, integrationType: string) {
  return api.post<{ success: boolean; detail: string }>(
    `/api/v1/workspaces/${workspaceId}/integrations/${integrationType}/test`,
  ).then((r) => ({ success: r.success, message: r.detail }));
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

export function updateWorkspace(workspaceId: string, data: { name?: string; timezone?: string }) {
  return api.patch<import("./types").Workspace>(`/api/v1/workspaces/${workspaceId}`, data);
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

export function getWebhookDeliveries(
  workspaceId: string,
  webhookId: string,
  params?: { status?: string; limit?: number; offset?: number },
) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status_filter", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return api.get<{ items: WebhookDelivery[]; total: number }>(
    `/api/v1/workspaces/${workspaceId}/webhooks/${webhookId}/deliveries${qs ? `?${qs}` : ""}`,
  );
}

export function retryWebhookDelivery(
  workspaceId: string,
  webhookId: string,
  deliveryId: string,
) {
  return api.post<WebhookDelivery>(
    `/api/v1/workspaces/${workspaceId}/webhooks/${webhookId}/deliveries/${deliveryId}/retry`,
    {},
  );
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
  data: { openrouter_api_key?: string; openrouter_base_url?: string | null; allowed_models?: string[]; internal_model?: string | null },
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

// Intelligence triggers (manual/dev)
export function triggerAnalyzeAll(workspaceId: string) {
  return api.post<{ status: string; conversations_queued: number }>(
    `/api/v1/workspaces/${workspaceId}/intelligence/trigger/analyze-all`
  );
}

export function triggerSentimentTrends(workspaceId: string) {
  return api.post<{ status: string }>(
    `/api/v1/workspaces/${workspaceId}/intelligence/trigger/sentiment-trends`
  );
}

export function triggerClusterGaps(workspaceId: string) {
  return api.post<{ status: string }>(
    `/api/v1/workspaces/${workspaceId}/intelligence/trigger/cluster-gaps`
  );
}

// Intelligence config (admin)
export interface IntelligenceConfig {
  auto_analyze: boolean;
  sentiment_trends: boolean;
  gap_clustering: boolean;
  report_frequency: string;
  report_recipients: string[];
  report_sections: Record<string, boolean>;
}

export function getIntelligenceConfig(workspaceId: string) {
  return api.get<IntelligenceConfig>(
    `/api/v1/workspaces/${workspaceId}/intelligence/config`
  );
}

export function updateIntelligenceConfig(workspaceId: string, config: Partial<IntelligenceConfig>) {
  return api.put<IntelligenceConfig>(
    `/api/v1/workspaces/${workspaceId}/intelligence/config`,
    config
  );
}

// ── Q&A Pairs ──────────────────────────────────────────────────

export async function getQAPairs(
  workspaceId: string,
  chatbotId: string,
  params?: { page?: number; page_size?: number; status_filter?: string },
): Promise<QAPairListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.status_filter) query.set("status_filter", params.status_filter);
  const qs = query.toString();
  return api.get<QAPairListResponse>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa${qs ? `?${qs}` : ""}`);
}

export async function createQAPair(
  workspaceId: string,
  chatbotId: string,
  question: string,
): Promise<QAPair> {
  return api.post<QAPair>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa`, { question });
}

export async function generateQAPairs(
  workspaceId: string,
  chatbotId: string,
  count: number = 10,
): Promise<{ status: string; count: number }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/generate`, { count });
}

export async function runQATests(
  workspaceId: string,
  chatbotId: string,
): Promise<{ status: string; count: number }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/run-tests`);
}

export async function retestAllQAPairs(
  workspaceId: string,
  chatbotId: string,
): Promise<{ status: string; count: number }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/retest-all`);
}

export async function updateQAPair(
  workspaceId: string,
  chatbotId: string,
  pairId: string,
  data: { question?: string; answer?: string },
): Promise<QAPair> {
  return api.put<QAPair>(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/${pairId}`, data);
}

export async function deleteQAPair(
  workspaceId: string,
  chatbotId: string,
  pairId: string,
): Promise<void> {
  return api.delete(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/${pairId}`);
}

export async function suggestQAAnswer(
  workspaceId: string,
  chatbotId: string,
  pairId: string,
): Promise<{ status: string }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/${pairId}/suggest`);
}

export async function retestQAPair(
  workspaceId: string,
  chatbotId: string,
  pairId: string,
): Promise<{ status: string }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/${pairId}/retest`);
}

export async function addQAPairToKB(
  workspaceId: string,
  chatbotId: string,
  pairId: string,
): Promise<{ status: string; document_id: string }> {
  return api.post(`/api/v1/workspaces/${workspaceId}/chatbots/${chatbotId}/qa/${pairId}/add-to-kb`);
}

// Realtime state
export function getRealtimeState(workspaceId: string) {
  return api.get<RealtimeState>(`/api/v1/workspaces/${workspaceId}/realtime/state`);
}

// Background task logs
export function getBackgroundTaskLogs(
  workspaceId: string,
  limit = 50,
  offset = 0,
  taskName?: string,
  status?: string,
) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (taskName) params.set("task_name", taskName);
  if (status) params.set("status", status);
  return api.get<BackgroundTaskLogResponse>(
    `/api/v1/workspaces/${workspaceId}/realtime/logs?${params}`,
  );
}

// Worker health
export function getWorkerHealth(workspaceId: string, window: "1h" | "24h" | "7d" = "24h") {
  return api.get<WorkerHealth>(
    `/api/v1/workspaces/${workspaceId}/workers/health?window=${window}`,
  );
}
