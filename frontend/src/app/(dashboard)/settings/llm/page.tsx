"use client";

import { useState, useEffect } from "react";
import { Key, Cpu, CheckCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getLLMSettings, updateLLMSettings, getOpenRouterModels } from "@/lib/api-functions";
import type { LLMSettings, OpenRouterModel } from "@/lib/types";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function LLMSettingsPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);

  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [keyInput, setKeyInput] = useState("");
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

  const [pageLoading, setPageLoading] = useState(true);

  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setSettings(data);
        setSelectedModels(new Set(data.allowed_models));
      })
      .finally(() => setPageLoading(false));
  }, [workspace]);

  async function handleSaveKey() {
    if (!workspace) return;
    setKeyError(null);
    setKeySuccess(false);
    setSavingKey(true);
    try {
      const updated = await updateLLMSettings(workspace.id, {
        openrouter_api_key: keyInput || "",
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

          {keyError && <p className="mt-3 text-sm text-red-600">{keyError}</p>}
          {keySuccess && <p className="mt-3 text-sm text-green-600">API key saved successfully.</p>}
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
              disabled={!settings?.openrouter_api_key_set}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Load from OpenRouter
            </Button>
          </div>

          {!settings?.openrouter_api_key_set && (
            <p className="text-sm text-gray-500 mb-4">Save your API key first to load available models.</p>
          )}

          {models.length > 0 && (
            <>
              <input
                type="text"
                placeholder="Search models..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />

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
                      if (prev.size === filteredModels.length) return new Set();
                      return new Set(filteredModels.map((m) => m.id));
                    })
                  }
                  className="text-sm text-primary-500 hover:underline"
                >
                  {selectedModels.size === filteredModels.length ? "Deselect all" : "Select all"}
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
    </div>
  );
}
