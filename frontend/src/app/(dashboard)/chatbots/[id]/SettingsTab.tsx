"use client";

import { Chatbot } from "@/lib/types";
import { PersonaSettingsPanel } from "@/panels/PersonaSettingsPanel";
import { LLMSettingsPanel } from "@/panels/LLMSettingsPanel";

interface SettingsTabProps {
  chatbot: Chatbot;
  onUpdate: (chatbot: Chatbot) => void;
}

export function SettingsTab({ chatbot, onUpdate }: SettingsTabProps) {
  return (
    <div className="space-y-6">
      <PersonaSettingsPanel chatbot={chatbot} onUpdate={onUpdate} />
      <LLMSettingsPanel chatbot={chatbot} onUpdate={onUpdate} />
    </div>
  );
}
