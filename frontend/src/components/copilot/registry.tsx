import React from "react";
import { LLMSettingsPanel } from "@/panels/LLMSettingsPanel";
import { PersonaSettingsPanel } from "@/panels/PersonaSettingsPanel";

function stub(name: string) {
  return function PanelStub(props: Record<string, unknown>) {
    return (
      <div className="p-4 text-sm text-gray-400">
        <span className="font-medium text-gray-600">{name}</span>
        <pre className="mt-2 text-xs overflow-auto">{JSON.stringify(props, null, 2)}</pre>
      </div>
    );
  };
}

export const ComponentRegistry: Record<string, React.ComponentType<Record<string, unknown>>> = {
  ConversationList: stub("ConversationList"),
  ConversationDetail: stub("ConversationDetail"),
  MetricsDashboard: stub("MetricsDashboard"),
  ChatbotList: stub("ChatbotList"),
  DocumentList: stub("DocumentList"),
  ActionsList: stub("ActionsList"),
  CreditBalance: stub("CreditBalance"),
  LLMSettingsPanel: LLMSettingsPanel as React.ComponentType<Record<string, unknown>>,
  PersonaSettingsPanel: PersonaSettingsPanel as React.ComponentType<Record<string, unknown>>,
  WidgetSettingsPanel: stub("WidgetSettingsPanel"),
};
