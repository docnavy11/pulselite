"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { clsx } from "clsx";
import { Bot, User, Headset, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { Exception, Message } from "@/lib/types";
import {
  getExceptionDetail,
  getMessages,
  replyToException,
  resolveException,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

function ConfidenceBadge({ confidence }: { confidence?: number }) {
  if (confidence == null) return null;
  const variant =
    confidence > 0.75 ? "success" : confidence > 0.5 ? "warning" : "danger";
  return (
    <Badge variant={variant} className="text-[10px]">
      {Math.round(confidence * 100)}%
    </Badge>
  );
}

const tierColors: Record<string, string> = {
  hot: "bg-red-100 text-red-700",
  warm: "bg-amber-100 text-amber-700",
  cold: "bg-blue-100 text-blue-700",
};

export default function ExceptionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = params.id as string;
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [exception, setException] = useState<Exception | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [resolving, setResolving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!workspace) return;
    Promise.all([
      getExceptionDetail(workspace.id, conversationId),
      getMessages(workspace.id, conversationId),
    ])
      .then(([exc, msgs]) => {
        setException(exc);
        setMessages(msgs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, conversationId]);

  async function handleReply(resolve = false) {
    if (!workspace || !reply.trim()) return;
    setSending(true);
    try {
      await replyToException(workspace.id, conversationId, reply.trim(), resolve);
      if (resolve) {
        router.push("/exceptions");
      } else {
        setReply("");
        const msgs = await getMessages(workspace.id, conversationId);
        setMessages(msgs);
      }
    } catch {
      // handle error
    } finally {
      setSending(false);
    }
  }

  async function handleResolve() {
    if (!workspace) return;
    setResolving(true);
    try {
      await resolveException(workspace.id, conversationId);
      router.push("/exceptions");
    } catch {
      // handle error
    } finally {
      setResolving(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleReply();
    }
  }

  // Auto-expand textarea
  function handleTextareaInput() {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }

  if (loading || !exception) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div>
      <Link
        href="/exceptions"
        className="inline-flex items-center gap-1 mb-4 text-sm text-gray-500 hover:text-gray-700 transition-colors"
      >
        ← Exceptions Queue
      </Link>
    <div className="flex gap-6 h-[calc(100vh-10rem)]">
      {/* Left: Conversation timeline */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <h1 className="text-lg font-semibold text-gray-900 mb-4">
          Exception Detail
        </h1>

        <div className="flex-1 overflow-auto rounded-lg border border-gray-200 bg-white p-4 space-y-4">
          {messages.map((msg, idx) => {
            const isEscalationPoint =
              idx > 0 &&
              messages[idx - 1]?.role === "assistant" &&
              msg.role === "user" &&
              idx === messages.length - 1;

            return (
              <div key={msg.id}>
                {isEscalationPoint && (
                  <div className="flex items-center gap-2 my-4">
                    <div className="flex-1 h-px bg-red-200" />
                    <span className="flex items-center gap-1 text-xs font-medium text-red-500">
                      <AlertTriangle className="h-3 w-3" />
                      Escalated: {exception.escalation_reason.replace(/_/g, " ")}
                    </span>
                    <div className="flex-1 h-px bg-red-200" />
                  </div>
                )}
                <div
                  className={clsx(
                    "flex gap-2",
                    msg.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  {msg.role === "assistant" && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500">
                      <Bot className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={clsx(
                      "max-w-[65%] rounded-lg px-4 py-2.5 text-sm",
                      msg.role === "user"
                        ? "bg-primary-600 text-white"
                        : "bg-gray-100 text-gray-900",
                    )}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.role === "assistant" && (
                      <div className="mt-1 flex items-center gap-2">
                        <ConfidenceBadge confidence={msg.confidence} />
                        <span className="text-[10px] text-gray-400">
                          {new Date(msg.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-3 space-y-2">
          <textarea
            ref={textareaRef}
            value={reply}
            onChange={(e) => {
              setReply(e.target.value);
              handleTextareaInput();
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type a reply... (Ctrl+Enter to send)"
            rows={2}
            className="block w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <Button
              variant="secondary"
              onClick={handleResolve}
              loading={resolving}
              size="sm"
            >
              Resolve
            </Button>
            <Button
              variant="secondary"
              onClick={() => handleReply(false)}
              loading={sending}
              disabled={!reply.trim()}
              size="sm"
            >
              Send Reply
            </Button>
            <Button
              onClick={() => handleReply(true)}
              loading={sending}
              disabled={!reply.trim()}
              size="sm"
            >
              Resolve & Reply
            </Button>
          </div>
        </div>
      </div>

      {/* Right panels */}
      <div className="w-80 space-y-4 overflow-auto">
        {/* Customer context */}
        <Card>
          <CardContent className="pt-5 pb-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900">
              Customer Context
            </h2>

            <div>
              <label className="text-xs font-medium text-gray-500">Name</label>
              <p className="text-sm text-gray-900">
                {exception.contact?.name ||
                  exception.conversation.contact_name ||
                  "Anonymous"}
              </p>
            </div>

            {(exception.contact?.email ||
              exception.conversation.contact_email) && (
              <div>
                <label className="text-xs font-medium text-gray-500">
                  Email
                </label>
                <p className="text-sm text-gray-900">
                  {exception.contact?.email ||
                    exception.conversation.contact_email}
                </p>
              </div>
            )}

            {exception.contact && (
              <>
                <div>
                  <label className="text-xs font-medium text-gray-500">
                    Lead Score
                  </label>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-sm font-semibold text-gray-900">
                      {exception.contact.lead_score}
                    </span>
                    {exception.contact.lead_tier && (
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${tierColors[exception.contact.lead_tier] || "bg-gray-100 text-gray-600"}`}
                      >
                        {exception.contact.lead_tier}
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-500">
                    Contact Since
                  </label>
                  <p className="text-sm text-gray-900">
                    {new Date(
                      exception.contact.created_at,
                    ).toLocaleDateString()}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Suggested action */}
        <Card className="border-primary-200 bg-primary-50/50">
          <CardContent className="pt-5 pb-5 space-y-3">
            <div className="flex items-center gap-2">
              <Headset className="h-4 w-4 text-primary-600" />
              <h2 className="text-sm font-semibold text-primary-900">
                Suggested Action
              </h2>
            </div>
            {exception.suggested_action ? (
              <p className="text-sm text-primary-800">
                {exception.suggested_action}
              </p>
            ) : (
              <div className="space-y-2">
                <div className="h-3 w-full rounded bg-primary-200/50 animate-pulse" />
                <div className="h-3 w-3/4 rounded bg-primary-200/50 animate-pulse" />
                <div className="h-3 w-1/2 rounded bg-primary-200/50 animate-pulse" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
    </div>
  );
}
