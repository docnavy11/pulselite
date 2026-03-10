export interface CitationSource {
  index: number;
  title: string;
  url: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onDone: (data: { conversationId?: string; messageId?: string; sources?: CitationSource[] }) => void;
  onError: (error: string) => void;
  onAction?: (data: { type: string; name: string; fields?: string[] }) => void;
}

export async function streamChat(
  apiUrl: string,
  chatbotId: string,
  sessionId: string,
  message: string,
  conversationId: string | null,
  callbacks: StreamCallbacks
): Promise<void> {
  const url = `${apiUrl}/api/v1/public/chat`;

  try {
    const body: Record<string, string> = {
      chatbot_id: chatbotId,
      session_id: sessionId,
      message,
    };
    if (conversationId) {
      body.conversation_id = conversationId;
    }

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      callbacks.onError(`Request failed: ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError("Streaming not supported");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";
    let convId: string | undefined;
    let msgId: string | undefined;
    let sources: CitationSource[] | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            callbacks.onDone({ conversationId: convId, messageId: msgId, sources });
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === "action" && parsed.data) {
              try {
                const actionData = JSON.parse(parsed.data);
                callbacks.onAction?.(actionData);
              } catch {
                // ignore malformed action data
              }
              continue;
            }
            if (parsed.type === "done") {
              convId = parsed.conversation_id ?? convId;
              msgId = parsed.message_id ?? msgId;
              sources = parsed.sources ?? undefined;
              continue;
            }
            if (parsed.data) {
              callbacks.onToken(parsed.data);
            }
            if (parsed.conversation_id) {
              convId = parsed.conversation_id;
            }
            if (parsed.error) {
              callbacks.onError(parsed.error);
              return;
            }
          } catch {
            // Plain text token
            if (data.trim()) {
              callbacks.onToken(data);
            }
          }
        }
      }
    }

    callbacks.onDone({ conversationId: convId, messageId: msgId, sources });
  } catch (err) {
    callbacks.onError(
      err instanceof Error ? err.message : "Connection failed"
    );
  }
}
