import React from "react";

// Panels are loaded lazily — they may not exist yet; stubs render a placeholder
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

// Replace stubs with real imports as panels are built in later chunks
export const ComponentRegistry: Record<string, React.ComponentType<Record<string, unknown>>> = {
  ConversationList: stub("ConversationList"),
  ConversationDetail: stub("ConversationDetail"),
  MetricsDashboard: stub("MetricsDashboard"),
  ChatbotList: stub("ChatbotList"),
  DocumentList: stub("DocumentList"),
  ActionsList: stub("ActionsList"),
  CreditBalance: stub("CreditBalance"),
  LLMSettingsPanel: stub("LLMSettingsPanel"),
  PersonaSettingsPanel: stub("PersonaSettingsPanel"),
  WidgetSettingsPanel: stub("WidgetSettingsPanel"),
};
