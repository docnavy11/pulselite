"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Article } from "@/lib/types";
import {
  getArticle,
  updateArticle,
  deleteArticle,
  publishArticle,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

export default function ArticleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const articleId = params.id as string;
  const [article, setArticle] = useState<Article | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getArticle(workspace.id, articleId)
      .then((art) => {
        setArticle(art);
        setTitle(art.title);
        setBody(art.body || "");
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace, articleId]);

  async function handleSave() {
    if (!workspace) return;
    setSaving(true);
    try {
      const updated = await updateArticle(workspace.id, articleId, { title, body });
      setArticle(updated);
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!workspace) return;
    setPublishing(true);
    try {
      await updateArticle(workspace.id, articleId, { title, body });
      const published = await publishArticle(workspace.id, articleId);
      setArticle(published);
    } catch {
      // handle error
    } finally {
      setPublishing(false);
    }
  }

  async function handleDelete() {
    if (!workspace) return;
    try {
      await deleteArticle(workspace.id, articleId);
      router.back();
    } catch {
      // handle error
    }
  }

  if (loading || !article) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  const stateVariant: Record<string, "default" | "success" | "warning"> = {
    draft: "default",
    published: "success",
    ai_draft_pending: "warning",
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Edit Article</h1>
          <Badge variant={stateVariant[article.state] || "default"}>
            {article.state.replace("_", " ")}
          </Badge>
        </div>
        <button
          onClick={() => setShowDelete(true)}
          className="rounded p-2 text-gray-400 hover:bg-red-50 hover:text-red-600 transition-all duration-200"
          title="Delete article"
        >
          <Trash2 className="h-5 w-5" />
        </button>
      </div>

      <div className="space-y-4">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="block w-full text-2xl font-bold border-0 border-b border-gray-200 pb-2 focus:outline-none focus:border-primary-500 transition-all duration-200 bg-transparent"
          placeholder="Article title"
        />

        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={20}
          className="block w-full rounded-lg border border-gray-200 px-4 py-3 text-sm font-mono leading-relaxed placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all duration-200"
          placeholder="Write your article content here... (Markdown supported)"
        />

        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-gray-400">Markdown supported</p>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={handleSave}
              loading={saving}
            >
              Save Draft
            </Button>
            <Button onClick={handlePublish} loading={publishing}>
              Publish
            </Button>
          </div>
        </div>
      </div>

      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 shadow-lg">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Delete Article
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Are you sure you want to delete this article? This action cannot
              be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <Button
                variant="secondary"
                onClick={() => setShowDelete(false)}
              >
                Cancel
              </Button>
              <Button variant="danger" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
