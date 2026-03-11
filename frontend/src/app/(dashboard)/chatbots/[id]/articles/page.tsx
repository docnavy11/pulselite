import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Plus, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Article, KnowledgeBase } from "@/lib/types";
import {
  getArticles,
  createArticle,
  getKnowledgeBases,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const stateVariant: Record<string, "default" | "success" | "warning"> = {
  draft: "default",
  published: "success",
  ai_draft_pending: "warning",
};

export default function ArticlesPage() {
  const { id: chatbotId } = useParams() as { id: string };
  const navigate = useNavigate();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [articles, setArticles] = useState<Article[]>([]);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    async function load() {
      if (!workspace) return;
      try {
        const kbs = await getKnowledgeBases(workspace.id, chatbotId);
        if (kbs.length > 0) {
          setKnowledgeBase(kbs[0]);
          const arts = await getArticles(workspace.id);
          setArticles(arts);
        }
      } catch {
        // handle error
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [workspace, chatbotId]);

  async function handleNewArticle() {
    if (!knowledgeBase || !workspace) return;
    setCreating(true);
    try {
      const article = await createArticle(workspace.id, {
        title: "Untitled Article",
      });
      navigate(`/articles/${article.id}`);
    } catch {
      // handle error
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Articles</h1>
        <Button onClick={handleNewArticle} loading={creating}>
          <Plus className="h-4 w-4 mr-2" />
          New Article
        </Button>
      </div>

      {articles.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-gray-400">
            <FileText className="h-10 w-10 mb-3" />
            <p className="text-sm font-medium">No articles yet</p>
            <p className="text-xs mt-1">
              Create articles to add to the knowledge base
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Title
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  State
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Updated
                </th>
              </tr>
            </thead>
            <tbody>
              {articles.map((article) => (
                <tr
                  key={article.id}
                  onClick={() => navigate(`/articles/${article.id}`)}
                  className="border-b border-gray-100 last:border-0 cursor-pointer hover:bg-gray-50 transition-all duration-200"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {article.title}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={stateVariant[article.state] || "default"}>
                      {article.state.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(article.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
