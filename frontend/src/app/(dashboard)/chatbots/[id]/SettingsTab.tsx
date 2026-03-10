"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { updateChatbot, updateLLMConfig, getLLMSettings } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const PERSONALITY_PRESETS = [
  {
    name: "Professional",
    prompt:
      "You are a professional, knowledgeable assistant. Respond clearly and concisely. Use formal language and avoid slang. Always be accurate and helpful.",
  },
  {
    name: "Friendly",
    prompt:
      "You are a friendly, approachable assistant. Use a warm, conversational tone. Feel free to use casual language and light humour where appropriate. Make users feel welcome and supported.",
  },
  {
    name: "Concise",
    prompt:
      "You are a direct, efficient assistant. Give short, clear answers. Avoid unnecessary words. Get straight to the point. Use bullet points when listing multiple items.",
  },
  {
    name: "Technical",
    prompt:
      "You are a technical expert. Provide detailed, precise answers. Use technical terminology correctly. Include code examples, commands, or step-by-step instructions where relevant.",
  },
  {
    name: "Empathetic",
    prompt:
      "You are a compassionate, empathetic assistant. Acknowledge user feelings and frustrations before providing solutions. Use supportive, encouraging language. Always validate the user's experience.",
  },
];

const toneOptions = [
  { value: "professional", label: "Professional" },
  { value: "friendly", label: "Friendly" },
  { value: "technical", label: "Technical" },
  { value: "custom", label: "Custom" },
];


interface SettingsTabProps {
  chatbot: Chatbot;
  onUpdate: (chatbot: Chatbot) => void;
}

export function SettingsTab({ chatbot, onUpdate }: SettingsTabProps) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [displayName, setDisplayName] = useState(chatbot.display_name);
  const [systemPrompt, setSystemPrompt] = useState(chatbot.system_prompt || "");
  const [tone, setTone] = useState(chatbot.tone);
  const [saving, setSaving] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState("");

  // LLM config state
  const [llmModel, setLlmModel] = useState(chatbot.llm_model);
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [temperature, setTemperature] = useState(chatbot.temperature ?? 0.3);
  const [confidenceThreshold, setConfidenceThreshold] = useState(chatbot.confidence_threshold ?? 0.65);
  const [retrievalTopK, setRetrievalTopK] = useState(chatbot.retrieval_top_k ?? 5);
  const [useReranking, setUseReranking] = useState(chatbot.use_reranking ?? true);
  const [useHybrid, setUseHybrid] = useState(chatbot.use_hybrid_retrieval ?? true);
  const [savingLLM, setSavingLLM] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setAllowedModels(data.allowed_models);
        setModelsLoaded(true);
      })
      .catch(() => setModelsLoaded(true));
  }, [workspace]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      if (!workspace) return;
      const updated = await updateChatbot(workspace.id, chatbot.id, {
        display_name: displayName,
        system_prompt: systemPrompt,
        tone,
      });
      onUpdate(updated);
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveLLM(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setSavingLLM(true);
    try {
      const updated = await updateLLMConfig(workspace.id, chatbot.id, {
        llm_provider: "openrouter",
        llm_model: llmModel,
        temperature,
        confidence_threshold: confidenceThreshold,
        retrieval_top_k: retrievalTopK,
        use_reranking: useReranking,
        use_hybrid_retrieval: useHybrid,
      });
      onUpdate(updated);
    } catch {
      // handle error
    } finally {
      setSavingLLM(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="pt-6 pb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">
            Bot Persona
          </h2>
          <form onSubmit={handleSave} className="space-y-4 max-w-lg">
            <Input
              label="Display Name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Support Assistant"
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tone
              </label>
              <div className="flex gap-2 flex-wrap">
                {toneOptions.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setTone(opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                      tone === opt.value
                        ? "bg-primary-100 text-primary-700 ring-1 ring-primary-300"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-gray-700">
                  System Prompt
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Load preset</span>
                  <select
                    value={selectedPreset}
                    onChange={(e) => {
                      const preset = PERSONALITY_PRESETS.find(
                        (p) => p.name === e.target.value
                      );
                      if (preset) setSystemPrompt(preset.prompt);
                      setSelectedPreset("");
                    }}
                    className="rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-700"
                  >
                    <option value="">Choose a preset…</option>
                    {PERSONALITY_PRESETS.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={6}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200"
                placeholder="You are a helpful support assistant. Answer questions based on the knowledge base provided..."
              />
              <p className="mt-1 text-xs text-gray-400">
                Define how the bot should behave and respond
              </p>
            </div>

            <div className="pt-2">
              <Button type="submit" loading={saving}>
                Save Settings
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 pb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">AI Behavior</h2>
          <p className="text-xs text-gray-400 mb-4">Configure the model, retrieval, and escalation settings.</p>
          <form onSubmit={handleSaveLLM} className="space-y-4 max-w-lg">
            {/* Model */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
              {!modelsLoaded ? (
                <Spinner className="h-5 w-5 text-primary-600" />
              ) : allowedModels.length > 0 ? (
                <select
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {allowedModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  placeholder="e.g. openai/gpt-4o"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              )}
              {allowedModels.length === 0 && modelsLoaded && (
                <p className="mt-1 text-xs text-gray-500">
                  Configure allowed models in{" "}
                  <a href="/settings/llm" className="text-primary-600 hover:underline">
                    AI Models settings
                  </a>
                  .
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Temperature: <span className="text-primary-600 font-semibold">{temperature}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full accent-primary-600"
              />
              <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                <span>Precise (0)</span>
                <span>Creative (1)</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Confidence Threshold: <span className="text-primary-600 font-semibold">{confidenceThreshold}</span>
              </label>
              <input
                type="range"
                min={0.1}
                max={0.99}
                step={0.01}
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                className="w-full accent-primary-600"
              />
              <p className="text-[10px] text-gray-400 mt-0.5">
                Responses below this score escalate to human. Higher = stricter.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Retrieved Chunks: <span className="text-primary-600 font-semibold">{retrievalTopK}</span>
              </label>
              <input
                type="range"
                min={1}
                max={20}
                step={1}
                value={retrievalTopK}
                onChange={(e) => setRetrievalTopK(parseInt(e.target.value))}
                className="w-full accent-primary-600"
              />
            </div>

            <div className="flex gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useReranking}
                  onChange={(e) => setUseReranking(e.target.checked)}
                  className="rounded accent-primary-600"
                />
                <span className="text-sm text-gray-700">Use Reranking</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useHybrid}
                  onChange={(e) => setUseHybrid(e.target.checked)}
                  className="rounded accent-primary-600"
                />
                <span className="text-sm text-gray-700">Hybrid Retrieval</span>
              </label>
            </div>

            <div className="pt-2">
              <Button type="submit" loading={savingLLM}>
                Save AI Config
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
