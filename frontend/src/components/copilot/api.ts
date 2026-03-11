import { useAuthStore } from "@/stores/auth-store";

export type CopilotEvent =
  | { type: "token"; data: string }
  | { type: "action"; tool: string; args: Record<string, unknown> }
  | { type: "done" }
  | { type: "error"; data: string };

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
}

interface StreamCallbacks {
  onToken: (token: string) => void;
  onAction: (tool: string, args: Record<string, unknown>) => void;
  onDone: () => void;
  onError: (msg: string) => void;
}

export async function streamCopilotChat(
  workspaceId: string,
  messages: CopilotMessage[],
  context: Record<string, unknown>,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const tokens = useAuthStore.getState().tokens;
  const res = await fetch(
    `/api/v1/workspaces/${workspaceId}/copilot/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tokens?.access_token ?? ""}`,
      },
      body: JSON.stringify({ messages, context, workspace_id: workspaceId }),
      signal,
    }
  );

  if (!res.ok || !res.body) {
    callbacks.onError(`HTTP ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    const lines = buf.split("\n");
    buf = lines.pop() ?? "";

    let eventType = "message";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const raw = line.slice(6).trim();
        try {
          const payload = JSON.parse(raw);
          if (eventType === "token") {
            callbacks.onToken(payload.data);
          } else if (eventType === "action") {
            callbacks.onAction(payload.tool, payload.args ?? {});
          } else if (eventType === "done") {
            callbacks.onDone();
          } else if (eventType === "error") {
            callbacks.onError(payload.data ?? "Unknown error");
          }
        } catch {
          // ignore malformed lines
        }
        eventType = "message";
      } else if (line === "") {
        eventType = "message";
      }
    }
  }
}
