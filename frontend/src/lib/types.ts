export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  white_label_enabled?: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

export interface CrawlProgress {
  pages_queued: number;
  pages_discovered: number;
  status: string;
  error_message: string | null;
}

export interface Chatbot {
  id: string;
  name: string;
  display_name: string;
  avatar_url?: string;
  system_prompt?: string;
  tone: string;
  language: string;
  llm_provider: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  confidence_threshold: number;
  retrieval_top_k: number;
  use_reranking: boolean;
  use_hybrid_retrieval: boolean;
  is_active: boolean;
  created_at: string;
  brand_color?: string;
  welcome_message?: string;
  suggested_questions?: string[];
  fallback_message?: string;
  setup_status?: string | null;
  active_crawl_job_id?: string | null;
  crawl_progress?: CrawlProgress | null;
  archived_at?: string | null;
}

export interface CrawlResponse {
  job_id: string;
  kb_id: string;
  pages_discovered: number;
  pages_queued: number;
}

export interface CrawlJobSummary {
  job_id: string;
  status: string;
  root_url: string;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  docs_skipped: number;
  created_at: string;
  completed_at: string | null;
}

export interface CrawlStatusResponse {
  job_id: string;
  status: string;
  phase: string | null;
  error_message: string | null;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  docs_total: number;
  docs_failed: number;
  docs_skipped: number;
  stalled: boolean;
}

export interface IngestionStep {
  step: string;
  status: string;
  started_at: string | null;
  duration_ms: number | null;
  detail: string | null;
  error: string | null;
}

export interface CrawlRunLogItem {
  job_id: string;
  chatbot_id: string | null;
  chatbot_name: string | null;
  root_url: string;
  status: string;
  phase: string | null;
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  docs_indexed: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
export interface CrawlRunLogResponse {
  items: CrawlRunLogItem[];
  total: number;
}

export interface DocumentLogItem {
  id: string;
  title: string | null;
  source_url: string | null;
  source_type: string;
  status: string;
  chunk_count: number;
  last_indexed_at: string | null;
  error_message: string | null;
  ingestion_steps: IngestionStep[] | null;
  knowledge_base_id: string;
  knowledge_base_name: string;
  chatbot_id: string | null;
  chatbot_name: string | null;
}
export interface DocumentLogResponse {
  items: DocumentLogItem[];
  total: number;
}

export interface AnalysisRunLogItem {
  id: string;
  conversation_id: string;
  chatbot_id: string | null;
  chatbot_name: string | null;
  contact_name: string | null;
  sentiment_score: number | null;
  sentiment_label: string | null;
  intent_primary: string | null;
  outcome_category: string | null;
  topics: string[] | null;
  summary: string | null;
  llm_model: string;
  processing_ms: number | null;
  created_at: string;
}
export interface AnalysisRunLogResponse {
  items: AnalysisRunLogItem[];
  total: number;
}

export interface WorkspaceUsage {
  chars_indexed: number;
  chars_limit: number | null;
  chars_remaining: number | null;
  plan: string;
}

export interface AutoConfigResponse {
  name: string;
  welcome_message: string | null;
  system_prompt: string | null;
  suggested_questions: string[] | null;
  fallback_message: string | null;
  brand_color: string | null;
  tone: string | null;
  language: string | null;
}

export interface KnowledgeBase {
  id: string;
  chatbot_id?: string | null;
  name: string;
  kb_type: string;
}

export interface Document {
  id: string;
  knowledge_base_id: string;
  source_type: string;
  source_url?: string;
  title?: string;
  status: string;
  chunk_count: number;
  last_indexed_at?: string;
  sync_frequency?: string;
  metadata_?: Record<string, string>;
}

export interface ChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  heading_path: string | null;
  token_count: number | null;
}

export interface DocumentContentResponse {
  id: string;
  title: string | null;
  source_type: string;
  source_url: string | null;
  status: string;
  error_message: string | null;
  char_count: number;
  chunk_count: number;
  raw_content: string | null;
  chunks: ChunkItem[];
  ingestion_steps: IngestionStep[] | null;
  last_indexed_at: string | null;
}

export interface Article {
  id: string;
  title: string;
  body?: string;
  state: string;
  is_ai_drafted: boolean;
  collection_id?: string;
  author_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  chatbot_id: string;
  contact_email?: string;
  contact_name?: string;
  status: string;
  confidence?: number;
  last_message_preview?: string;
  outcome?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  created_at: string;
}

export interface ChatEvent {
  type: "token" | "done" | "error";
  data: string;
  confidence?: number;
  conversation_id?: string;
}

export interface WidgetConfig {
  primary_color: string;
  position: "bottom-right" | "bottom-left";
  welcome_message: string;
  launcher_text: string;
  avatar_url?: string;
  display_name?: string;
  quick_replies?: string[];
  lead_capture_enabled?: boolean;
  lead_capture_fields?: string[];
  gdpr_consent_enabled?: boolean;
  gdpr_consent_text?: string;
  allowed_domains?: string[];
  auto_open_delay?: number | null;
  persist_conversation?: boolean;
  custom_css?: string | null;
  white_label_enabled?: boolean;
}

export interface Contact {
  id: string;
  email?: string;
  name?: string;
  company_id?: string;
  lead_score: number;
  lead_tier?: string;
  contact_type: string;
  created_at: string;
}

