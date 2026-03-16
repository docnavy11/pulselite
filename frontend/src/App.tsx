import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useDeploymentStore } from './stores/deployment-store'

// Layouts
import DashboardLayout from './app/(dashboard)/layout'
import AuthLayout from './app/(auth)/layout'

// Auth pages
import LoginPage from './app/(auth)/login/page'
import RegisterPage from './app/(auth)/register/page'
import AcceptInvitePage from './app/(auth)/accept-invite/page'

// Dashboard pages
import DashboardPage from './app/(dashboard)/dashboard/page'
import OnboardingPage from './app/(dashboard)/onboarding/page'
import WorkspacesPage from './app/(dashboard)/workspaces/page'

// Chatbot pages
import ChatbotsPage from './app/(dashboard)/chatbots/page'
import NewChatbotPage from './app/(dashboard)/chatbots/new/page'
import ChatbotSetupPage from './app/(dashboard)/chatbots/[id]/setup/page'
import ChatbotLayout from './app/(dashboard)/chatbots/[id]/layout'
import ChatbotDashboardPage from './app/(dashboard)/chatbots/[id]/dashboard/page'
import KnowledgePage from './app/(dashboard)/chatbots/[id]/page'
import ChatbotSettingsPage from './app/(dashboard)/chatbots/[id]/settings/page'
import ActionsPage from './app/(dashboard)/chatbots/[id]/actions/page'
import CustomizePage from './app/(dashboard)/chatbots/[id]/customize/page'
import ChatPage from './app/(dashboard)/chatbots/[id]/chat/page'
import DeployPage from './app/(dashboard)/chatbots/[id]/deploy/page'
import ArticlesPage from './app/(dashboard)/chatbots/[id]/articles/page'
import QAPage from './app/(dashboard)/chatbots/[id]/qa/page'


// Conversation pages
import ConversationsPage from './app/(dashboard)/conversations/page'
import ConversationDetailPage from './app/(dashboard)/conversations/[id]/page'

// Intelligence pages
import IntelligencePage from './app/(dashboard)/intelligence/page'
import SentimentPage from './app/(dashboard)/intelligence/sentiment/page'
import GapsPage from './app/(dashboard)/intelligence/gaps/page'
import GapDetailPage from './app/(dashboard)/intelligence/gaps/[id]/page'

// Article pages
import ArticleDetailPage from './app/(dashboard)/articles/[id]/page'

// Settings pages
import SettingsPage from './app/(dashboard)/settings/page'
import BillingPage from './app/(dashboard)/settings/billing/page'
import DataRetentionPage from './app/(dashboard)/settings/data-retention/page'
import IntegrationsPage from './app/(dashboard)/settings/integrations/page'
import LLMPage from './app/(dashboard)/settings/llm/page'
import SecurityPage from './app/(dashboard)/settings/security/page'
import TeamPage from './app/(dashboard)/settings/team/page'
import WebhooksPage from './app/(dashboard)/settings/webhooks/page'
import IntelligenceSettingsPage from './app/(dashboard)/settings/intelligence/page'

// Logs page
import LogsPage from './app/(dashboard)/logs/page'

// Admin page
import AdminPage from './app/(dashboard)/admin/page'

// Public
import PublicChatPage from './app/chat/[chatbotId]/page'

// Not Found
import NotFoundPage from './app/not-found'

export default function App() {
  const loadConfig = useDeploymentStore((s) => s.loadConfig);
  const isCloud = useDeploymentStore((s) => s.isCloud);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Auth */}
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/accept-invite" element={<AcceptInvitePage />} />
        </Route>

        {/* Dashboard */}
        <Route element={<DashboardLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/workspaces" element={<WorkspacesPage />} />

          <Route path="/chatbots" element={<ChatbotsPage />} />
          <Route path="/chatbots/new" element={<NewChatbotPage />} />
          <Route path="/chatbots/:id/setup" element={<ChatbotSetupPage />} />
          <Route path="/chatbots/:id" element={<ChatbotLayout />}>
            <Route index element={<ChatbotDashboardPage />} />
            <Route path="sources" element={<KnowledgePage />} />
            <Route path="settings" element={<ChatbotSettingsPage />} />
            <Route path="actions" element={<ActionsPage />} />
            <Route path="customize" element={<CustomizePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="deploy" element={<DeployPage />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="qa" element={<QAPage />} />
          </Route>

          <Route path="/conversations" element={<ConversationsPage />} />
          <Route path="/conversations/:id" element={<ConversationDetailPage />} />

          <Route path="/logs" element={<LogsPage />} />
          <Route path="/admin" element={<AdminPage />} />

          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/intelligence/sentiment" element={<SentimentPage />} />
          <Route path="/intelligence/gaps" element={<GapsPage />} />
          <Route path="/intelligence/gaps/:id" element={<GapDetailPage />} />

          <Route path="/articles/:id" element={<ArticleDetailPage />} />

          <Route path="/settings" element={<SettingsPage />} />
          {isCloud && <Route path="/settings/billing" element={<BillingPage />} />}
          <Route path="/settings/data-retention" element={<DataRetentionPage />} />
          <Route path="/settings/integrations" element={<IntegrationsPage />} />
          <Route path="/settings/llm" element={<LLMPage />} />
          <Route path="/settings/security" element={<SecurityPage />} />
          <Route path="/settings/team" element={<TeamPage />} />
          <Route path="/settings/webhooks" element={<WebhooksPage />} />
          <Route path="/settings/intelligence" element={<IntelligenceSettingsPage />} />
        </Route>

        {/* Public chat widget */}
        <Route path="/chat/:chatbotId" element={<PublicChatPage />} />

        {/* 404 catch-all */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
