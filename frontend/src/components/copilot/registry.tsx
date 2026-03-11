import React from "react";
import { LLMSettingsPanel } from "@/panels/LLMSettingsPanel";
import { PersonaSettingsPanel } from "@/panels/PersonaSettingsPanel";
import { ConversationListPanel } from "@/panels/ConversationListPanel";
import { MetricsDashboardPanel } from "@/panels/MetricsDashboardPanel";
import { ChatbotListPanel } from "@/panels/ChatbotListPanel";
import { DocumentListPanel } from "@/panels/DocumentListPanel";
import { CreditBalancePanel } from "@/panels/CreditBalancePanel";
import { CrawlStatusPanel } from "@/panels/CrawlStatusPanel";

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
  ConversationList: ConversationListPanel as unknown as React.ComponentType<Record<string, unknown>>,
  ConversationDetail: stub("ConversationDetail"),
  MetricsDashboard: MetricsDashboardPanel as unknown as React.ComponentType<Record<string, unknown>>,
  ChatbotList: ChatbotListPanel,
  DocumentList: DocumentListPanel as unknown as React.ComponentType<Record<string, unknown>>,
  ActionsList: stub("ActionsList"),
  CreditBalance: CreditBalancePanel,
  LLMSettingsPanel: LLMSettingsPanel as unknown as React.ComponentType<Record<string, unknown>>,
  PersonaSettingsPanel: PersonaSettingsPanel as unknown as React.ComponentType<Record<string, unknown>>,
  WidgetSettingsPanel: stub("WidgetSettingsPanel"),
  CrawlStatusPanel: CrawlStatusPanel as unknown as React.ComponentType<Record<string, unknown>>,
};
