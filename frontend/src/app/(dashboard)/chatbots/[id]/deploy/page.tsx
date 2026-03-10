"use client";

import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { clsx } from "clsx";
import { Copy, Check, Plus, Trash2, Key } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { Highlight, themes } from "prism-react-renderer";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { ApiKey, ApiKeyCreated } from "@/lib/types";
import { getApiKeys, createApiKey, revokeApiKey } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const deployTabs = ["Script Tag", "Shareable Link", "REST API"] as const;
type DeployTab = (typeof deployTabs)[number];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 transition-all duration-200"
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5 text-green-500" />
          Copied
        </>
      ) : (
        <>
          <Copy className="h-3.5 w-3.5" />
          Copy
        </>
      )}
    </button>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <div className="relative rounded-lg overflow-hidden border border-gray-200">
      <div className="absolute top-2 right-2 z-10">
        <CopyButton text={code} />
      </div>
      <Highlight theme={themes.vsLight} code={code.trim()} language={language}>
        {({ className, style, tokens, getLineProps, getTokenProps }) => (
          <pre
            className={clsx(className, "p-4 text-sm overflow-auto")}
            style={style}
          >
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}

const platformGuides: { name: string; steps: string[] }[] = [
  {
    name: "WordPress",
    steps: [
      "Go to Appearance > Theme Editor or use a plugin like Insert Headers and Footers",
      "Paste the script tag before the closing </body> tag",
      "Save changes",
    ],
  },
  {
    name: "Shopify",
    steps: [
      "Go to Online Store > Themes > Edit Code",
      "Open theme.liquid",
      "Paste the script tag before </body>",
    ],
  },
  {
    name: "Webflow",
    steps: [
      "Go to Project Settings > Custom Code",
      "Paste the script in the Footer Code section",
      "Publish your site",
    ],
  },
];

export default function DeployPage() {
  const params = useParams();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const chatbotId = params.id as string;
  const [activeTab, setActiveTab] = useState<DeployTab>("Script Tag");
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [creating, setCreating] = useState(false);
  const [expandedGuide, setExpandedGuide] = useState<string | null>(null);
  const qrRef = useRef<HTMLDivElement>(null);

  const scriptTag = `<script src="https://cdn.pulse.ai/widget.js" data-chatbot-id="${chatbotId}"></script>`;
  const chatUrl = `${APP_URL}/chat/${chatbotId}`;
  const curlExample = `curl -X POST ${API_URL}/api/v1/public/chat \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -d '{
    "chatbot_id": "${chatbotId}",
    "message": "Hello, I need help",
    "session_id": "unique-session-id"
  }'`;

  useEffect(() => {
    if (!workspace) return;
    getApiKeys(workspace.id).then(setApiKeys).catch(() => {});
  }, [workspace, chatbotId]);

  async function handleCreateKey() {
    if (!newKeyName.trim() || !workspace) return;
    setCreating(true);
    try {
      const key = await createApiKey(workspace.id, newKeyName.trim());
      setCreatedKey(key);
      setApiKeys((prev) => [...prev, key]);
      setNewKeyName("");
    } catch {
      // handle error
    } finally {
      setCreating(false);
    }
  }

  async function handleRevokeKey(keyId: string) {
    if (!workspace) return;
    try {
      await revokeApiKey(workspace.id, keyId);
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch {
      // handle error
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Deploy</h1>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {deployTabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                "pb-3 text-sm font-medium border-b-2 transition-all duration-200",
                activeTab === tab
                  ? "border-primary-600 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
              )}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "Script Tag" && (
        <div className="space-y-6 max-w-2xl">
          <Card>
            <CardContent className="pt-6 pb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">
                Embed Script
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                Add this script tag to your website to display the chat widget.
              </p>
              <CodeBlock code={scriptTag} language="html" />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6 pb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">
                Platform Guides
              </h2>
              <div className="space-y-2">
                {platformGuides.map((guide) => (
                  <div
                    key={guide.name}
                    className="rounded-lg border border-gray-200"
                  >
                    <button
                      onClick={() =>
                        setExpandedGuide(
                          expandedGuide === guide.name ? null : guide.name,
                        )
                      }
                      className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all duration-200"
                    >
                      {guide.name}
                      <span className="text-gray-400">
                        {expandedGuide === guide.name ? "-" : "+"}
                      </span>
                    </button>
                    {expandedGuide === guide.name && (
                      <div className="px-4 pb-3">
                        <ol className="list-decimal list-inside space-y-1 text-sm text-gray-600">
                          {guide.steps.map((step, i) => (
                            <li key={i}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "Shareable Link" && (
        <div className="space-y-6 max-w-2xl">
          <Card>
            <CardContent className="pt-6 pb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">
                Full-Page Chat Link
              </h2>
              <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-4 py-3 mb-4">
                <code className="flex-1 text-sm text-gray-700 truncate">
                  {chatUrl}
                </code>
                <CopyButton text={chatUrl} />
              </div>

              <div ref={qrRef} className="flex flex-col items-center pt-4">
                <QRCodeSVG value={chatUrl} size={180} level="M" />
                <p className="text-xs text-gray-400 mt-3">
                  Scan to open chat
                </p>
                <button
                  onClick={() => {
                    const canvas = qrRef.current?.querySelector(
                      "svg",
                    ) as SVGSVGElement;
                    if (!canvas) return;
                    const svgData = new XMLSerializer().serializeToString(
                      canvas,
                    );
                    const blob = new Blob([svgData], {
                      type: "image/svg+xml",
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `pulse-qr-${chatbotId}.svg`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="mt-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
                >
                  Download QR Code
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "REST API" && (
        <div className="space-y-6 max-w-2xl">
          <Card>
            <CardContent className="pt-6 pb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">
                API Endpoint
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                Send chat messages programmatically using the REST API.
              </p>
              <CodeBlock code={curlExample} language="bash" />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6 pb-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-4">
                API Keys
              </h2>

              {createdKey && (
                <div className="mb-4 rounded-lg bg-green-50 border border-green-200 p-4">
                  <p className="text-sm font-medium text-green-800 mb-1">
                    API key created! Copy it now - it won&apos;t be shown again.
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <code className="text-sm bg-white px-3 py-1.5 rounded border border-green-200 flex-1 truncate">
                      {createdKey.key}
                    </code>
                    <CopyButton text={createdKey.key} />
                  </div>
                  <button
                    onClick={() => setCreatedKey(null)}
                    className="mt-2 text-xs text-green-700 hover:text-green-800"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              <div className="flex gap-2 mb-4">
                <Input
                  placeholder="Key name (e.g. Production)"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreateKey();
                  }}
                />
                <Button onClick={handleCreateKey} loading={creating} size="sm">
                  <Plus className="h-4 w-4 mr-1" />
                  Create
                </Button>
              </div>

              {apiKeys.length > 0 ? (
                <div className="space-y-2">
                  {apiKeys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <Key className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {key.name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {key.key_prefix}... / Created{" "}
                            {new Date(key.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 transition-all duration-200"
                        title="Revoke"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400 text-center py-4">
                  No API keys yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
