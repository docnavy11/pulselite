import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { X, Plus, Globe, Upload, AlignLeft, Map, HardDrive, Headphones, Cloud, FolderOpen, FileText, ArrowRight, CheckCircle2 } from "lucide-react";
import {
  createDocumentFromUrl,
  createDocumentFromFile,
  createDocumentFromText,
  startCrawl,
} from "@/lib/api-functions";

const parsePathList = (raw: string): string[] =>
  raw.split(",").map((s) => s.trim()).filter(Boolean);

const SOURCE_TYPES = [
  {
    id: "url" as const,
    label: "Web Page",
    description: "Crawl any public URL",
    icon: Globe,
    color: "#3b82f6",
    bg: "#eff6ff",
    darkBg: "rgba(59,130,246,0.12)",
  },
  {
    id: "upload" as const,
    label: "File Upload",
    description: "PDF, DOCX, TXT, CSV",
    icon: Upload,
    color: "#8b5cf6",
    bg: "#f5f3ff",
    darkBg: "rgba(139,92,246,0.12)",
  },
  {
    id: "text" as const,
    label: "Plain Text",
    description: "Paste text or Q&A pairs",
    icon: AlignLeft,
    color: "#f59e0b",
    bg: "#fffbeb",
    darkBg: "rgba(245,158,11,0.12)",
  },
  {
    id: "sitemap" as const,
    label: "Sitemap",
    description: "Crawl an entire site",
    icon: Map,
    color: "#10b981",
    bg: "#ecfdf5",
    darkBg: "rgba(16,185,129,0.12)",
  },
  {
    id: "google_drive" as const,
    label: "Google Drive",
    description: "Docs, Sheets, folders",
    icon: HardDrive,
    color: "#f97316",
    bg: "#fff7ed",
    darkBg: "rgba(249,115,22,0.12)",
  },
  {
    id: "zendesk" as const,
    label: "Zendesk",
    description: "Help Center articles",
    icon: Headphones,
    color: "#06b6d4",
    bg: "#ecfeff",
    darkBg: "rgba(6,182,212,0.12)",
  },
  {
    id: "salesforce" as const,
    label: "Salesforce",
    description: "Knowledge articles",
    icon: Cloud,
    color: "#0ea5e9",
    bg: "#f0f9ff",
    darkBg: "rgba(14,165,233,0.12)",
  },
  {
    id: "dropbox" as const,
    label: "Dropbox",
    description: "Files from any folder",
    icon: FolderOpen,
    color: "#6366f1",
    bg: "#eef2ff",
    darkBg: "rgba(99,102,241,0.12)",
  },
] as const;

type SourceId = (typeof SOURCE_TYPES)[number]["id"];

interface AddSourceModalProps {
  workspaceId: string;
  getKnowledgeBaseId: () => Promise<string>;
  onClose: () => void;
  onAdded: () => void;
}

