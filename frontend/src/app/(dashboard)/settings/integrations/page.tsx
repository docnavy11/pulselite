import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, X, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { IntegrationConfig } from "@/lib/types";
import {
  getIntegrations,
  updateIntegration,
  testIntegration,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const integrationMeta: Record<
  string,
  { name: string; description: string; icon: string }
> = {
  slack: {
    name: "Slack",
    description: "Get escalation alerts and weekly digests in Slack.",
    icon: "#",
  },
  email: {
    name: "Email",
    description: "Send escalation notifications and reports via email (Resend or SMTP).",
    icon: "@",
  },
  hubspot: {
    name: "HubSpot",
    description: "Auto-push qualified leads to HubSpot CRM.",
    icon: "H",
  },
  linear: {
    name: "Linear",
    description: "Push feature requests as Linear issues.",
    icon: "L",
  },
  jira: {
    name: "Jira",
    description: "Push feature requests as Jira tickets.",
    icon: "J",
  },
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function IntegrationsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [integrations, setIntegrations] = useState<IntegrationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<{
    id: string;
    success: boolean;
    message: string;
  } | null>(null);
  const [notionConnectedBanner, setNotionConnectedBanner] = useState(false);
  const [slackConnectedBanner, setSlackConnectedBanner] = useState(false);
  const [shopifyConnectedBanner, setShopifyConnectedBanner] = useState(false);
  const [googleDriveConnectedBanner, setGoogleDriveConnectedBanner] = useState(false);
  const [zendeskConnectedBanner, setZendeskConnectedBanner] = useState(false);
  const [salesforceConnectedBanner, setSalesforceConnectedBanner] = useState(false);
  const [dropboxConnectedBanner, setDropboxConnectedBanner] = useState(false);

  const [searchParams] = useSearchParams();

  useEffect(() => {
    if (searchParams.get("notion_connected") === "1") {
      setNotionConnectedBanner(true);
      const timer = setTimeout(() => setNotionConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("slack_connected") === "1") {
      setSlackConnectedBanner(true);
      const timer = setTimeout(() => setSlackConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("shopify_connected") === "1") {
      setShopifyConnectedBanner(true);
      const timer = setTimeout(() => setShopifyConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("connected") === "google_drive") {
      setGoogleDriveConnectedBanner(true);
      const timer = setTimeout(() => setGoogleDriveConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("connected") === "zendesk") {
      setZendeskConnectedBanner(true);
      const timer = setTimeout(() => setZendeskConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("connected") === "salesforce") {
      setSalesforceConnectedBanner(true);
      const timer = setTimeout(() => setSalesforceConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
    if (searchParams.get("connected") === "dropbox") {
      setDropboxConnectedBanner(true);
      const timer = setTimeout(() => setDropboxConnectedBanner(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    getIntegrations(workspace.id)
      .then(setIntegrations)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  async function handleSave(
    integration: IntegrationConfig,
    config: Record<string, unknown>,
  ) {
    if (!workspace) return;
    setSaving(true);
    try {
      const updated = await updateIntegration(
        workspace.id,
        integration.id,
        config,
      );
      setIntegrations((prev) =>
        prev.map((i) => (i.id === integration.id ? updated : i)),
      );
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handleChannelSave(
    integrationType: string,
    config: Record<string, unknown>,
  ) {
    if (!workspace) return;
    setSaving(true);
    try {
      await updateIntegration(workspace.id, integrationType, { config, is_active: true });
      // Re-fetch integrations to pick up new record
      const updated = await getIntegrations(workspace.id);
      setIntegrations(updated);
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(integrationId: string) {
    if (!workspace) return;
    try {
      const result = await testIntegration(workspace.id, integrationId);
      setTestResult({ id: integrationId, ...result });
      setTimeout(() => setTestResult(null), 3000);
    } catch {
      setTestResult({
        id: integrationId,
        success: false,
        message: "Test failed",
      });
    }
  }

  // Find the Stripe integration
  const stripeIntegration = integrations.find((i) => i.service === "stripe");
  const stripeConnected = stripeIntegration?.is_connected ?? false;

  // Find channel integrations from the loaded list
  const shopifyIntegration = integrations.find((i) => i.service === "shopify");
  const shopifyConnected = shopifyIntegration?.is_connected ?? false;
  const shopifyShop = (shopifyIntegration?.config?.shop as string) || "";

  const whatsappIntegration = integrations.find((i) => i.service === "whatsapp");
  const messengerIntegration = integrations.find((i) => i.service === "messenger");
  const instagramIntegration = integrations.find((i) => i.service === "instagram");

  // Find the Notion integration from the loaded list
  const notionIntegration = integrations.find(
    (i) => i.service === "notion",
  );
  const notionConnected = notionIntegration?.is_connected ?? false;
  const notionWorkspaceName =
    (notionIntegration?.config?.workspace_name as string) || "";

  // Find the Google Drive integration
  const googleDriveIntegration = integrations.find(
    (i) => i.service === "google_drive",
  );
  const googleDriveConnected = googleDriveIntegration?.is_connected ?? false;

  // Find the Zendesk integration
  const zendeskIntegration = integrations.find(
    (i) => i.service === "zendesk",
  );
  const zendeskConnected = zendeskIntegration?.is_connected ?? false;
  const zendeskSubdomain =
    (zendeskIntegration?.config?.subdomain as string) || "";

  // Find the Salesforce integration
  const salesforceIntegration = integrations.find(
    (i) => i.service === "salesforce",
  );
  const salesforceConnected = salesforceIntegration?.is_connected ?? false;
  const salesforceInstanceUrl =
    (salesforceIntegration?.config?.instance_url as string) || "";

  // Find the Dropbox integration
  const dropboxIntegration = integrations.find(
    (i) => i.service === "dropbox",
  );
  const dropboxConnected = dropboxIntegration?.is_connected ?? false;

  // Find the Slack Bot integration
  const slackBotIntegration = integrations.find(
    (i) => i.service === "slack_bot",
  );
  const slackBotConnected = slackBotIntegration?.is_connected ?? false;
  const slackTeamName =
    (slackBotIntegration?.config?.team_name as string) || "";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Integrations</h1>

      {notionConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Notion connected successfully! You can now add Notion pages to your
          knowledge base using their page URL.
        </div>
      )}

      {slackConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Slack bot connected successfully! Users can now message your bot
          directly in Slack.
        </div>
      )}

      {shopifyConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Shopify connected! The Pulse widget has been injected into your
          storefront.
        </div>
      )}

      {googleDriveConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Google Drive connected successfully! You can now add Google Docs or
          folder URLs to your knowledge base.
        </div>
      )}

      {zendeskConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Zendesk connected successfully! You can now ingest your Help Center
          articles into the knowledge base.
        </div>
      )}

      {salesforceConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Salesforce connected successfully! You can now ingest Knowledge
          articles and use Salesforce AI actions in your chatbots.
        </div>
      )}

      {dropboxConnectedBanner && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
          <Check className="h-4 w-4 flex-shrink-0" />
          Dropbox connected successfully! You can now ingest text files from
          your Dropbox into the knowledge base.
        </div>
      )}

      {/* Notion section */}
      <div className="mb-6 max-w-2xl">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Knowledge Base Sources
        </h2>
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
                  N
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Notion
                    </h3>
                    <Badge variant={notionConnected ? "success" : "default"}>
                      {notionConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {notionConnected && notionWorkspaceName
                      ? `Connected to "${notionWorkspaceName}" — paste Notion page URLs to ingest them into the knowledge base.`
                      : "Connect your Notion workspace to ingest Notion pages into the knowledge base."}
                  </p>
                </div>
              </div>
              {notionConnected ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    Re-authorize to update
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (workspace) {
                        window.location.href = `${API_URL}/api/v1/oauth/notion/authorize?workspace_id=${workspace.id}`;
                      }
                    }}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (workspace) {
                      window.location.href = `${API_URL}/api/v1/oauth/notion/authorize?workspace_id=${workspace.id}`;
                    }
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  Connect Notion
                </Button>
              )}
            </div>
            {notionConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                To add a Notion page to your knowledge base, copy the page URL
                from your browser (e.g.{" "}
                <code className="font-mono">
                  https://notion.so/My-Page-abc123...
                </code>
                ) and paste it as the source URL when adding a new document.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Google Drive */}
        <Card className="mt-4">
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
                  G
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Google Drive
                    </h3>
                    <Badge variant={googleDriveConnected ? "success" : "default"}>
                      {googleDriveConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {googleDriveConnected
                      ? "Connected — paste Google Doc or folder URLs to ingest them into the knowledge base."
                      : "Connect your Google account to ingest Google Docs and Drive files into the knowledge base."}
                  </p>
                </div>
              </div>
              {googleDriveConnected ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    Re-authorize to update
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (workspace) {
                        window.location.href = `${API_URL}/api/v1/oauth/google/authorize?workspace_id=${workspace.id}`;
                      }
                    }}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (workspace) {
                      window.location.href = `${API_URL}/api/v1/oauth/google/authorize?workspace_id=${workspace.id}`;
                    }
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  Connect Google Drive
                </Button>
              )}
            </div>
            {googleDriveConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                To add a Google Doc, copy its URL from the browser (e.g.{" "}
                <code className="font-mono">
                  https://docs.google.com/document/d/...
                </code>
                ) and paste it as the source URL when adding a new document.
                You can also paste a Google Drive folder URL to ingest all
                Docs in that folder.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Dropbox */}
        <Card className="mt-4">
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-lg font-bold text-blue-700">
                  D
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Dropbox
                    </h3>
                    <Badge variant={dropboxConnected ? "success" : "default"}>
                      {dropboxConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {dropboxConnected
                      ? "Connected — enter a folder path to ingest text files into the knowledge base."
                      : "Connect your Dropbox account to ingest text files into the knowledge base."}
                  </p>
                </div>
              </div>
              {dropboxConnected ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    Re-authorize to update
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (workspace) {
                        window.location.href = `${API_URL}/api/v1/oauth/dropbox/authorize?workspace_id=${workspace.id}`;
                      }
                    }}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (workspace) {
                      window.location.href = `${API_URL}/api/v1/oauth/dropbox/authorize?workspace_id=${workspace.id}`;
                    }
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  Connect Dropbox
                </Button>
              )}
            </div>
            {dropboxConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                Enter a Dropbox folder path (e.g.{" "}
                <code className="font-mono">/My Knowledge Base</code>) or leave
                blank for root when adding a new document source. Supported
                file types: .txt, .md, .csv, .rst.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Zendesk */}
        <Card className="mt-4">
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-lg font-bold text-green-700">
                  Z
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Zendesk
                    </h3>
                    <Badge variant={zendeskConnected ? "success" : "default"}>
                      {zendeskConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {zendeskConnected && zendeskSubdomain
                      ? `Connected to ${zendeskSubdomain}.zendesk.com — add Zendesk sources to ingest all Help Center articles.`
                      : "Connect your Zendesk account to ingest Help Center articles into the knowledge base."}
                  </p>
                </div>
              </div>
              <ZendeskConnectButton
                workspace={workspace}
                connected={zendeskConnected}
              />
            </div>
            {zendeskConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                To ingest your Zendesk Help Center articles, go to your
                knowledge base and add a new source with type{" "}
                <strong>Zendesk</strong>. All published articles will be
                imported automatically.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Salesforce */}
        <Card className="mt-4">
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-sm font-bold text-blue-700">
                  SF
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Salesforce
                    </h3>
                    <Badge variant={salesforceConnected ? "success" : "default"}>
                      {salesforceConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {salesforceConnected && salesforceInstanceUrl
                      ? `Connected to ${salesforceInstanceUrl} — ingest Knowledge articles and use AI actions for contact lookup and case creation.`
                      : "Connect your Salesforce org to ingest Knowledge articles and enable AI actions for contact lookup and case creation."}
                  </p>
                </div>
              </div>
              {salesforceConnected ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    Re-authorize to update
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (workspace) {
                        window.location.href = `/api/v1/oauth/salesforce/authorize?workspace_id=${workspace.id}`;
                      }
                    }}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (workspace) {
                      window.location.href = `/api/v1/oauth/salesforce/authorize?workspace_id=${workspace.id}`;
                    }
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  Connect Salesforce
                </Button>
              )}
            </div>
            {salesforceConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                To ingest your Salesforce Knowledge articles, go to your
                knowledge base and add a new source with type{" "}
                <strong>Salesforce</strong>. All published articles will be
                imported automatically. You can also enable{" "}
                <strong>Salesforce AI actions</strong> on your chatbot to look
                up contacts and create cases mid-conversation.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Slack Bot section */}
      <div className="mb-6 max-w-2xl">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Slack Bot
        </h2>
        <Card>
          <CardContent className="py-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
                  #
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Slack Bot
                    </h3>
                    <Badge variant={slackBotConnected ? "success" : "default"}>
                      {slackBotConnected ? "Connected" : "Not connected"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {slackBotConnected && slackTeamName
                      ? `Connected to "${slackTeamName}" — users can message your bot directly in Slack DMs and channels.`
                      : "Install the Pulse bot in your Slack workspace so users can chat with the AI in DMs and channels."}
                  </p>
                </div>
              </div>
              {slackBotConnected ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    Re-authorize to update
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (workspace) {
                        window.location.href = `${API_URL}/api/v1/oauth/slack/authorize?workspace_id=${workspace.id}`;
                      }
                    }}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  onClick={() => {
                    if (workspace) {
                      window.location.href = `${API_URL}/api/v1/oauth/slack/authorize?workspace_id=${workspace.id}`;
                    }
                  }}
                >
                  <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                  Connect Slack Bot
                </Button>
              )}
            </div>
            {slackBotConnected && (
              <div className="mt-3 rounded-md bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
                After connecting, users can message your bot directly in Slack.
                The bot will respond to DMs and{" "}
                <code className="font-mono">@mentions</code> in channels using
                your AI knowledge base.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Messaging Channels */}
      <div className="mb-6 max-w-2xl">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Messaging Channels
        </h2>
        <div className="space-y-4">
          {/* WhatsApp */}
          <ChannelWebhookCard
            icon="W"
            name="WhatsApp Business"
            description="Receive and reply to WhatsApp messages via the Pulse AI."
            integration={whatsappIntegration}
            fields={[
              { key: "phone_number_id", label: "Phone Number ID" },
              { key: "access_token", label: "Access Token", secret: true },
            ]}
            webhookUrl={`${API_URL}/api/v1/whatsapp/webhook`}
            onSave={(config) => handleChannelSave("whatsapp", config)}
            saving={saving}
          />

          {/* Messenger */}
          <ChannelWebhookCard
            icon="M"
            name="Facebook Messenger"
            description="Answer Messenger conversations from your Facebook Page."
            integration={messengerIntegration}
            fields={[
              { key: "page_id", label: "Facebook Page ID" },
              { key: "page_access_token", label: "Page Access Token", secret: true },
            ]}
            webhookUrl={`${API_URL}/api/v1/messenger/webhook`}
            onSave={(config) => handleChannelSave("messenger", config)}
            saving={saving}
          />

          {/* Instagram */}
          <ChannelWebhookCard
            icon="I"
            name="Instagram DMs"
            description="Reply to Instagram Direct Messages with the Pulse AI."
            integration={instagramIntegration}
            fields={[
              { key: "account_id", label: "Instagram Business Account ID" },
              { key: "page_access_token", label: "Page Access Token", secret: true },
            ]}
            webhookUrl={`${API_URL}/api/v1/instagram/webhook`}
            onSave={(config) => handleChannelSave("instagram", config)}
            saving={saving}
          />

          {/* Shopify */}
          <Card>
            <CardContent className="py-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
                    S
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-gray-900">Shopify</h3>
                      <Badge variant={shopifyConnected ? "success" : "default"}>
                        {shopifyConnected ? "Connected" : "Not connected"}
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {shopifyConnected && shopifyShop
                        ? `Connected to ${shopifyShop} — Pulse widget injected into your storefront.`
                        : "Connect your Shopify store to auto-inject the Pulse widget on your storefront."}
                    </p>
                  </div>
                </div>
                <ShopifyConnectButton workspace={workspace} connected={shopifyConnected} />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Stripe section */}
      <div className="mb-6 max-w-2xl">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Payments
        </h2>
        <StripeCard
          connected={stripeConnected}
          onSave={(secretKey) => handleChannelSave("stripe", { secret_key: secretKey })}
          saving={saving}
        />
      </div>

      {/* Other integrations */}
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 max-w-2xl">
        Notifications &amp; CRM
      </h2>
      <div className="grid grid-cols-1 gap-4 max-w-2xl">
        {integrations
          .filter((i) => i.service !== "notion")
          .map((integration) => {
            const meta = integrationMeta[integration.service] || {
              name: integration.service,
              description: "",
              icon: "?",
            };
            const isExpanded = expandedId === integration.id;

            return (
              <Card key={integration.id}>
                <CardContent className="py-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
                        {meta.icon}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900">
                            {meta.name}
                          </h3>
                          <Badge
                            variant={
                              integration.is_connected ? "success" : "default"
                            }
                          >
                            {integration.is_connected
                              ? "Connected"
                              : "Not connected"}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {meta.description}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setExpandedId(isExpanded ? null : integration.id)
                      }
                    >
                      Configure
                    </Button>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
                      {integration.service === "slack" && (
                        <SlackConfig
                          integration={integration}
                          onSave={(c) => handleSave(integration, c)}
                          onTest={() => handleTest(integration.id)}
                          saving={saving}
                          testResult={
                            testResult?.id === integration.id
                              ? testResult
                              : null
                          }
                        />
                      )}
                      {integration.service === "email" && (
                        <EmailConfig
                          integration={integration}
                          onSave={(c) => handleSave(integration, c)}
                          saving={saving}
                        />
                      )}
                      {integration.service === "hubspot" && (
                        <HubspotConfig
                          integration={integration}
                          onSave={(c) => handleSave(integration, c)}
                          saving={saving}
                        />
                      )}
                      {(integration.service === "linear" ||
                        integration.service === "jira") && (
                        <GenericApiConfig
                          integration={integration}
                          onSave={(c) => handleSave(integration, c)}
                          saving={saving}
                        />
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
      </div>
    </div>
  );
}

function SlackConfig({
  integration,
  onSave,
  onTest,
  saving,
  testResult,
}: {
  integration: IntegrationConfig;
  onSave: (c: Record<string, unknown>) => void;
  onTest: () => void;
  saving: boolean;
  testResult: { success: boolean; message: string } | null;
}) {
  const [webhookUrl, setWebhookUrl] = useState(
    (integration.config.webhook_url as string) || "",
  );
  const [alertMinConf, setAlertMinConf] = useState<number | undefined>(
    (integration.config.alert_max_confidence ?? integration.config.alert_min_confidence) != null
      ? ((integration.config.alert_max_confidence ?? integration.config.alert_min_confidence) as number)
      : undefined,
  );

  return (
    <>
      <Input
        label="Webhook URL"
        value={webhookUrl}
        onChange={(e) => setWebhookUrl(e.target.value)}
        placeholder="https://hooks.slack.com/services/..."
      />
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          Alert only when confidence below (0–1, leave blank to always alert)
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          placeholder="e.g. 0.4"
          value={alertMinConf ?? ""}
          onChange={(e) =>
            setAlertMinConf(
              e.target.value === "" ? undefined : parseFloat(e.target.value),
            )
          }
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <p className="text-xs text-gray-400 mt-1">
          Leave blank to alert on every escalation.
        </p>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() =>
            onSave({
              webhook_url: webhookUrl,
              ...(alertMinConf !== undefined && { alert_max_confidence: alertMinConf }),
            })
          }
          loading={saving}
        >
          Save
        </Button>
        <Button variant="secondary" size="sm" onClick={onTest}>
          Test
        </Button>
      </div>
      {testResult && (
        <div
          className={`flex items-center gap-1 text-sm ${testResult.success ? "text-green-600" : "text-red-600"}`}
        >
          {testResult.success ? (
            <Check className="h-4 w-4" />
          ) : (
            <X className="h-4 w-4" />
          )}
          {testResult.message}
        </div>
      )}
    </>
  );
}

function EmailConfig({
  integration,
  onSave,
  saving,
}: {
  integration: IntegrationConfig;
  onSave: (c: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [provider, setProvider] = useState(
    (integration.config.provider as string) || "resend",
  );
  const [apiKey, setApiKey] = useState(
    (integration.config.api_key as string) || "",
  );
  const [host, setHost] = useState(
    (integration.config.host as string) || "",
  );
  const [port, setPort] = useState(
    (integration.config.port as number) || 587,
  );
  const [username, setUsername] = useState(
    (integration.config.username as string) || "",
  );
  const [password, setPassword] = useState(
    (integration.config.password as string) || "",
  );
  const [tls, setTls] = useState(
    integration.config.tls !== false,
  );
  const [toEmail, setToEmail] = useState(
    (integration.config.to_email as string) || "",
  );
  const [fromEmail, setFromEmail] = useState(
    (integration.config.from_email as string) || "Pulse <notifications@pulse.app>",
  );
  const [appUrl, setAppUrl] = useState(
    (integration.config.app_url as string) || "",
  );
  const [alertMinConf, setAlertMinConf] = useState<number | undefined>(
    (integration.config.alert_max_confidence ?? integration.config.alert_min_confidence) != null
      ? ((integration.config.alert_max_confidence ?? integration.config.alert_min_confidence) as number)
      : undefined,
  );

  function handleSave() {
    const base: Record<string, unknown> = {
      provider,
      to_email: toEmail,
      from_email: fromEmail,
      ...(appUrl && { app_url: appUrl }),
      ...(alertMinConf !== undefined && { alert_max_confidence: alertMinConf }),
    };
    if (provider === "resend") {
      base.api_key = apiKey;
    } else {
      base.host = host;
      base.port = port;
      base.username = username;
      base.password = password;
      base.tls = tls;
    }
    onSave(base);
  }

  return (
    <>
      {/* Provider selector */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Provider</label>
        <div className="flex gap-2">
          {(["resend", "smtp"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setProvider(p)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                provider === p
                  ? "bg-primary-50 border-primary-300 text-primary-700"
                  : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50"
              }`}
            >
              {p === "resend" ? "Resend" : "SMTP"}
            </button>
          ))}
        </div>
      </div>

      {/* Provider-specific fields */}
      {provider === "resend" ? (
        <Input
          label="Resend API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="re_..."
          type="password"
        />
      ) : (
        <>
          <Input
            label="SMTP Host"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="smtp.example.com"
          />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Port</label>
              <input
                type="number"
                value={port}
                onChange={(e) => setPort(parseInt(e.target.value) || 587)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={tls}
                  onChange={(e) => setTls(e.target.checked)}
                  className="rounded border-gray-300"
                />
                TLS
              </label>
            </div>
          </div>
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="user@example.com"
          />
          <Input
            label="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="••••••••"
          />
        </>
      )}

      {/* Common fields */}
      <Input
        label="Send Alerts To"
        value={toEmail}
        onChange={(e) => setToEmail(e.target.value)}
        placeholder="you@yourcompany.com"
      />
      <Input
        label="From Address"
        value={fromEmail}
        onChange={(e) => setFromEmail(e.target.value)}
        placeholder="Pulse <notifications@pulse.app>"
      />
      <Input
        label="App URL (for links in emails)"
        value={appUrl}
        onChange={(e) => setAppUrl(e.target.value)}
        placeholder="https://app.pulse.dev"
      />
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">
          Alert only when confidence below (0-1, leave blank to always alert)
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          placeholder="e.g. 0.4"
          value={alertMinConf ?? ""}
          onChange={(e) =>
            setAlertMinConf(
              e.target.value === "" ? undefined : parseFloat(e.target.value),
            )
          }
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <p className="text-xs text-gray-400 mt-1">
          Leave blank to alert on every escalation.
        </p>
      </div>
      <Button size="sm" onClick={handleSave} loading={saving}>
        Save
      </Button>
    </>
  );
}

function HubspotConfig({
  integration,
  onSave,
  saving,
}: {
  integration: IntegrationConfig;
  onSave: (c: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [apiKey, setApiKey] = useState(
    (integration.config.api_key as string) || "",
  );

  return (
    <>
      <Input
        label="API Key"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="pat-..."
        type="password"
      />
      <Button
        size="sm"
        onClick={() => onSave({ api_key: apiKey })}
        loading={saving}
      >
        Save
      </Button>
    </>
  );
}

function GenericApiConfig({
  integration,
  onSave,
  saving,
}: {
  integration: IntegrationConfig;
  onSave: (c: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [token, setToken] = useState(
    (integration.config.api_token as string) || "",
  );
  const [project, setProject] = useState(
    (integration.config.default_project as string) || "",
  );

  return (
    <>
      <Input
        label="API Token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        type="password"
      />
      <Input
        label="Default Project"
        value={project}
        onChange={(e) => setProject(e.target.value)}
        placeholder="Project key or ID"
      />
      <Button
        size="sm"
        onClick={() =>
          onSave({ api_token: token, default_project: project })
        }
        loading={saving}
      >
        Save
      </Button>
    </>
  );
}

// ChannelWebhookCard — generic card for webhook-based channel integrations
function ChannelWebhookCard({
  icon,
  name,
  description,
  integration,
  fields,
  webhookUrl,
  onSave,
  saving,
}: {
  icon: string;
  name: string;
  description: string;
  integration: IntegrationConfig | undefined;
  fields: { key: string; label: string; secret?: boolean }[];
  webhookUrl: string;
  onSave: (config: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    fields.forEach((f) => {
      init[f.key] = (integration?.config?.[f.key] as string) || "";
    });
    return init;
  });

  const isConnected = integration?.is_connected ?? false;

  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-lg font-bold text-gray-600">
              {icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-gray-900">{name}</h3>
                <Badge variant={isConnected ? "success" : "default"}>
                  {isConnected ? "Connected" : "Not connected"}
                </Badge>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">{description}</p>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setExpanded((v) => !v)}
          >
            Configure
          </Button>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
            {fields.map((f) => (
              <Input
                key={f.key}
                label={f.label}
                type={f.secret ? "password" : "text"}
                value={values[f.key]}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [f.key]: e.target.value }))
                }
              />
            ))}
            <div className="rounded-md bg-gray-50 border border-gray-200 px-3 py-2 text-xs text-gray-600 font-mono break-all">
              Webhook URL: {webhookUrl}
            </div>
            <Button size="sm" onClick={() => onSave(values)} loading={saving}>
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StripeCard({
  connected,
  onSave,
  saving,
}: {
  connected: boolean;
  onSave: (secretKey: string) => void;
  saving: boolean;
}) {
  const [secretKey, setSecretKey] = useState("");
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-lg font-bold text-primary-600">
              $
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-gray-900">Stripe</h3>
                <Badge variant={connected ? "success" : "default"}>
                  {connected ? "Connected" : "Not connected"}
                </Badge>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                {connected
                  ? "Connected — the AI can look up customer invoices and subscriptions mid-conversation."
                  : "Add your Stripe secret key to let the AI look up customer invoices and subscription info."}
              </p>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setExpanded((v) => !v)}>
            {connected ? "Update" : "Configure"}
          </Button>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
            <Input
              label="Stripe Secret Key"
              type="password"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              placeholder="sk_live_..."
            />
            <p className="text-xs text-gray-400">
              Use a Restricted Key with read-only access to Customers, Invoices, and Subscriptions for least privilege.
            </p>
            <Button
              size="sm"
              onClick={() => {
                onSave(secretKey);
                setSecretKey("");
                setExpanded(false);
              }}
              loading={saving}
              disabled={!secretKey}
            >
              Save
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ShopifyConnectButton({
  workspace,
  connected,
}: {
  workspace: { id: string } | null;
  connected: boolean;
}) {
  const [shop, setShop] = useState("");
  const [showInput, setShowInput] = useState(false);

  if (!showInput && !connected) {
    return (
      <Button size="sm" onClick={() => setShowInput(true)}>
        <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
        Connect Shopify
      </Button>
    );
  }

  if (connected) {
    return (
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setShowInput(true)}
      >
        Reconnect
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        placeholder="mystore.myshopify.com"
        value={shop}
        onChange={(e) => setShop(e.target.value)}
        className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 w-52"
      />
      <Button
        size="sm"
        onClick={() => {
          if (workspace && shop) {
            window.location.href = `${API_URL}/api/v1/oauth/shopify/authorize?shop=${encodeURIComponent(shop)}&workspace_id=${workspace.id}`;
          }
        }}
        disabled={!shop}
      >
        Connect
      </Button>
    </div>
  );
}

function ZendeskConnectButton({
  workspace,
  connected,
}: {
  workspace: { id: string } | null;
  connected: boolean;
}) {
  const [subdomain, setSubdomain] = useState("");
  const [showInput, setShowInput] = useState(false);

  if (!showInput && !connected) {
    return (
      <Button size="sm" onClick={() => setShowInput(true)}>
        <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
        Connect Zendesk
      </Button>
    );
  }

  if (connected) {
    return (
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setShowInput(true)}
      >
        Reconnect
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        placeholder="mycompany"
        value={subdomain}
        onChange={(e) => setSubdomain(e.target.value)}
        className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 w-40"
      />
      <span className="text-xs text-gray-400 whitespace-nowrap">.zendesk.com</span>
      <Button
        size="sm"
        onClick={() => {
          if (workspace && subdomain.trim()) {
            window.location.href = `${API_URL}/api/v1/oauth/zendesk/authorize?workspace_id=${workspace.id}&subdomain=${encodeURIComponent(subdomain.trim())}`;
          }
        }}
        disabled={!subdomain.trim()}
      >
        Connect
      </Button>
    </div>
  );
}
