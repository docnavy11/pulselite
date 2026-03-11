import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Chatbot } from "@/lib/types";
import { getLLMSettings, updateLLMConfig } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

interface LLMSettingsPanelProps {
  chatbot: Chatbot;
  onUpdate: (chatbot: Chatbot) => void;
}

export function LLMSettingsPanel({ chatbot, onUpdate }: LLMSettingsPanelProps) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [llmModel, setLlmModel] = useState(chatbot.llm_model);
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [temperature, setTemperature] = useState(chatbot.temperature ?? 0.3);
  const [confidenceThreshold, setConfidenceThreshold] = useState(chatbot.confidence_threshold ?? 0.65);
  const [retrievalTopK, setRetrievalTopK] = useState(chatbot.retrieval_top_k ?? 5);
  const [useReranking, setUseReranking] = useState(chatbot.use_reranking ?? true);
  const [useHybrid, setUseHybrid] = useState(chatbot.use_hybrid_retrieval ?? true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspace) return;
    getLLMSettings(workspace.id)
      .then((data) => {
        setAllowedModels(data.allowed_models);
        if (data.allowed_models.length > 0 && !data.allowed_models.includes(chatbot.llm_model)) {
          setLlmModel(data.allowed_models[0]);
        }
        setModelsLoaded(true);
      })
      .catch(() => setModelsLoaded(true));
  }, [workspace]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setSaving(true);
    setSaveError(null);
    try {
      const provider = llmModel.startsWith("anthropic/") ? "anthropic" : llmModel.startsWith("google/") ? "google" : "openrouter";
      const updated = await updateLLMConfig(workspace.id, chatbot.id, { llm_provider: provider, llm_model: llmModel, temperature, confidence_threshold: confidenceThreshold, retrieval_top_k: retrievalTopK, use_reranking: useReranking, use_hybrid_retrieval: useHybrid });
      onUpdate(updated);
    } catch {
      setSaveError("Failed to save. Please try again.");
    } finally { setSaving(false); }
  }

  return (
    <Card>
      <CardContent className="pt-6 pb-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1">AI Behavior</h2>
        <p className="text-xs text-gray-400 mb-4">Configure the model, retrieval, and escalation settings.</p>
        <form onSubmit={handleSave} className="space-y-4 max-w-lg">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
            {!modelsLoaded ? <Spinner className="h-5 w-5 text-primary-500" />
              : allowedModels.length > 0 ? (
                <select value={llmModel} onChange={(e) => setLlmModel(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  {allowedModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input type="text" value={llmModel} onChange={(e) => setLlmModel(e.target.value)} placeholder="e.g. openai/gpt-4o" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              )}
            {allowedModels.length === 0 && modelsLoaded && (
              <p className="mt-1 text-xs text-gray-500">Configure allowed models in <a href="/settings/llm" className="text-primary-500 hover:underline">AI Models settings</a>.</p>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Temperature: <span className="text-primary-500 font-semibold">{temperature}</span></label>
            <input type="range" min={0} max={1} step={0.05} value={temperature} onChange={(e) => setTemperature(parseFloat(e.target.value))} className="w-full accent-primary-500" />
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5"><span>Precise (0)</span><span>Creative (1)</span></div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Confidence Threshold: <span className="text-primary-500 font-semibold">{confidenceThreshold}</span></label>
            <input type="range" min={0.1} max={0.99} step={0.01} value={confidenceThreshold} onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))} className="w-full accent-primary-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Retrieved Chunks: <span className="text-primary-500 font-semibold">{retrievalTopK}</span></label>
            <input type="range" min={1} max={20} step={1} value={retrievalTopK} onChange={(e) => setRetrievalTopK(parseInt(e.target.value))} className="w-full accent-primary-500" />
          </div>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={useReranking} onChange={(e) => setUseReranking(e.target.checked)} className="rounded accent-primary-500" />
              <span className="text-sm text-gray-700">Use Reranking</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={useHybrid} onChange={(e) => setUseHybrid(e.target.checked)} className="rounded accent-primary-500" />
              <span className="text-sm text-gray-700">Hybrid Retrieval</span>
            </label>
          </div>
          <div className="pt-2"><Button type="submit" loading={saving}>Save AI Config</Button></div>
          {saveError && <p className="text-xs text-red-500 mt-1">{saveError}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