export function AddSourceModal({
  workspaceId,
  getKnowledgeBaseId,
  onClose,
  onAdded,
}: AddSourceModalProps) {
  const [activeSource, setActiveSource] = useState<SourceId>("url");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const [urlInput, setUrlInput] = useState("");
  const [urls, setUrls] = useState<string[]>([]);
  const [urlError, setUrlError] = useState("");

  const [files, setFiles] = useState<File[]>([]);

  const [textContent, setTextContent] = useState("");
  const [textMode, setTextMode] = useState<"plain" | "qa">("plain");

  const [sitemapUrl, setSitemapUrl] = useState("");
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [googleDriveUrl, setGoogleDriveUrl] = useState("");
  const [zendeskSubdomain, setZendeskSubdomain] = useState("");
  const [dropboxFolderPath, setDropboxFolderPath] = useState("");

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
      "text/csv": [".csv"],
      "application/csv": [".csv"],
    },
  });

  function addUrl() {
    const trimmed = urlInput.trim();
    if (!trimmed) return;
    setUrlError("");
    try {
      const parsed = new URL(trimmed);
      if (!["http:", "https:"].includes(parsed.protocol)) {
        setUrlError("URL must start with http:// or https://");
        return;
      }
    } catch {
      setUrlError("Please enter a valid URL");
      return;
    }
    if (!urls.includes(trimmed)) {
      setUrls((prev) => [...prev, trimmed]);
      setUrlInput("");
    }
  }

  function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const knowledgeBaseId = await getKnowledgeBaseId();
      if (activeSource === "url") {
        await Promise.all(urls.map((url) => createDocumentFromUrl(workspaceId, { source_url: url, knowledge_base_id: knowledgeBaseId })));
      } else if (activeSource === "upload") {
        await Promise.all(files.map((file) => createDocumentFromFile(workspaceId, file, knowledgeBaseId)));
      } else if (activeSource === "text" && textContent.trim()) {
        await createDocumentFromText(workspaceId, { raw_content: textContent, content_type: textMode, knowledge_base_id: knowledgeBaseId });
      } else if (activeSource === "sitemap" && sitemapUrl.trim()) {
        await startCrawl(workspaceId, sitemapUrl.trim(), parsePathList(includePaths), parsePathList(excludePaths));
      } else if (activeSource === "google_drive" && googleDriveUrl.trim()) {
        await createDocumentFromUrl(workspaceId, { source_url: googleDriveUrl.trim(), source_type: "google_drive", knowledge_base_id: knowledgeBaseId });
      } else if (activeSource === "zendesk" && zendeskSubdomain.trim()) {
        await createDocumentFromUrl(workspaceId, { source_url: zendeskSubdomain.trim(), source_type: "zendesk", knowledge_base_id: knowledgeBaseId });
      } else if (activeSource === "salesforce") {
        await createDocumentFromUrl(workspaceId, { source_url: "salesforce", source_type: "salesforce", knowledge_base_id: knowledgeBaseId });
      } else if (activeSource === "dropbox") {
        await createDocumentFromUrl(workspaceId, { source_url: dropboxFolderPath.trim(), source_type: "dropbox", knowledge_base_id: knowledgeBaseId });
      }
      setDone(true);
      setTimeout(() => { onAdded(); }, 900);
    } catch {
      // handle error
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    (activeSource === "url" && urls.length > 0) ||
    (activeSource === "upload" && files.length > 0) ||
    (activeSource === "text" && textContent.trim().length > 0) ||
    (activeSource === "sitemap" && sitemapUrl.trim().length > 0) ||
    (activeSource === "google_drive" && googleDriveUrl.trim().length > 0) ||
    (activeSource === "zendesk" && zendeskSubdomain.trim().length > 0) ||
    activeSource === "salesforce" ||
    activeSource === "dropbox";

  const active = SOURCE_TYPES.find((s) => s.id === activeSource)!;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(9,9,18,0.75)", backdropFilter: "blur(8px)" }}
    >
      {/* Modal shell */}
      <div
        className="relative w-full flex overflow-hidden"
        style={{
          maxWidth: 860,
          maxHeight: "90vh",
          borderRadius: 20,
          background: "#0d0d14",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 40px 120px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
        }}
      >
        {/* Mesh gradient background */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage: `radial-gradient(ellipse 60% 50% at 80% -10%, ${active.color}18 0%, transparent 60%),
              radial-gradient(ellipse 40% 40% at 20% 110%, ${active.color}10 0%, transparent 50%)`,
            transition: "background-image 0.4s ease",
          }}
        />

        {/* Left sidebar — source picker */}
        <div
          className="flex-shrink-0 flex flex-col overflow-y-auto py-5"
          style={{
            width: 220,
            borderRight: "1px solid rgba(255,255,255,0.06)",
            gap: 0,
          }}
        >
          <div className="px-5 mb-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.3)" }}>
              Source type
            </p>
          </div>
          {SOURCE_TYPES.map((src) => {
            const Icon = src.icon;
            const isActive = activeSource === src.id;
            return (
              <button
                key={src.id}
                onClick={() => setActiveSource(src.id)}
                className="relative flex items-center gap-3 px-4 py-3 text-left transition-all duration-200"
                style={{
                  background: isActive ? src.darkBg : "transparent",
                  borderLeft: isActive ? `2px solid ${src.color}` : "2px solid transparent",
                }}
              >
                <div
                  className="flex-shrink-0 flex items-center justify-center rounded-lg"
                  style={{
                    width: 32,
                    height: 32,
                    background: isActive ? src.color + "22" : "rgba(255,255,255,0.06)",
                    color: isActive ? src.color : "rgba(255,255,255,0.4)",
                    transition: "all 0.2s",
                  }}
                >
                  <Icon size={15} />
                </div>
                <div>
                  <div
                    className="text-sm font-medium leading-none mb-0.5"
                    style={{ color: isActive ? "#fff" : "rgba(255,255,255,0.6)", transition: "color 0.2s" }}
                  >
                    {src.label}
                  </div>
                  <div className="text-[11px]" style={{ color: "rgba(255,255,255,0.28)" }}>
                    {src.description}
                  </div>
                </div>
                {isActive && (
                  <div className="ml-auto flex-shrink-0">
                    <div className="w-1.5 h-1.5 rounded-full" style={{ background: src.color }} />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Right panel — form */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {/* Panel header */}
          <div
            className="flex items-center justify-between px-7 pt-6 pb-5 flex-shrink-0"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
          >
            <div className="flex items-center gap-3">
              <div
                className="flex items-center justify-center rounded-xl"
                style={{ width: 40, height: 40, background: active.color + "20", color: active.color }}
              >
                <active.icon size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold leading-none mb-1" style={{ color: "#fff" }}>
                  {active.label}
                </h2>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>
                  {active.description}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="flex items-center justify-center rounded-lg transition-all duration-200"
              style={{
                width: 32,
                height: 32,
                background: "rgba(255,255,255,0.06)",
                color: "rgba(255,255,255,0.4)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.1)";
                (e.currentTarget as HTMLButtonElement).style.color = "#fff";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.06)";
                (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.4)";
              }}
            >
              <X size={15} />
            </button>
          </div>

          {/* Form body */}
          <div className="flex-1 px-7 py-6 space-y-4">

            {/* URL */}
            {activeSource === "url" && (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="https://docs.example.com/page"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addUrl(); } }}
                    className="flex-1 rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      border: urlError ? "1px solid #ef4444" : "1px solid rgba(255,255,255,0.1)",
                      color: "#fff",
                      fontFamily: "ui-monospace, monospace",
                    }}
                    onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                    onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = urlError ? "#ef4444" : "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                  />
                  <button
                    onClick={addUrl}
                    className="flex items-center justify-center rounded-lg px-3 transition-all duration-200"
                    style={{ background: active.color + "25", color: active.color, border: `1px solid ${active.color}40` }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = active.color + "40"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = active.color + "25"; }}
                  >
                    <Plus size={16} />
                  </button>
                </div>
                {urlError && <p className="text-xs" style={{ color: "#f87171" }}>{urlError}</p>}
                {urls.length > 0 && (
                  <div className="space-y-1.5 mt-2">
                    {urls.map((url) => (
                      <div
                        key={url}
                        className="flex items-center justify-between rounded-lg px-3 py-2"
                        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Globe size={13} style={{ color: active.color, flexShrink: 0 }} />
                          <span className="text-xs truncate" style={{ color: "rgba(255,255,255,0.7)", fontFamily: "ui-monospace, monospace" }}>{url}</span>
                        </div>
                        <button onClick={() => setUrls((p) => p.filter((u) => u !== url))} className="ml-2 flex-shrink-0 transition-colors duration-200" style={{ color: "rgba(255,255,255,0.25)" }} onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#f87171"; }} onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.25)"; }}>
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {urls.length === 0 && (
                  <p className="text-xs mt-1" style={{ color: "rgba(255,255,255,0.25)" }}>
                    Add one or more URLs and press Enter or click +
                  </p>
                )}
              </div>
            )}

            {/* File Upload */}
            {activeSource === "upload" && (
              <div className="space-y-3">
                <div
                  {...getRootProps()}
                  className="rounded-xl p-8 text-center cursor-pointer transition-all duration-200"
                  style={{
                    border: isDragActive ? `2px dashed ${active.color}` : "2px dashed rgba(255,255,255,0.12)",
                    background: isDragActive ? active.color + "10" : "rgba(255,255,255,0.03)",
                  }}
                >
                  <input {...getInputProps()} />
                  <div
                    className="mx-auto mb-3 flex items-center justify-center rounded-2xl"
                    style={{ width: 48, height: 48, background: active.color + "20", color: active.color }}
                  >
                    <Upload size={20} />
                  </div>
                  <p className="text-sm font-medium mb-1" style={{ color: isDragActive ? active.color : "rgba(255,255,255,0.7)" }}>
                    {isDragActive ? "Drop to add files" : "Drag & drop files here"}
                  </p>
                  <p className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>
                    or click to browse · PDF, DOCX, TXT, CSV
                  </p>
                </div>
                {files.length > 0 && (
                  <div className="space-y-1.5">
                    {files.map((file, i) => (
                      <div key={`${file.name}-${i}`} className="flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={13} style={{ color: active.color, flexShrink: 0 }} />
                          <span className="text-xs truncate" style={{ color: "rgba(255,255,255,0.7)" }}>{file.name}</span>
                          <span className="text-[10px] flex-shrink-0" style={{ color: "rgba(255,255,255,0.3)" }}>{formatFileSize(file.size)}</span>
                        </div>
                        <button onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))} className="ml-2 flex-shrink-0 transition-colors duration-200" style={{ color: "rgba(255,255,255,0.25)" }} onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#f87171"; }} onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.25)"; }}>
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Text */}
            {activeSource === "text" && (
              <div className="space-y-3">
                <div className="flex gap-1 rounded-lg p-1" style={{ background: "rgba(255,255,255,0.05)" }}>
                  {(["plain", "qa"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setTextMode(mode)}
                      className="flex-1 rounded-md py-1.5 text-xs font-medium transition-all duration-200"
                      style={{
                        background: textMode === mode ? active.color + "30" : "transparent",
                        color: textMode === mode ? active.color : "rgba(255,255,255,0.4)",
                        border: textMode === mode ? `1px solid ${active.color}50` : "1px solid transparent",
                      }}
                    >
                      {mode === "plain" ? "Plain text" : "Q&A pairs"}
                    </button>
                  ))}
                </div>
                {textMode === "qa" && (
                  <p className="text-xs rounded-lg px-3 py-2" style={{ color: active.color, background: active.color + "12", border: `1px solid ${active.color}20` }}>
                    Format: <span className="font-mono">Q: question</span> then <span className="font-mono">A: answer</span> on the next line
                  </p>
                )}
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  rows={8}
                  className="w-full rounded-lg px-4 py-3 text-sm outline-none transition-all duration-200 resize-none"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "#fff",
                    fontFamily: textMode === "qa" ? "ui-monospace, monospace" : "inherit",
                  }}
                  placeholder={textMode === "qa" ? "Q: What is your return policy?\nA: We offer 30-day returns on all items.\n\nQ: Do you ship internationally?\nA: Yes, we ship to 40+ countries." : "Paste your knowledge content here..."}
                  onFocus={(e) => { (e.target as HTMLTextAreaElement).style.borderColor = active.color; (e.target as HTMLTextAreaElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLTextAreaElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLTextAreaElement).style.boxShadow = "none"; }}
                />
              </div>
            )}

            {/* Sitemap */}
            {activeSource === "sitemap" && (
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="https://example.com/sitemap.xml"
                  value={sitemapUrl}
                  onChange={(e) => setSitemapUrl(e.target.value)}
                  className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontFamily: "ui-monospace, monospace" }}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                />
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>
                  Every URL in the sitemap will be crawled and indexed automatically.
                </p>

                {/* Include paths */}
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "rgba(255,255,255,0.5)" }}>
                    Include paths <span style={{ color: "rgba(255,255,255,0.25)", fontWeight: 400 }}>(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={includePaths}
                    onChange={(e) => setIncludePaths(e.target.value)}
                    placeholder="/blog, /docs"
                    className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontFamily: "ui-monospace, monospace" }}
                    onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                    onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                  />
                  <p className="mt-1 text-[11px]" style={{ color: "rgba(255,255,255,0.25)" }}>Only crawl URLs matching these path prefixes. Leave empty to crawl all pages.</p>
                </div>

                {/* Exclude paths */}
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "rgba(255,255,255,0.5)" }}>
                    Exclude paths <span style={{ color: "rgba(255,255,255,0.25)", fontWeight: 400 }}>(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={excludePaths}
                    onChange={(e) => setExcludePaths(e.target.value)}
                    placeholder="/admin, /private"
                    className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                    style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontFamily: "ui-monospace, monospace" }}
                    onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                    onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                  />
                  <p className="mt-1 text-[11px]" style={{ color: "rgba(255,255,255,0.25)" }}>Skip URLs matching these path prefixes.</p>
                </div>
              </div>
            )}

            {/* Google Drive */}
            {activeSource === "google_drive" && (
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="https://docs.google.com/document/d/..."
                  value={googleDriveUrl}
                  onChange={(e) => setGoogleDriveUrl(e.target.value)}
                  className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontFamily: "ui-monospace, monospace" }}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                />
                <div className="rounded-lg px-4 py-3 text-xs space-y-1" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
                  <p style={{ color: "rgba(255,255,255,0.5)" }}>Paste a Google Doc, Sheet, or Drive folder URL. Connect Google Drive in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.</p>
                </div>
              </div>
            )}

            {/* Zendesk */}
            {activeSource === "zendesk" && (
              <div className="space-y-3">
                <div className="flex items-center rounded-lg overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.1)" }}>
                  <span className="px-3 py-2.5 text-xs flex-shrink-0" style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.3)", borderRight: "1px solid rgba(255,255,255,0.1)" }}>subdomain</span>
                  <input
                    type="text"
                    placeholder="mycompany"
                    value={zendeskSubdomain}
                    onChange={(e) => setZendeskSubdomain(e.target.value)}
                    className="flex-1 px-3 py-2.5 text-sm outline-none"
                    style={{ background: "rgba(255,255,255,0.04)", color: "#fff" }}
                  />
                  <span className="px-3 py-2.5 text-xs flex-shrink-0" style={{ background: "rgba(255,255,255,0.06)", color: "rgba(255,255,255,0.3)", borderLeft: "1px solid rgba(255,255,255,0.1)" }}>.zendesk.com</span>
                </div>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>
                  All published Help Center articles will be ingested. Connect Zendesk in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.
                </p>
              </div>
            )}

            {/* Salesforce */}
            {activeSource === "salesforce" && (
              <div className="rounded-xl p-5 space-y-3" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center rounded-lg" style={{ width: 40, height: 40, background: active.color + "20", color: active.color }}>
                    <Cloud size={18} />
                  </div>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "#fff" }}>Salesforce Knowledge</p>
                    <p className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>All published articles will be synced</p>
                  </div>
                </div>
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.35)" }}>
                  Connect Salesforce in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> before importing. Articles are fetched from the Knowledge object and indexed automatically.
                </p>
              </div>
            )}

            {/* Dropbox */}
            {activeSource === "dropbox" && (
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="/My Knowledge Base"
                  value={dropboxFolderPath}
                  onChange={(e) => setDropboxFolderPath(e.target.value)}
                  className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                  style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "#fff", fontFamily: "ui-monospace, monospace" }}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.1)"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                />
                <p className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>
                  Leave blank to ingest from root. Supported: .txt, .md, .csv, .rst. Connect Dropbox in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div
            className="flex items-center justify-between px-7 py-4 flex-shrink-0"
            style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
          >
            <button
              onClick={onClose}
              className="text-sm px-4 py-2 rounded-lg transition-all duration-200"
              style={{ color: "rgba(255,255,255,0.4)", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)"; (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.7)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)"; (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.4)"; }}
            >
              Cancel
            </button>

            <button
              onClick={handleSubmit}
              disabled={!canSubmit || submitting || done}
              className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: done ? "#10b981" : active.color,
                color: "#fff",
                boxShadow: canSubmit && !done ? `0 0 20px ${active.color}40` : "none",
              }}
            >
              {done ? (
                <>
                  <CheckCircle2 size={15} />
                  Added!
                </>
              ) : submitting ? (
                <>
                  <div className="h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Adding…
                </>
              ) : (
                <>
                  Add {active.label}
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
