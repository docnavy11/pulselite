"use client";

import { Spinner } from "@/components/ui/Spinner";
import { useChatbotStore } from "@/stores/chatbot-store";
import { SettingsTab } from "../SettingsTab";

export default function ChatbotSettingsPage() {
  const { currentChatbot: chatbot, setChatbot } = useChatbotStore();

  if (!chatbot) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return <SettingsTab chatbot={chatbot} onUpdate={setChatbot} />;
}
