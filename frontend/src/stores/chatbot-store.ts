import { create } from "zustand";
import { Chatbot } from "@/lib/types";

interface ChatbotState {
  // The chatbot currently open in the detail view
  currentChatbot: Chatbot | null;
  setChatbot: (chatbot: Chatbot) => void;
  patchChatbot: (partial: Partial<Chatbot>) => void;
  clearChatbot: () => void;

  // All chatbots for the current workspace (used by in-app assistant, dashboard, etc.)
  chatbots: Chatbot[];
  setChatbots: (chatbots: Chatbot[]) => void;
  patchChatbotInList: (id: string, partial: Partial<Chatbot>) => void;
  removeChatbotFromList: (id: string) => void;
}

export const useChatbotStore = create<ChatbotState>((set) => ({
  currentChatbot: null,
  chatbots: [],

  setChatbot: (chatbot) => {
    set({ currentChatbot: chatbot });
    // Also keep the list in sync
    set((s) => ({
      chatbots: s.chatbots.some((c) => c.id === chatbot.id)
        ? s.chatbots.map((c) => (c.id === chatbot.id ? chatbot : c))
        : s.chatbots,
    }));
  },

  patchChatbot: (partial) =>
    set((s) => ({
      currentChatbot: s.currentChatbot ? { ...s.currentChatbot, ...partial } : null,
      chatbots: s.chatbots.map((c) =>
        c.id === s.currentChatbot?.id ? { ...c, ...partial } : c
      ),
    })),

  clearChatbot: () => set({ currentChatbot: null }),

  setChatbots: (chatbots) => set({ chatbots }),

  patchChatbotInList: (id, partial) =>
    set((s) => ({
      chatbots: s.chatbots.map((c) => (c.id === id ? { ...c, ...partial } : c)),
      currentChatbot:
        s.currentChatbot?.id === id
          ? { ...s.currentChatbot, ...partial }
          : s.currentChatbot,
    })),

  removeChatbotFromList: (id) =>
    set((s) => ({
      chatbots: s.chatbots.filter((c) => c.id !== id),
      currentChatbot: s.currentChatbot?.id === id ? null : s.currentChatbot,
    })),
}));
