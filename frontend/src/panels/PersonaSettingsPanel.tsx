"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Chatbot } from "@/lib/types";
import { updateChatbot } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const PERSONALITY_PRESETS = [
  { name: "Professional", prompt: "You are a professional, knowledgeable assistant. Respond clearly and concisely. Use formal language and avoid slang. Always be accurate and helpful." },
  { name: "Friendly", prompt: "You are a friendly, approachable assistant. Use a warm, conversational tone. Feel free to use casual language and light humour where appropriate. Make users feel welcome and supported." },
  { name: "Concise", prompt: "You are a direct, efficient assistant. Give short, clear answers. Avoid unnecessary words. Get straight to the point. Use bullet points when listing multiple items." },
  { name: "Technical", prompt: "You are a technical expert. Provide detailed, precise answers. Use technical terminology correctly. Include code examples, commands, or step-by-step instructions where relevant." },
  { name: "Empathetic", prompt: "You are a compassionate, empathetic assistant. Acknowledge user feelings and frustrations before providing solutions. Use supportive, encouraging language. Always validate the user's experience." },
];

const toneOptions = [
  { value: "professional", label: "Professional" },
  { value: "friendly", label: "Friendly" },
  { value: "technical", label: "Technical" },
  { value: "custom", label: "Custom" },
];

interface PersonaSettingsPanelProps {
  chatbot: Chatbot;
  onUpdate: (chatbot: Chatbot) => void;
}

export function PersonaSettingsPanel({ chatbot, onUpdate }: PersonaSettingsPanelProps) {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [displayName, setDisplayName] = useState(chatbot.display_name);
  const [systemPrompt, setSystemPrompt] = useState(chatbot.system_prompt || "");
  const [tone, setTone] = useState(chatbot.tone);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [welcomeMessage, setWelcomeMessage] = useState(chatbot.welcome_message || "");
  const [fallbackMessage, setFallbackMessage] = useState(chatbot.fallback_message || "");
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(chatbot.suggested_questions || []);
  const [suggestionInput, setSuggestionInput] = useState("");
  const [savingPrompts, setSavingPrompts] = useState(false);

  async function handleSavePersona(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateChatbot(workspace.id, chatbot.id, { display_name: displayName, system_prompt: systemPrompt, tone });
      onUpdate(updated);
    } catch {
      setSaveError("Failed to save. Please try again.");
    } finally { setSaving(false); }
  }

  async function handleSavePrompts(e: React.FormEvent) {
    e.preventDefault();
    if (!workspace) return;
    setSavingPrompts(true);
    setSaveError(null);
    try {
      const updated = await updateChatbot(workspace.id, chatbot.id, { welcome_message: welcomeMessage, fallback_message: fallbackMessage, suggested_questions: suggestedQuestions });
      onUpdate(updated);
    } catch {
      setSaveError("Failed to save. Please try again.");
    } finally { setSavingPrompts(false); }
  }

  function addSuggestion() {
    const val = suggestionInput.trim();
    if (val && !suggestedQuestions.includes(val) && suggestedQuestions.length < 6) {
      setSuggestedQuestions([...suggestedQuestions, val]);
      setSuggestionInput("");
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="pt-6 pb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Bot Persona</h2>
          <form onSubmit={handleSavePersona} className="space-y-4 max-w-lg">
            <Input label="Display Name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Support Assistant" />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tone</label>
              <div className="flex gap-2 flex-wrap">
                {toneOptions.map((opt) => (
                  <button key={opt.value} type="button" onClick={() => setTone(opt.value)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${tone === opt.value ? "bg-primary-100 text-primary-700 ring-1 ring-primary-300" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium text-gray-700">System Prompt</label>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Load preset</span>
                  <select value={selectedPreset} onChange={(e) => { const p = PERSONALITY_PRESETS.find((x) => x.name === e.target.value); if (p) setSystemPrompt(p.prompt); setSelectedPreset(""); }}
                    className="rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary-500 text-gray-700">
                    <option value="">Choose a preset…</option>
                    {PERSONALITY_PRESETS.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
                  </select>
                </div>
              </div>
              <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={6}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200"
                placeholder="You are a helpful support assistant…" />
            </div>
            <div className="pt-2"><Button type="submit" loading={saving}>Save Settings</Button></div>
            {saveError && <p className="text-xs text-red-500">{saveError}</p>}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 pb-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">Conversation Prompts</h2>
          <p className="text-xs text-gray-400 mb-4">What the bot says at the start, when it&apos;s stuck, and what it suggests.</p>
          <form onSubmit={handleSavePrompts} className="space-y-4 max-w-lg">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Welcome Message</label>
              <textarea value={welcomeMessage} onChange={(e) => setWelcomeMessage(e.target.value)} rows={2}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" placeholder="Hi! How can I help you today?" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fallback Message</label>
              <textarea value={fallbackMessage} onChange={(e) => setFallbackMessage(e.target.value)} rows={2}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" placeholder="I'm not sure about that." />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Suggested Questions <span className="text-gray-400 font-normal">(max 6)</span></label>
              <div className="flex gap-2 mb-2">
                <input type="text" value={suggestionInput} onChange={(e) => setSuggestionInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSuggestion(); } }}
                  placeholder="e.g. How do I reset my password?"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
                <button type="button" onClick={addSuggestion} className="px-3 py-2 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">Add</button>
              </div>
              {suggestedQuestions.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  {suggestedQuestions.map((q, i) => (
                    <div key={i} className="flex items-center justify-between gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700">
                      <span className="truncate">{q}</span>
                      <button type="button" onClick={() => setSuggestedQuestions(suggestedQuestions.filter((_, j) => j !== i))}
                        className="shrink-0 text-gray-400 hover:text-red-500 transition-colors">×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="pt-2"><Button type="submit" loading={savingPrompts}>Save Prompts</Button></div>
            {saveError && <p className="text-xs text-red-500">{saveError}</p>}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