export interface GapCluster {
  id: string;
  topic_label: string;
  topic_keywords: string[];
  gap_count: number;
  representative_query: string;
  status: string;
}

export interface GapClusterDetail extends GapCluster {
  example_queries: string[];
}

export interface DashboardData {
  resolution_rate: number;
  resolution_rate_trend: number;
  stats: {
    total_conversations: number;
    resolved: number;
    escalated: number;
    new_articles: number;
  };
  escalation_breakdown: Record<string, number>;
  resolution_trend: { week_start: string; total: number; resolved: number; rate: number }[];
  intelligence: {
    open_gaps: number;
  };
  feedback: {
    thumbs_up: number;
    thumbs_down: number;
  };
  top_topics: { topic: string; total_count: number; resolved_count: number; resolution_rate: number }[];
  recent_negative_feedback: { id: string; comment: string; created_at: string; message_content: string }[];
}

export interface SentimentDataPoint {
  date: string;
  score: number;
}

export interface SentimentData {
  data_points: SentimentDataPoint[];
  avg_sentiment: number;
  positive_pct: number;
  negative_pct: number;
  trend: number;
}

export interface IntegrationConfig {
  id: string;
  service: string;
  is_connected: boolean;
  config: Record<string, unknown>;
}

export interface BillingPlan {
  id: string;
  name: string;
  price: number;
  interval: string;
  features: string[];
  is_popular?: boolean;
}

export interface CreditBalance {
  balance: number;
  usage_this_month: number;
  usage_history: { date: string; amount: number }[];
}

export interface OnboardingState {
  current_step: number;
  completed: boolean;
  steps: { step: number; name: string; completed: boolean }[];
}

export interface UsageBreakdownItem {
  model: string;
  provider: string;
  tokens: number;
  cost_usd: number;
}

export interface UsageDailyPoint {
  date: string;
  tokens: number;
  cost_usd: number;
}

export interface UsageBreakdown {
  total_tokens: number;
  total_cost_usd: number;
  breakdown: UsageBreakdownItem[];
  daily: UsageDailyPoint[];
}

export interface Invite {
  id: string;
  email: string;
  role: string;
  expires_at?: string;
  accepted_at?: string | null;
  created_at: string;
}

export interface SegmentSentimentItem {
  name: string;
  avg_sentiment: number;
  count: number;
}

export interface Webhook {
  id: string;
  url: string;
  event_types: string[];
  is_active: boolean;
  created_at: string;
}

export interface LLMSettings {
  openrouter_api_key_set: boolean;
  openrouter_base_url: string | null;
  effective_base_url: string | null;
  effective_api_key_set: boolean;
  allowed_models: string[];
}

export interface OpenRouterModel {
  id: string;
  name: string;
  context_length: number | null;
  pricing: { prompt: string; completion: string } | null;
}

export type ActionType =
  | "collect_lead"
  | "webhook"
  | "custom_button"
  | "slack_message"
  | "calendly"
  | "calcom"
  | "custom_tool"
  | "stripe_lookup"
  | "salesforce_ticket";

export interface ActionParameter {
  name: string;
  type: "string" | "number" | "boolean";
  required: boolean;
  description: string;
}

export interface Action {
  id: string;
  chatbot_id: string;
  workspace_id: string;
  action_type: ActionType;
  name: string;
  trigger_description: string;
  config: Record<string, string>;
  is_enabled: boolean;
  parameters: ActionParameter[];
  created_at: string;
}

export interface ActionCreate {
  action_type: ActionType;
  name: string;
  trigger_description: string;
  config: Record<string, string>;
  is_enabled?: boolean;
  parameters?: ActionParameter[];
}

export interface ActionUpdate {
  name?: string;
  trigger_description?: string;
  config?: Record<string, string>;
  is_enabled?: boolean;
  parameters?: ActionParameter[];
}

// Socket.IO event payloads

export interface CrawlProgressEvent {
  job_id: string;
  chatbot_id: string | null;
  phase: "discovering" | "fetching";
  pages_discovered: number;
  pages_queued: number;
  pages_failed: number;
  status: string;
}

export interface CrawlCompletedEvent {
  job_id: string;
  chatbot_id: string | null;
  status: "completed" | "failed";
  pages_queued: number;
  pages_failed: number;
  error_message: string | null;
}

export interface DocumentStatusEvent {
  document_id: string;
  knowledge_base_id: string;
  status: "processing" | "indexed" | "failed" | "skipped";
  char_count: number;
  title: string;
  error_message: string | null;
}

export interface ChatbotStatusEvent {
  chatbot_id: string;
  setup_status: "crawling" | "configuring" | "ready" | "setup_failed";
}

export interface WorkspaceUsageEvent {
  chars_indexed: number;
  chars_limit: number | null;
  plan: string;
}

export interface TaskEvent {
  task_name: string;
  task_id: string;
  detail?: string | null;
  current?: number | null;
  total?: number | null;
  error?: string | null;
}

export interface QAPair {
  id: string;
  chatbot_id: string;
  question: string;
  answer: string | null;
  suggested_answer: string | null;
  status: "pending" | "testing" | "completed" | "failed";
  confidence_score: number | null;
  escalated: boolean;
  sources: Array<{ chunk_id?: string; title?: string }> | null;
  is_edited: boolean;
  kb_document_id: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface QAPairListResponse {
  items: QAPair[];
  total: number;
}
