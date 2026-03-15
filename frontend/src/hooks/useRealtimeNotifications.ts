import { useSocketEvent } from "@/lib/socket";
import { useToast } from "@/lib/toast";
import type { CrawlCompletedEvent, DocumentStatusEvent, ChatbotStatusEvent } from "@/lib/types";

export function useRealtimeNotifications(): void {
  const { success, error } = useToast();

  useSocketEvent<CrawlCompletedEvent>("crawl:completed", (data) => {
    if (data.status === "completed") {
      success(`Crawl completed — ${data.pages_queued} pages indexed`);
    } else {
      error(`Crawl failed: ${data.error_message || "Unknown error"}`);
    }
  });

  useSocketEvent<DocumentStatusEvent>("document:status_changed", (data) => {
    if (data.status === "failed") {
      error(`Failed to index: ${data.title} — ${data.error_message || "Unknown error"}`);
    }
    // Don't toast every successful index (too noisy during crawls)
  });

  useSocketEvent<ChatbotStatusEvent>("chatbot:status_changed", (data) => {
    if (data.setup_status === "ready") {
      success("Chatbot is ready for review");
    } else if (data.setup_status === "setup_failed") {
      error("Chatbot auto-configuration failed");
    }
  });

  useSocketEvent<{ chatbot_id: string; count: number }>("qa:questions_generated", (data) => {
    success(`${data.count} Q&A questions generated — testing in progress`);
  });

  useSocketEvent<{ qa_pair_id: string; status: string }>("qa:pair_updated", (data) => {
    if (data.status === "failed") {
      error("A Q&A test failed");
    }
    // Don't toast every successful test (too noisy when batch completes)
  });
}
