import { getTokens } from "./auth";
import { ChatEvent } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function* streamChat(
  chatbotId: string,
  message: string,
  options?: {
    conversationId?: string;
    sessionId?: string;
    isPublic?: boolean;
  },
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const endpoint = options?.isPublic
    ? `${BASE_URL}/api/v1/public/chat`
    : `${BASE_URL}/api/v1/chat`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!options?.isPublic) {
    const tokens = getTokens();
    if (tokens) {
      headers["Authorization"] = `Bearer ${tokens.access_token}`;
    }
  }

  const body: Record<string, string> = {
    chatbot_id: chatbotId,
    message,
  };
  if (options?.conversationId) body.conversation_id = options.conversationId;
  if (options?.sessionId) body.session_id = options.sessionId;

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    yield { type: "error", data: `Request failed: ${response.status}` };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: "error", data: "No response body" };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    if (signal?.aborted) break;
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        try {
          const event: ChatEvent = JSON.parse(data);
          yield event;
          if (event.type === "done" || event.type === "error") return;
        } catch {
          yield { type: "token", data };
        }
      }
    }
  }
}
