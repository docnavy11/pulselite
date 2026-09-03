import { useState, useEffect } from "react";
import { Key, Cpu, CheckCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getLLMSettings, updateLLMSettings, getOpenRouterModels } from "@/lib/api-functions";
import type { LLMSettings, OpenRouterModel } from "@/lib/types";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useDeploymentStore } from "@/stores/deployment-store";
import { api } from "@/lib/api";

export default function LLMSettingsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const isCloud = useDeploymentStore((s) => s.isCloud);

  const [isByok, setIsByok] = useState(false);
  const [savingByok, setSavingByok] = useState(false);

  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [keySuccess, setKeySuccess] = useState(false);

  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelSearch, setModelSearch] = useState("");
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [savingModels, setSavingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSuccess, setModelSuccess] = useState(false);

  const [internalModel, setInternalModel] = useState("");
  const [savingInternal, setSavingInternal] = useState(false);
  const [internalSuccess, setInternalSuccess] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);

  const [defaultChatbotModel, setDefaultChatbotModel] = useState("");
  const [savingDefault, setSavingDefault] = useState(false);
  const [defaultSuccess, setDefaultSuccess] = useState(false);
  const [defaultError, setDefaultError] = useState<string | null>(null);

  const [pageLoading, setPageLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setSettings(data);
        setBaseUrlInput(data.openrouter_base_url || "");
        setSelectedModels(new Set(data.allowed_models));
        setInternalModel(data.internal_model || "");
        setDefaultChatbotModel(data.default_chatbot_model || "");
      })
      .finally(() => setPageLoading(false));
  }, [workspace]);

  useEffect(() => {
    if (workspace) setIsByok((workspace as any).is_byok ?? false);
  }, [workspace]);

  async function handleToggleByok() {
    if (!workspace) return;
    setSavingByok(true);
    try {
      const newValue = !isByok;
      await api.patch(`/api/v1/workspaces/${workspace.id}`, { is_byok: newValue });
      setIsByok(newValue);
    } catch {
      // revert on error
    } finally {
      setSavingByok(false);
    }
  }

  async function handleSaveKey() {
    if (!workspace) return;
    setKeyError(null);
    setKeySuccess(false);
    setSavingKey(true);
    try {
      const updated = await updateLLMSettings(workspace.id, {
        openrouter_api_key: keyInput || "",
        openrouter_base_url: baseUrlInput || null,
        allowed_models: [...selectedModels],
      });
      setSettings(updated);
      setKeyInput("");
      setKeySuccess(true);
    } catch {
      setKeyError("Failed to save API key. Please try again.");
    } finally {
      setSavingKey(false);
    }
  }

  async function handleLoadModels() {
    if (!workspace) return;
    setModelError(null);
    setLoadingModels(true);
    try {
      const data = await getOpenRouterModels(workspace.id);
      setModels(data.models);
    } catch {
      setModelError("Failed to load models. Ensure your API key is saved and valid.");
    } finally {
      setLoadingModels(false);
    }
  }

  async function handleSaveModels() {
    if (!workspace) return;
    setModelError(null);
    setModelSuccess(false);
    setSavingModels(true);
    try {
      const updated = await updateLLMSettings(workspace.id, {
        allowed_models: [...selectedModels],
      });
      setSettings(updated);
      setModels([]);
      setModelSearch("");
      setModelSuccess(true);
    } catch {
      setModelError("Failed to save model selection.");
    } finally {
      setSavingModels(false);
    }
  }

  function toggleModel(modelId: string) {
    setSelectedModels((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  }

  const filteredModels = models.filter(
    (m) =>
      m.id.toLowerCase().includes(modelSearch.toLowerCase()) ||
      m.name.toLowerCase().includes(modelSearch.toLowerCase()),
  );

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Models</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your OpenRouter API key and select which models chatbots in this workspace can use.
        </p>
      </div>

      {isCloud && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-gray-900">Bring Your Own Key (BYOK)</h2>
                <p className="mt-1 text-sm text-gray-500">
                  {isByok
                    ? "Using your own API key — 50% discount on credits"
                    : "Using platform API keys — standard credit pricing"}
                </p>
              </div>
              <button
                onClick={handleToggleByok}
                disabled={savingByok}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  isByok ? 'bg-primary-500' : 'bg-gray-300'
                } ${savingByok ? 'opacity-50' : ''}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isByok ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Card 1 — API Key */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-4">
            <Key className="h-5 w-5 text-primary-500" />
            <h2 className="text-base font-semibold text-gray-900">OpenRouter API Key</h2>
            {settings?.openrouter_api_key_set && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                <CheckCircle className="h-3 w-3" /> Key saved
              </span>
            )}
            {!settings?.openrouter_api_key_set && settings?.env_api_key_set && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                <CheckCircle className="h-3 w-3" /> From .env
              </span>
            )}
          </div>

          <div className="flex gap-3 max-w-lg">
            <input
              type="password"
              placeholder={settings?.openrouter_api_key_set ? "••••••••••••••••••••" : "sk-or-v1-..."}
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <Button onClick={handleSaveKey} loading={savingKey} disabled={!keyInput}>
              Save key
            </Button>
          </div>

          {settings?.openrouter_api_key_set && (
            <button
              onClick={async () => {
                if (!workspace) return;
                try {
                  const updated = await updateLLMSettings(workspace.id, {
                    openrouter_api_key: "",
                    openrouter_base_url: baseUrlInput || null,
                    allowed_models: [...selectedModels],
                  });
                  setSettings(updated);
                } catch {
                  setKeyError("Failed to remove key.");
                }
              }}
              className="mt-2 text-xs text-red-500 hover:underline"
            >
              Remove key
            </button>
          )}

          <div className="mt-6 border-t pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Custom Base URL <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <p className="text-xs text-gray-500 mb-2">
              Override the default API endpoint. Useful for proxies or self-hosted compatible APIs.
            </p>
            <div className="flex gap-3 max-w-lg">
              <input
                type="text"
                placeholder="https://openrouter.ai/api/v1"
                value={baseUrlInput}
                onChange={(e) => setBaseUrlInput(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <Button
                onClick={async () => {
                  if (!workspace) return;
                  setSavingKey(true);
                  setKeyError(null);
                  setKeySuccess(false);
                  try {
                    const updated = await updateLLMSettings(workspace.id, {
                      openrouter_base_url: baseUrlInput || null,
                      allowed_models: [...selectedModels],
                    });
                    setSettings(updated);
                    setKeySuccess(true);
                  } catch {
                    setKeyError("Failed to save base URL.");
                  } finally {
                    setSavingKey(false);
                  }
                }}
                loading={savingKey}
                variant="secondary"
              >
                Save URL
              </Button>
            </div>
            {!baseUrlInput && settings?.env_base_url && (
              <p className="mt-1 text-xs text-gray-400">
                From .env: <code className="bg-gray-100 px-1 rounded">{settings.env_base_url}</code>
              </p>
            )}
          </div>

          {keyError && <p className="mt-3 text-sm text-red-600">{keyError}</p>}
          {keySuccess && <p className="mt-3 text-sm text-green-600">Settings saved successfully.</p>}
        </CardContent>
      </Card>

      {/* Card 2 — Allowed Models */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-primary-500" />
              <h2 className="text-base font-semibold text-gray-900">Allowed Models</h2>
              {settings && settings.allowed_models.length > 0 && (
                <span className="rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                  {settings.allowed_models.length} selected
                </span>
              )}
            </div>
            <Button
              variant="secondary"
              onClick={handleLoadModels}
              loading={loadingModels}
              disabled={!settings?.effective_api_key_set}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Edit models
            </Button>
          </div>

          {!settings?.effective_api_key_set && (
            <p className="text-sm text-gray-500 mb-4">Save your API key first to load available models.</p>
          )}

          {models.length > 0 && (
            <>
              <input
                type="text"
                placeholder="Search models..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />

              {selectedModels.size > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {[...selectedModels].map((m) => (
                    <span
                      key={m}
                      className="inline-flex items-center gap-1 rounded-full bg-primary-50 border border-primary-200 px-2.5 py-0.5 text-xs font-medium text-primary-700"
                    >
                      {m}
                      <button
                        onClick={() => toggleModel(m)}
                        className="ml-0.5 text-primary-400 hover:text-primary-600"
                      >
                        &times;
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <div className="max-h-80 overflow-y-auto space-y-1 border border-gray-200 rounded-lg p-2">
                {filteredModels.map((model) => (
                  <label
                    key={model.id}
                    className="flex items-center gap-3 px-2 py-2 rounded hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedModels.has(model.id)}
                      onChange={() => toggleModel(model.id)}
                      className="h-4 w-4 text-primary-500 border-gray-300 rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{model.name}</p>
                      <p className="text-xs text-gray-500 truncate">{model.id}</p>
                    </div>
                    {model.context_length && (
                      <span className="text-xs text-gray-400 shrink-0">
                        {(model.context_length / 1000).toFixed(0)}k ctx
                      </span>
                    )}
                  </label>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-3">
                <Button onClick={handleSaveModels} loading={savingModels}>
                  Save model selection
                </Button>
                <button
                  onClick={() =>
                    setSelectedModels((prev) => {
                      const allFilteredSelected = filteredModels.every((m) => prev.has(m.id));
                      const next = new Set(prev);
                      if (allFilteredSelected) {
                        for (const m of filteredModels) next.delete(m.id);
                      } else {
                        for (const m of filteredModels) next.add(m.id);
                      }
                      return next;
                    })
                  }
                  className="text-sm text-primary-500 hover:underline"
                >
                  {filteredModels.every((m) => selectedModels.has(m.id)) ? "Deselect all" : "Select all"}
                </button>
              </div>
            </>
          )}

          {models.length === 0 && settings && settings.allowed_models.length > 0 && (
            <div className="space-y-1">
              {settings.allowed_models.map((m) => (
                <div key={m} className="text-sm text-gray-700 flex items-center gap-2">
                  <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                  {m}
                </div>
              ))}
            </div>
          )}

          {modelError && <p className="mt-3 text-sm text-red-600">{modelError}</p>}
          {modelSuccess && <p className="mt-3 text-sm text-green-600">Model selection saved.</p>}
        </CardContent>
      </Card>

      {/* Card 3 — Default Chatbot Model */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="h-5 w-5 text-primary-500" />
            <h2 className="text-base font-semibold text-gray-900">Default Chatbot Model</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Model assigned to new chatbots by default. Used during autoconfig and when creating a chatbot.
          </p>

          <div className="flex gap-3 max-w-lg">
            <select
              value={defaultChatbotModel}
              onChange={(e) => setDefaultChatbotModel(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
            >
              <option value="">Select a model</option>
              {(settings?.allowed_models || []).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <Button
              onClick={async () => {
                if (!workspace) return;
                setSavingDefault(true);
                setDefaultError(null);
                setDefaultSuccess(false);
                try {
                  const updated = await updateLLMSettings(workspace.id, {
                    default_chatbot_model: defaultChatbotModel.trim() || null,
                  });
                  setSettings(updated);
                  setDefaultChatbotModel(updated.default_chatbot_model || "");
                  setDefaultSuccess(true);
                } catch {
                  setDefaultError("Failed to save model.");
                } finally {
                  setSavingDefault(false);
                }
              }}
              loading={savingDefault}
            >
              Save
            </Button>
          </div>

          {!defaultChatbotModel && settings?.env_default_chatbot_model && (
            <p className="mt-2 text-xs text-gray-400">
              From .env: <code className="bg-gray-100 px-1 rounded">{settings.env_default_chatbot_model}</code>
            </p>
          )}

          {defaultError && <p className="mt-3 text-sm text-red-600">{defaultError}</p>}
          {defaultSuccess && <p className="mt-3 text-sm text-green-600">Default chatbot model saved.</p>}
        </CardContent>
      </Card>

      {/* Card 4 — Background Tasks Model */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 mb-2">
            <Cpu className="h-5 w-5 text-primary-500" />
            <h2 className="text-base font-semibold text-gray-900">Background Tasks Model</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Model used for internal background tasks like conversation analysis, Q&A generation, action triggers, and the copilot.
          </p>

          <div className="flex gap-3 max-w-lg">
            <select
              value={internalModel}
              onChange={(e) => setInternalModel(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
            >
              <option value="">Select a model</option>
              {(settings?.allowed_models || []).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <Button
              onClick={async () => {
                if (!workspace) return;
                setSavingInternal(true);
                setInternalError(null);
                setInternalSuccess(false);
                try {
                  const updated = await updateLLMSettings(workspace.id, {
                    internal_model: internalModel.trim() || null,
                  });
                  setSettings(updated);
                  setInternalModel(updated.internal_model || "");
                  setInternalSuccess(true);
                } catch {
                  setInternalError("Failed to save model.");
                } finally {
                  setSavingInternal(false);
                }
              }}
              loading={savingInternal}
            >
              Save
            </Button>
          </div>

          {!internalModel && settings?.env_internal_model && (
            <p className="mt-2 text-xs text-gray-400">
              From .env: <code className="bg-gray-100 px-1 rounded">{settings.env_internal_model}</code>
            </p>
          )}

          {internalError && <p className="mt-3 text-sm text-red-600">{internalError}</p>}
          {internalSuccess && <p className="mt-3 text-sm text-green-600">Background task model saved.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
