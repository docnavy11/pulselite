import { useState, useCallback, useEffect, useRef } from "react";
import { useSocketEvent } from "@/lib/socket";
import type { TaskEvent, CrawlCompletedEvent, ChatbotStatusEvent } from "@/lib/types";

export interface ActivityEntry {
  id: string;
  taskName: string;
  status: "running" | "done" | "error";
  detail?: string;
  current?: number;
  total?: number;
  error?: string;
  timestamp: number;
}

const MAX_ENTRIES = 50;
const AUTO_DISMISS_MS = 30_000;

export function useActivityConsole() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const scheduleDismiss = useCallback((id: string) => {
    const existing = timersRef.current.get(id);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      setEntries((prev) => prev.filter((e) => e.id !== id));
      timersRef.current.delete(id);
    }, AUTO_DISMISS_MS);
    timersRef.current.set(id, timer);
  }, []);

  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const addEntry = useCallback((entry: ActivityEntry) => {
    setEntries((prev) => {
      const filtered = prev.filter((e) => e.id !== entry.id);
      const next = [entry, ...filtered];
      return next.slice(0, MAX_ENTRIES);
    });
  }, []);

  const updateEntry = useCallback((id: string, updates: Partial<ActivityEntry>) => {
    setEntries((prev) =>
      prev.map((e) => (e.id === id ? { ...e, ...updates } : e))
    );
  }, []);

  const dismissEntry = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }, []);

  useSocketEvent<TaskEvent>("task:started", (data) => {
    addEntry({
      id: data.task_id,
      taskName: data.task_name,
      status: "running",
      detail: data.detail ?? undefined,
      timestamp: Date.now(),
    });
  });

  useSocketEvent<TaskEvent>("task:progress", (data) => {
    updateEntry(data.task_id, {
      current: data.current ?? undefined,
      total: data.total ?? undefined,
      detail: data.detail ?? undefined,
    });
  });

  useSocketEvent<TaskEvent>("task:completed", (data) => {
    const isError = data.error != null;
    const status: ActivityEntry["status"] = isError ? "error" : "done";

    setEntries((prev) => {
      const existing = prev.find((e) => e.id === data.task_id);
      if (existing) {
        return prev.map((e) =>
          e.id === data.task_id
            ? { ...e, status, detail: data.detail ?? e.detail, error: data.error ?? undefined, timestamp: Date.now() }
            : e
        );
      }
      return [
        {
          id: data.task_id,
          taskName: data.task_name,
          status,
          detail: data.detail ?? undefined,
          error: data.error ?? undefined,
          timestamp: Date.now(),
        },
        ...prev,
      ].slice(0, MAX_ENTRIES);
    });

    if (!isError) {
      scheduleDismiss(data.task_id);
    }
  });

  useSocketEvent<CrawlCompletedEvent>("crawl:completed", (data) => {
    const isError = data.status === "failed";
    const entry: ActivityEntry = {
      id: data.job_id,
      taskName: "crawl_completed",
      status: isError ? "error" : "done",
      detail: isError
        ? data.error_message ?? "Crawl failed"
        : `${data.pages_queued} pages indexed`,
      error: isError ? (data.error_message ?? "Crawl failed") : undefined,
      timestamp: Date.now(),
    };
    addEntry(entry);
    if (!isError) scheduleDismiss(data.job_id);
  });

  useSocketEvent<ChatbotStatusEvent>("chatbot:status_changed", (data) => {
    if (data.setup_status !== "ready" && data.setup_status !== "setup_failed") return;
    const isError = data.setup_status === "setup_failed";
    const id = crypto.randomUUID();
    const entry: ActivityEntry = {
      id,
      taskName: "chatbot_ready",
      status: isError ? "error" : "done",
      detail: isError ? "Auto-configuration failed" : "Chatbot is ready",
      error: isError ? "Auto-configuration failed" : undefined,
      timestamp: Date.now(),
    };
    addEntry(entry);
    if (!isError) scheduleDismiss(id);
  });

  const runningCount = entries.filter((e) => e.status === "running").length;

  return { entries, runningCount, dismissEntry };
}
