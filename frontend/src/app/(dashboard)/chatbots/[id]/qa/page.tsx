import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  Loader2,
  Sparkles,
  Trash2,
  RotateCcw,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Check,
  ChevronDown,
  ChevronRight,
  Play,
  Send,
  Bot,
  User as UserIcon,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useSocketEvent } from "@/lib/socket";
import {
  getQAPairs,
  generateQAPairs,
  createQAPair,
  runQATests,
  updateQAPair,
  deleteQAPair,
  suggestQAAnswer,
  retestQAPair,
  retestAllQAPairs,
  addQAPairToKB,
} from "@/lib/api-functions";
import { MarkdownMessage } from "@/components/ui/MarkdownMessage";
import { MarkdownEditor } from "@/components/ui/MarkdownEditor";
import type { QAPair } from "@/lib/types";

type Filter = "all" | "pending" | "low_confidence" | "escalated" | "failed";

export default function QAPage() {
  const { id: chatbotId } = useParams<{ id: string }>();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [totalUnfiltered, setTotalUnfiltered] = useState(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [testing, setTesting] = useState(false);
  const [retestingAll, setRetestingAll] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [showGeneratePopover, setShowGeneratePopover] = useState(false);
  const [generateCount, setGenerateCount] = useState(10);
  const [customCount, setCustomCount] = useState("");
  const [newQuestion, setNewQuestion] = useState("");
  const [collapseKey, setCollapseKey] = useState(0);
  const [expandKey, setExpandKey] = useState(0);
  const [allExpanded, setAllExpanded] = useState(false);
  const [suggestingIds, setSuggestingIds] = useState<Set<string>>(new Set());
  const [addingQuestion, setAddingQuestion] = useState(false);

  const wsId = workspace?.id || "";

  // Always fetch all pairs — filter client-side for counts
  const [allPairs, setAllPairs] = useState<QAPair[]>([]);

  const fetchPairs = useCallback(async (merge = false) => {
    if (!wsId || !chatbotId) return;
    try {
      const res = await getQAPairs(wsId, chatbotId, { page_size: 200 });
      if (merge) {
        // Merge updates into existing list without reordering
        setAllPairs((prev) => {
          const incoming = new Map(res.items.map((p) => [p.id, p]));
          // Update existing pairs in place, append new ones at end
          const updated = prev.map((p) => incoming.get(p.id) ?? p);
          const existingIds = new Set(prev.map((p) => p.id));
          const newPairs = res.items.filter((p) => !existingIds.has(p.id));
          return newPairs.length > 0 ? [...newPairs, ...updated] : updated;
        });
      } else {
        setAllPairs(res.items);
      }
      setTotalUnfiltered(res.total);
      // Clear suggesting state for pairs that now have suggestions
      setSuggestingIds((prev) => {
        if (prev.size === 0) return prev;
        const next = new Set(prev);
        for (const item of res.items) {
          if (item.suggested_answer && next.has(item.id)) next.delete(item.id);
        }
        return next;
      });
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [wsId, chatbotId]);

  useEffect(() => {
    fetchPairs();
  }, [fetchPairs]);

  // Socket.IO: refresh on new questions generated
  useSocketEvent("qa:questions_generated", () => {
    setGenerating(false);
    fetchPairs();
  });

  // Socket.IO: update individual pair in real-time
  useSocketEvent<{
    qa_pair_id: string;
    status: string;
    confidence_score: number | null;
    escalated: boolean;
    answer: string | null;
    suggested_answer: string | null;
  }>("qa:pair_updated", (data) => {
    setAllPairs((prev) =>
      prev.map((p) =>
        p.id === data.qa_pair_id
          ? {
              ...p,
              status: data.status as QAPair["status"],
              confidence_score: data.confidence_score,
              escalated: data.escalated,
              answer: data.answer ?? p.answer,
              suggested_answer: data.suggested_answer ?? p.suggested_answer,
            }
          : p,
      ),
    );
    // Stop spinners when results arrive
    setTesting(false);
    setRetestingAll(false);
    if (data.suggested_answer) {
      setSuggestingIds((prev) => {
        const next = new Set(prev);
        next.delete(data.qa_pair_id);
        return next;
      });
    }
  });

  // Fallback polling: covers testing, suggesting, and any background ops
  // Socket.IO from workers isn't always reliable, so poll as safety net
  const hasPendingWork = allPairs.some((p) => p.status === "testing") || suggestingIds.size > 0;
  useEffect(() => {
    if (!hasPendingWork) return;
    const interval = setInterval(() => fetchPairs(true), 4000);
    return () => clearInterval(interval);
  }, [hasPendingWork, fetchPairs]);

  // Compute filter counts from all pairs
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  const pendingCount = allPairs.filter((p) => p.status === "pending").length;
  const failedCount = allPairs.filter((p) => p.status === "failed").length;
  const completedPairs = allPairs.filter((p) => p.status === "completed");
  const lowConfCount = completedPairs.filter((p) => clamp(p.confidence_score ?? 1) < 0.5).length;
  const escalatedCount = completedPairs.filter((p) => p.escalated).length;
  const hasInProgress = allPairs.some((p) => p.status === "testing");

  // Apply client-side filter
  const pairs = filter === "all" ? allPairs :
    filter === "pending" ? allPairs.filter((p) => p.status === "pending") :
    filter === "failed" ? allPairs.filter((p) => p.status === "failed") :
    filter === "low_confidence" ? completedPairs.filter((p) => clamp(p.confidence_score ?? 1) < 0.5) :
    filter === "escalated" ? completedPairs.filter((p) => p.escalated) :
    allPairs;

  async function handleGenerate() {
    if (!wsId || !chatbotId) return;
    setGenerating(true);
    setShowGeneratePopover(false);
    try {
      await generateQAPairs(wsId, chatbotId, generateCount);
    } catch {
      setGenerating(false);
    }
  }

  async function handleRunTests() {
    if (!wsId || !chatbotId) return;
    setTesting(true);
    try {
      await runQATests(wsId, chatbotId);
    } catch {
      setTesting(false);
    }
  }

  async function handleRetestAll() {
    if (!wsId || !chatbotId) return;
    setRetestingAll(true);
    try {
      await retestAllQAPairs(wsId, chatbotId);
      // Optimistically mark all completed/failed as testing
      setAllPairs((prev) =>
        prev.map((p) =>
          p.status === "completed" || p.status === "failed"
            ? { ...p, status: "testing" as const, answer: null, confidence_score: null, escalated: false }
            : p,
        ),
      );
    } catch {
      // ignore
    } finally {
      setRetestingAll(false);
    }
  }

  async function handleAddQuestion() {
    if (!wsId || !chatbotId || !newQuestion.trim()) return;
    setAddingQuestion(true);
    try {
      const pair = await createQAPair(wsId, chatbotId, newQuestion.trim());
      setAllPairs((prev) => [pair, ...prev]);
      setTotalUnfiltered((t) => t + 1);
      setNewQuestion("");
    } finally {
      setAddingQuestion(false);
    }
  }

  async function handleDelete(pairId: string) {
    if (!wsId || !chatbotId) return;
    await deleteQAPair(wsId, chatbotId, pairId);
    setAllPairs((prev) => prev.filter((p) => p.id !== pairId));
    setTotalUnfiltered((t) => t - 1);
  }

  async function handleRetest(pairId: string) {
    if (!wsId || !chatbotId) return;
    setAllPairs((prev) => prev.map((p) => (p.id === pairId ? { ...p, status: "testing" as const, answer: null } : p)));
    await retestQAPair(wsId, chatbotId, pairId);
  }

  async function handleSuggest(pairId: string) {
    if (!wsId || !chatbotId) return;
    setSuggestingIds((prev) => new Set(prev).add(pairId));
    await suggestQAAnswer(wsId, chatbotId, pairId);
  }

  async function handleAddToKB(pairId: string) {
    if (!wsId || !chatbotId) return;
    const res = await addQAPairToKB(wsId, chatbotId, pairId);
    setAllPairs((prev) =>
      prev.map((p) => (p.id === pairId ? { ...p, kb_document_id: res.document_id } : p)),
    );
  }

  async function handleSaveEdit(pairId: string, field: "question" | "answer", value: string) {
    if (!wsId || !chatbotId) return;
    const updated = await updateQAPair(wsId, chatbotId, pairId, { [field]: value });
    setAllPairs((prev) => prev.map((p) => (p.id === pairId ? updated : p)));
  }

  function handleRejectSuggestion(pairId: string) {
    setAllPairs((prev) =>
      prev.map((p) => (p.id === pairId ? { ...p, suggested_answer: null } : p)),
    );
  }

  async function handleUseSuggestion(pairId: string) {
    const pair = allPairs.find((p) => p.id === pairId);
    if (!pair?.suggested_answer || !wsId || !chatbotId) return;
    // Update answer AND clear suggested_answer in one API call
    const updated = await updateQAPair(wsId, chatbotId, pairId, {
      answer: pair.suggested_answer,
    });
    setAllPairs((prev) =>
      prev.map((p) => (p.id === pairId ? { ...updated, suggested_answer: null } : p)),
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Q&A Testing</h2>
        </div>

        <div className="flex items-center gap-2">
          {/* Re-run all — visible when there are completed/failed pairs */}
          {completedPairs.length + failedCount > 0 && (
            <Button
              onClick={handleRetestAll}
              disabled={retestingAll || hasInProgress}
              loading={retestingAll}
              variant="secondary"
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Re-run all
            </Button>
          )}

          {/* Run Tests button — visible when there are pending questions */}
          {pendingCount > 0 && (
            <Button
              onClick={handleRunTests}
              disabled={testing || hasInProgress}
              loading={testing || hasInProgress}
              variant="secondary"
            >
              <Play className="mr-2 h-4 w-4" />
              {testing || hasInProgress ? "Testing..." : `Run tests (${pendingCount})`}
            </Button>
          )}

          {/* Generate button */}
          <div className="relative">
            <Button
              onClick={() => setShowGeneratePopover(!showGeneratePopover)}
              disabled={generating}
              loading={generating}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {generating ? "Generating..." : "Generate"}
            </Button>

            {showGeneratePopover && (
              <div className="absolute right-0 top-full z-10 mt-2 w-56 rounded-lg border border-gray-200 bg-white p-4 shadow-lg">
                <p className="mb-3 text-sm font-medium text-gray-700">How many questions?</p>
                <div className="mb-3 flex flex-wrap gap-2">
                  {[5, 10, 25, 50].map((n) => (
                    <button
                      key={n}
                      onClick={() => { setGenerateCount(n); setCustomCount(""); }}
                      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                        generateCount === n && !customCount
                          ? "bg-primary-500 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                  <input
                    type="number"
                    min={1}
                    max={50}
                    placeholder="#"
                    value={customCount}
                    onChange={(e) => {
                      const v = e.target.value;
                      setCustomCount(v);
                      const num = parseInt(v, 10);
                      if (num >= 1 && num <= 50) setGenerateCount(num);
                    }}
                    className={`w-16 rounded-md border px-2 py-1.5 text-sm font-medium text-center ${
                      customCount
                        ? "border-primary-500 ring-1 ring-primary-500"
                        : "border-gray-200"
                    }`}
                  />
                </div>
                <Button onClick={handleGenerate} className="w-full">
                  Generate {generateCount} questions
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add question input */}
      <div className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={newQuestion}
            onChange={(e) => setNewQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && newQuestion.trim()) handleAddQuestion(); }}
            placeholder="Add your own question..."
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <Button
            onClick={handleAddQuestion}
            disabled={!newQuestion.trim() || addingQuestion}
            loading={addingQuestion}
            variant="secondary"
          >
            <Send className="mr-2 h-4 w-4" />
            Add
          </Button>
        </div>
      </div>

      {/* Filters + expand/collapse */}
      {totalUnfiltered > 0 && (
        <div className="mb-4 flex items-center justify-between">
          <div className="flex gap-2">
            {(["all", "pending", "low_confidence", "escalated", "failed"] as Filter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  filter === f
                    ? "bg-primary-50 text-primary-700"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {f === "all" ? `All (${totalUnfiltered})` : f === "pending" ? `Pending (${pendingCount})` : f === "low_confidence" ? `Low confidence (${lowConfCount})` : f === "escalated" ? `Escalated (${escalatedCount})` : `Failed (${failedCount})`}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              if (allExpanded) {
                setCollapseKey((k) => k + 1);
              } else {
                setExpandKey((k) => k + 1);
              }
              setAllExpanded(!allExpanded);
            }}
            className="rounded px-2.5 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          >
            {allExpanded ? "Collapse all" : "Expand all"}
          </button>
        </div>
      )}

      {/* Empty state */}
      {totalUnfiltered === 0 && !generating && (
        <Card>
          <CardContent className="py-16 text-center">
            <Sparkles className="mx-auto mb-4 h-10 w-10 text-gray-300" />
            <h3 className="text-sm font-semibold text-gray-900">No Q&A pairs yet</h3>
            <p className="mt-1 text-sm text-gray-500">
              Generate questions or add your own to test how your chatbot responds.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <Button onClick={() => setShowGeneratePopover(true)}>
                <Sparkles className="mr-2 h-4 w-4" />
                Generate
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* No results for current filter */}
      {pairs.length === 0 && totalUnfiltered > 0 && !generating && (
        <p className="py-8 text-center text-sm text-gray-500">
          No {filter === "all" ? "" : filter.replace("_", " ")} pairs found.
        </p>
      )}

      {/* Q&A Cards */}
      <div className="space-y-3">
        {pairs.map((pair) => (
          <QACard
            key={pair.id}
            pair={pair}
            collapseKey={collapseKey}
            expandKey={expandKey}
            onDelete={() => handleDelete(pair.id)}
            onRetest={() => handleRetest(pair.id)}
            suggesting={suggestingIds.has(pair.id)}
            onSuggest={() => handleSuggest(pair.id)}
            onAddToKB={() => handleAddToKB(pair.id)}
            onSaveEdit={(field, value) => handleSaveEdit(pair.id, field, value)}
            onUseSuggestion={() => handleUseSuggestion(pair.id)}
            onRejectSuggestion={() => handleRejectSuggestion(pair.id)}
            onAccept={() => handleSaveEdit(pair.id, "answer", pair.answer || "")}
          />
        ))}
      </div>
    </div>
  );
}

// ── QA Card Component (Chat-window style) ─────────────────────

interface QACardProps {
  pair: QAPair;
  collapseKey: number;
  expandKey: number;
  suggesting: boolean;
  onDelete: () => void;
  onRetest: () => void;
  onSuggest: () => void;
  onAddToKB: () => void;
  onSaveEdit: (field: "question" | "answer", value: string) => void;
  onUseSuggestion: () => void;
  onRejectSuggestion: () => void;
  onAccept: () => void;
}

function QACard({ pair, collapseKey, expandKey, suggesting, onDelete, onRetest, onSuggest, onAddToKB, onSaveEdit, onUseSuggestion, onRejectSuggestion, onAccept }: QACardProps) {
  const [editingQ, setEditingQ] = useState(false);
  const [editingA, setEditingA] = useState(false);
  const [qDraft, setQDraft] = useState(pair.question);
  const [aDraft, setADraft] = useState(pair.answer || "");
  const [accepted, setAccepted] = useState(false);
  const [collapsed, setCollapsed] = useState(true);

  // React to global collapse/expand
  useEffect(() => {
    if (collapseKey > 0) setCollapsed(true);
  }, [collapseKey]);

  useEffect(() => {
    if (expandKey > 0) setCollapsed(false);
  }, [expandKey]);

  const isPending = pair.status === "pending";
  const isTesting = pair.status === "testing";
  const isWorking = isPending || isTesting;

  function confidenceBadge() {
    if (pair.confidence_score === null) return null;
    const score = Math.max(0, Math.min(1, pair.confidence_score));
    const color =
      score >= 0.75 ? "bg-green-100 text-green-700" :
      score >= 0.5 ? "bg-yellow-100 text-yellow-700" :
      "bg-red-100 text-red-700";
    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>
        {(score * 100).toFixed(0)}%
      </span>
    );
  }

  function handleAccept() {
    setAccepted(true);
    setCollapsed(true);
    onAccept();
  }

  // Collapsed view
  if (collapsed) {
    return (
      <Card className="border-green-200 bg-green-50/30">
        <CardContent className="py-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setCollapsed(false)} className="text-gray-400 hover:text-gray-600">
              <ChevronRight className="h-4 w-4" />
            </button>
            <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
            <p className="flex-1 text-sm text-gray-900">{pair.question}</p>
            {confidenceBadge()}
            {pair.is_edited && (
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">Edited</span>
            )}
            {pair.kb_document_id && (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-700">In KB</span>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`${isWorking ? "opacity-60" : ""} ${accepted ? "border-green-200" : ""}`}>
      <CardContent className="py-4">
        {/* Top bar with badges and collapse */}
        <div className="mb-3 flex items-center gap-2">
          {!isWorking && (
            <button onClick={() => setCollapsed(true)} className="text-gray-400 hover:text-gray-600">
              <ChevronDown className="h-4 w-4" />
            </button>
          )}
          {confidenceBadge()}
          {pair.escalated && (
            <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-[11px] font-medium text-orange-700">
              <AlertTriangle className="h-3 w-3" /> Escalated
            </span>
          )}
          {pair.status === "failed" && (
            <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">
              Failed
            </span>
          )}
          {isPending && (
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
              Pending
            </span>
          )}
          {pair.is_edited && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700">Edited</span>
          )}
          {pair.kb_document_id && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-700">In KB</span>
          )}
          {isTesting && <Loader2 className="h-3 w-3 animate-spin text-gray-400" />}
        </div>

        {/* Chat window */}
        <div className="space-y-3">
          {/* User question bubble (right-aligned) */}
          <div className="flex items-start gap-2 justify-end">
            <div className="max-w-[80%]">
              {editingQ ? (
                <div className="flex gap-2">
                  <input
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    value={qDraft}
                    onChange={(e) => setQDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") { onSaveEdit("question", qDraft); setEditingQ(false); }
                      if (e.key === "Escape") setEditingQ(false);
                    }}
                    autoFocus
                  />
                  <button onClick={() => { onSaveEdit("question", qDraft); setEditingQ(false); }} className="text-sm text-primary-500 font-medium">Save</button>
                  <button onClick={() => setEditingQ(false)} className="text-sm text-gray-400">Cancel</button>
                </div>
              ) : (
                <div
                  className="cursor-pointer rounded-2xl rounded-tr-sm bg-primary-500 px-4 py-2.5 text-sm text-white hover:bg-primary-600 transition-colors"
                  onClick={() => setEditingQ(true)}
                  title="Click to edit question"
                >
                  {pair.question}
                </div>
              )}
            </div>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100">
              <UserIcon className="h-4 w-4 text-primary-600" />
            </div>
          </div>

          {/* Bot answer bubble (left-aligned) */}
          {isTesting && (
            <div className="flex items-start gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100">
                <Bot className="h-4 w-4 text-gray-600" />
              </div>
              <div className="rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2.5">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Thinking...
                </div>
              </div>
            </div>
          )}

          {pair.answer !== null && (
            <div className="flex items-start gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100">
                <Bot className="h-4 w-4 text-gray-600" />
              </div>
              <div className="max-w-[80%]">
                {editingA ? (
                  <div>
                    <MarkdownEditor
                      value={aDraft}
                      onChange={setADraft}
                    />
                    <div className="mt-2 flex gap-2">
                      <button onClick={() => { onSaveEdit("answer", aDraft); setEditingA(false); }} className="text-sm text-primary-500 font-medium">Save</button>
                      <button onClick={() => setEditingA(false)} className="text-sm text-gray-400">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div
                    className="cursor-pointer rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-sm text-gray-800 hover:bg-gray-150 transition-colors"
                    onClick={() => { setADraft(pair.answer || ""); setEditingA(true); }}
                    title="Click to edit answer"
                  >
                    <MarkdownMessage content={pair.answer || ""} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Pending state — no answer yet, not testing */}
          {isPending && (
            <div className="flex items-start gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100">
                <Bot className="h-4 w-4 text-gray-600" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-dashed border-gray-300 bg-gray-50 px-4 py-2.5 text-sm text-gray-400">
                Waiting for test...
              </div>
            </div>
          )}
        </div>

        {/* Error message */}
        {pair.error_message && (
          <p className="mt-2 text-xs text-red-500">{pair.error_message}</p>
        )}

        {/* Suggested answer panel */}
        {pair.suggested_answer && (
          <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-blue-600">Suggested Answer</span>
            <MarkdownMessage content={pair.suggested_answer || ""} className="text-sm text-blue-900" />
            <div className="mt-2 flex gap-2">
              <button
                onClick={onUseSuggestion}
                className="rounded-md bg-blue-500 px-3 py-1 text-xs font-medium text-white hover:bg-blue-600"
              >
                Use this answer
              </button>
              <button
                onClick={onRejectSuggestion}
                className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {/* Suggesting placeholder */}
        {suggesting && !pair.suggested_answer && (
          <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
            <div className="flex items-center gap-2 text-sm text-blue-600">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Generating suggestion...
            </div>
          </div>
        )}

        {/* Actions */}
        {!isWorking && (
          <div className="mt-3 flex items-center gap-2 border-t border-gray-100 pt-3">
            {!accepted && pair.answer !== null && (
              <button
                onClick={handleAccept}
                className="flex items-center gap-1 rounded-md border border-green-300 bg-green-50 px-2.5 py-1 text-[12px] font-medium text-green-700 hover:bg-green-100"
              >
                <Check className="h-3 w-3" /> Accept
              </button>
            )}
            {(pair.escalated || (pair.confidence_score !== null && pair.confidence_score < 0.5)) && !pair.suggested_answer && !suggesting && (
              <button
                onClick={onSuggest}
                className="flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-[12px] font-medium text-gray-700 hover:bg-gray-100"
              >
                <Sparkles className="h-3 w-3" /> Suggest answer
              </button>
            )}
            {pair.is_edited && (
              <button
                onClick={onAddToKB}
                disabled={pair.kb_document_id !== null}
                className="flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-[12px] font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                <Plus className="h-3 w-3" />
                {pair.kb_document_id ? (
                  <><CheckCircle2 className="h-3 w-3 text-green-500" /> Added to KB</>
                ) : (
                  "Add to KB"
                )}
              </button>
            )}
            {pair.answer !== null && (
              <button
                onClick={onRetest}
                className="flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1 text-[12px] font-medium text-gray-700 hover:bg-gray-100"
              >
                <RotateCcw className="h-3 w-3" /> Re-test
              </button>
            )}
            <button
              onClick={onDelete}
              className="ml-auto flex items-center gap-1 rounded-md px-2.5 py-1 text-[12px] font-medium text-red-500 hover:bg-red-50"
            >
              <Trash2 className="h-3 w-3" /> Delete
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
