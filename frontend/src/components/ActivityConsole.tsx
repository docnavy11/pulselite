import { useState, useEffect } from "react";
import { useActivityConsole, type ActivityEntry } from "@/hooks/useActivityConsole";

const TASK_LABELS: Record<string, string> = {
  analyze_conversation: "Analyzing conversation",
  analyze_all: "Analyzing all conversations",
  compute_sentiment: "Computing sentiment trends",
  cluster_gaps: "Clustering gap events",
  weekly_digest: "Sending weekly digest",
  export_data: "Exporting workspace data",
  sync_documents: "Syncing stale documents",
  auto_recharge: "Auto-recharging credits",
  purge_data: "Purging old data",
  crawl_completed: "Website crawl",
  chatbot_ready: "Chatbot configuration",
};

function getLabel(taskName: string): string {
  return TASK_LABELS[taskName] ?? taskName;
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function StatusIcon({ status }: { status: ActivityEntry["status"] }) {
  if (status === "running") {
    return (
      <svg className="h-4 w-4 animate-spin text-amber-500" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
        <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    );
  }
  if (status === "done") {
    return (
      <svg className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4 text-red-500" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
    </svg>
  );
}

function EntryRow({
  entry,
  onDismiss,
}: {
  entry: ActivityEntry;
  onDismiss: (id: string) => void;
}) {
  const isDone = entry.status === "done";
  return (
    <div className={`flex items-start gap-2 px-3 py-2 border-b border-gray-100 last:border-0 ${isDone ? "opacity-60" : ""}`}>
      <div className="mt-0.5 shrink-0">
        <StatusIcon status={entry.status} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${isDone ? "text-gray-500" : "text-gray-800"}`}>
          {getLabel(entry.taskName)}
          {isDone && <span className="ml-1.5 text-[10px] font-normal text-green-600">Done</span>}
        </p>
        {entry.detail && (
          <p className="text-xs text-gray-500 truncate">{entry.detail}</p>
        )}
        {entry.current != null && entry.total != null && entry.total > 0 && entry.status === "running" && (
          <div className="mt-1 h-1.5 w-full rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-amber-400 transition-all"
              style={{ width: `${Math.min(100, (entry.current / entry.total) * 100)}%` }}
            />
          </div>
        )}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <span className="text-[10px] text-gray-400">{relativeTime(entry.timestamp)}</span>
        {entry.status !== "running" && (
          <button
            onClick={() => onDismiss(entry.id)}
            className="ml-1 text-gray-400 hover:text-gray-600"
            title="Dismiss"
          >
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export function ActivityConsole() {
  const { entries, runningCount, dismissEntry } = useActivityConsole();
  const [expanded, setExpanded] = useState(false);
  // Listen for toggle event from sidebar
  useEffect(() => {
    const handler = () => setExpanded((prev) => !prev);
    window.addEventListener("toggle-activity-console", handler);
    return () => window.removeEventListener("toggle-activity-console", handler);
  }, []);

  const hasEntries = entries.length > 0;
  const isVisible = hasEntries || expanded;

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 transition-opacity ${
        isVisible ? "opacity-100" : "opacity-0 pointer-events-none"
      }`}
    >
      {expanded ? (
        <div className="w-80 max-h-[400px] bg-white rounded-lg shadow-lg border border-gray-200 flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Activity
            </h3>
            <button
              onClick={() => setExpanded(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          <div className="overflow-y-auto flex-1">
            {entries.length === 0 ? (
              <p className="px-3 py-6 text-xs text-gray-400 text-center">No activity yet</p>
            ) : (
              entries.map((entry) => (
                <EntryRow key={entry.id} entry={entry} onDismiss={dismissEntry} />
              ))
            )}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-lg border border-gray-200 hover:bg-gray-50 transition-colors"
        >
          <svg className="h-4 w-4 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
          <span className="text-sm text-gray-600">Activity</span>
          {runningCount > 0 && (
            <span className="flex items-center justify-center h-5 min-w-[20px] px-1 text-xs font-medium text-white bg-amber-500 rounded-full">
              {runningCount}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
