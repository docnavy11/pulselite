import { useState, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Key, Server, Cpu, AlertTriangle, RefreshCw, CheckCircle } from "lucide-react";
import { updateLLMSettings, getOpenRouterModels } from "@/lib/api-functions";
import type { OpenRouterModel } from "@/lib/types";

interface AISetupDialogProps {
  workspaceId: string;
  isCloud: boolean;
  hasApiKey: boolean;
  onComplete: () => void;
}

export function AISetupDialog({ workspaceId, isCloud, hasApiKey, onComplete }: AISetupDialogProps) {

  // Step flow: cloud -> "choice" | "credentials" | "models"
  //            self-hosted -> "credentials" | "models"
  //            If API key already set (from env), skip straight to models
  const [step, setStep] = useState<"choice" | "credentials" | "models">(
    hasApiKey ? "models" : isCloud ? "choice" : "credentials",
  );
  const [autoLoaded, setAutoLoaded] = useState(false);
  const [credentialType, setCredentialType] = useState<"byok" | "self-hosted">("self-hosted");

  // Credentials
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Models
  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelSearch, setModelSearch] = useState("");
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [defaultChatbotModel, setDefaultChatbotModel] = useState("");
  const [internalModel, setInternalModel] = useState("");
  const [savingModels, setSavingModels] = useState(false);

  async function handleSaveCredentials() {
    if (!apiKey.trim()) {
      setError("API key is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateLLMSettings(workspaceId, {
        openrouter_api_key: apiKey.trim(),
        openrouter_base_url: baseUrl.trim() || null,
      });
      // Move to model selection step and auto-load models
      setStep("models");
      loadModels();
    } catch {
      setError("Failed to save. Please check your API key and try again.");
    } finally {
      setSaving(false);
    }
  }

  // Auto-load models when starting on models step (API key from env)
  useEffect(() => {
    if (hasApiKey && step === "models" && !autoLoaded) {
      setAutoLoaded(true);
      loadModels();
    }
  }, [hasApiKey, step, autoLoaded]);

  async function loadModels() {
    setLoadingModels(true);
    setModelError(null);
    try {
      const data = await getOpenRouterModels(workspaceId);
      setModels(data.models);
    } catch {
      setModelError("Failed to load models. Your API key may be invalid.");
    } finally {
      setLoadingModels(false);
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

  const selectedList = [...selectedModels];

  async function handleFinish() {
    setSavingModels(true);
    setModelError(null);
    try {
      await updateLLMSettings(workspaceId, {
        allowed_models: selectedList,
        default_chatbot_model: defaultChatbotModel || null,
        internal_model: internalModel || null,
      });
      onComplete();
    } catch {
      setModelError("Failed to save model configuration.");
    } finally {
      setSavingModels(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-2xl mx-4 max-h-[90vh] flex flex-col">
        <div className="p-8 pb-0 shrink-0">
          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-6">
            {(isCloud ? ["Mode", "Credentials", "Models"] : ["Credentials", "Models"]).map((label, i) => {
              const stepIndex = step === "choice" ? 0 : step === "credentials" ? (isCloud ? 1 : 0) : (isCloud ? 2 : 1);
              const isActive = i === stepIndex;
              const isDone = i < stepIndex;
              return (
                <div key={label} className="flex items-center gap-2">
                  {i > 0 && <div className={`w-8 h-px ${isDone ? "bg-primary-500" : "bg-gray-200"}`} />}
                  <div className={`flex items-center gap-1.5 text-xs font-medium ${isActive ? "text-primary-600" : isDone ? "text-primary-500" : "text-gray-400"}`}>
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${isActive ? "bg-primary-500 text-white" : isDone ? "bg-primary-100 text-primary-600" : "bg-gray-100 text-gray-400"}`}>
                      {isDone ? <CheckCircle className="h-3 w-3" /> : i + 1}
                    </div>
                    {label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-8 pt-2 overflow-y-auto flex-1">
          {/* Cloud mode: choice between BYOK and platform keys */}
          {step === "choice" && (
            <>
              <div className="text-center mb-6">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                  <Server className="h-6 w-6 text-primary-600" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">Configure AI</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Choose how you want to power your chatbots.
                </p>
              </div>

              <div className="space-y-3">
                <button
                  onClick={onComplete}
                  className="w-full rounded-xl border-2 border-gray-200 p-4 text-left hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <p className="font-semibold text-gray-900">Use PulseLight keys</p>
                  <p className="mt-1 text-sm text-gray-500">
                    Use platform-managed AI keys. Standard credit pricing applies.
                  </p>
                </button>

                <button
                  onClick={() => { setCredentialType("byok"); setStep("credentials"); }}
                  className="w-full rounded-xl border-2 border-gray-200 p-4 text-left hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-gray-900">Bring Your Own Key (BYOK)</p>
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                      50% off credits
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-gray-500">
                    Use your own OpenRouter or compatible API key.
                  </p>
                </button>
              </div>
            </>
          )}

          {/* Credentials step */}
          {step === "credentials" && (
            <>
              {isCloud && (
                <button
                  onClick={() => setStep("choice")}
                  className="text-sm text-gray-500 hover:text-gray-700 mb-4"
                >
                  &larr; Back
                </button>
              )}

              <div className={isCloud ? "" : "text-center"}>
                {!isCloud && (
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                    <Server className="h-6 w-6 text-primary-600" />
                  </div>
                )}
                <div className={`flex items-center gap-2 mb-2 ${isCloud ? "" : "justify-center"}`}>
                  {isCloud && <Key className="h-5 w-5 text-primary-500" />}
                  <h2 className="text-xl font-bold text-gray-900">
                    {isCloud ? "Enter your API key" : "Configure AI Provider"}
                  </h2>
                </div>
                <p className="text-sm text-gray-500 mb-6">
                  {isCloud
                    ? "Enter your OpenRouter API key to use your own models."
                    : "Connect an OpenRouter-compatible API to power your chatbots."}
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                  <input
                    type="password"
                    placeholder="sk-or-v1-..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Base URL <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  {!isCloud && (
                    <p className="text-xs text-gray-500 mb-1">
                      Override the default endpoint for proxies or self-hosted compatible APIs.
                    </p>
                  )}
                  <input
                    type="text"
                    placeholder="https://openrouter.ai/api/v1"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <Button onClick={handleSaveCredentials} loading={saving} disabled={!apiKey.trim()} className="w-full">
                  Save and load models
                </Button>
              </div>
            </>
          )}

          {/* Model selection step */}
          {step === "models" && (
            <>
              <div className="text-center mb-6">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                  <Cpu className="h-6 w-6 text-primary-600" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">Select Models</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Choose which models are available in this workspace.
                </p>
              </div>

              {loadingModels && (
                <div className="text-center py-8">
                  <RefreshCw className="h-6 w-6 text-primary-500 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-gray-500">Loading available models...</p>
                </div>
              )}

              {modelError && !loadingModels && (
                <div className="text-center py-4">
                  <div className="flex items-center justify-center gap-2 text-sm text-red-600 mb-3">
                    <AlertTriangle className="h-4 w-4" />
                    {modelError}
                  </div>
                  {hasApiKey && (
                    <p className="text-xs text-gray-500 mb-3">
                      Could not connect to your AI provider. Check your AI_BASE_URL and AI_API_KEY in .env
                    </p>
                  )}
                  <div className="flex items-center justify-center gap-2">
                    <Button variant="secondary" onClick={loadModels}>
                      <RefreshCw className="h-4 w-4 mr-1" /> Retry
                    </Button>
                    {!hasApiKey && (
                      <Button variant="secondary" onClick={() => setStep("credentials")}>
                        &larr; Back to credentials
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {!loadingModels && models.length > 0 && (
                <div className="space-y-4">
                  {/* Allowed models */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Allowed Models
                      {selectedModels.size > 0 && (
                        <span className="ml-2 rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                          {selectedModels.size} selected
                        </span>
                      )}
                    </label>
                    <input
                      type="text"
                      placeholder="Search models..."
                      value={modelSearch}
                      onChange={(e) => setModelSearch(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <div className="max-h-48 overflow-y-auto space-y-0.5 border border-gray-200 rounded-lg p-2">
                      {filteredModels.map((model) => (
                        <label
                          key={model.id}
                          className="flex items-center gap-3 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer"
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
                              {(model.context_length / 1000).toFixed(0)}k
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                    <div className="mt-1 flex justify-end">
                      <button
                        onClick={() =>
                          setSelectedModels((prev) => {
                            const allSelected = filteredModels.every((m) => prev.has(m.id));
                            const next = new Set(prev);
                            if (allSelected) {
                              for (const m of filteredModels) next.delete(m.id);
                            } else {
                              for (const m of filteredModels) next.add(m.id);
                            }
                            return next;
                          })
                        }
                        className="text-xs text-primary-500 hover:underline"
                      >
                        {filteredModels.every((m) => selectedModels.has(m.id)) ? "Deselect all" : "Select all"}
                      </button>
                    </div>
                  </div>

                  {/* Default chatbot model */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Default Chatbot Model
                    </label>
                    <p className="text-xs text-gray-500 mb-1">
                      Model assigned to new chatbots by default.
                    </p>
                    <select
                      value={defaultChatbotModel}
                      onChange={(e) => setDefaultChatbotModel(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
                    >
                      <option value="">Select a model</option>
                      {selectedList.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>

                  {/* Background tasks model */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Background Tasks Model
                    </label>
                    <p className="text-xs text-gray-500 mb-1">
                      Used for conversation analysis, Q&A generation, and autoconfig.
                    </p>
                    <select
                      value={internalModel}
                      onChange={(e) => setInternalModel(e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
                    >
                      <option value="">Select a model</option>
                      {selectedList.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>

                  {modelError && (
                    <div className="flex items-center gap-2 text-sm text-red-600">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      {modelError}
                    </div>
                  )}

                  {selectedModels.size === 0 && (
                    <p className="text-xs text-amber-600 text-center">
                      Select at least one model to continue.
                    </p>
                  )}

                  <Button
                    onClick={handleFinish}
                    loading={savingModels}
                    disabled={selectedModels.size === 0}
                    className="w-full"
                  >
                    Finish setup
                  </Button>
                </div>
              )}

              {!loadingModels && models.length === 0 && !modelError && (
                <div className="text-center py-4">
                  <p className="text-sm text-gray-500 mb-3">No models loaded yet.</p>
                  <Button variant="secondary" onClick={loadModels}>
                    <RefreshCw className="h-4 w-4 mr-1" /> Load models
                  </Button>
                </div>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
}
