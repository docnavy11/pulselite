import { useState, useCallback, useMemo } from "react";
import { useDropzone } from "react-dropzone";
import { X, Plus, Globe, Upload, AlignLeft, HardDrive, Headphones, Cloud, FolderOpen, FileText, ArrowRight, CheckCircle2, ChevronRight, FolderClosed } from "lucide-react";
import {
  createDocumentFromUrl,
  createDocumentFromFile,
  createDocumentFromText,
  previewCrawl,
  startCrawl,
} from "@/lib/api-functions";

// --- Directory tree helpers ---

interface DirNode {
  path: string;       // e.g. "/blog" or "/blog/2024"
  label: string;      // e.g. "blog" or "2024"
  pageCount: number;  // pages directly at or under this prefix
  children: DirNode[];
}

function buildDirTree(urls: string[]): DirNode[] {
  const pathCounts = new Map<string, number>();

  for (const url of urls) {
    try {
      const path = new URL(url).pathname;
      const segments = path.split("/").filter(Boolean);
      // Count at depth 0 (root), depth 1, depth 2
      if (segments.length === 0) {
        pathCounts.set("/", (pathCounts.get("/") || 0) + 1);
      } else {
        const lvl1 = "/" + segments[0];
        if (segments.length === 1) {
          pathCounts.set(lvl1, (pathCounts.get(lvl1) || 0) + 1);
        } else {
          const lvl2 = "/" + segments[0] + "/" + segments[1];
          pathCounts.set(lvl2, (pathCounts.get(lvl2) || 0) + 1);
        }
      }
    } catch {
      // skip malformed URLs
    }
  }

  // Build two-level tree
  const level1Map = new Map<string, DirNode>();
  let rootCount = pathCounts.get("/") || 0;

  for (const [path, count] of pathCounts) {
    if (path === "/") continue;
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 1) {
      // Level 1 directory
      const existing = level1Map.get(path);
      if (existing) {
        existing.pageCount += count;
      } else {
        level1Map.set(path, { path, label: segments[0], pageCount: count, children: [] });
      }
    } else {
      // Level 2 directory
      const parentPath = "/" + segments[0];
      let parent = level1Map.get(parentPath);
      if (!parent) {
        parent = { path: parentPath, label: segments[0], pageCount: 0, children: [] };
        level1Map.set(parentPath, parent);
      }
      parent.children.push({ path, label: segments[1], pageCount: count, children: [] });
    }
  }

  const nodes: DirNode[] = [];
  if (rootCount > 0) {
    nodes.push({ path: "/", label: "/", pageCount: rootCount, children: [] });
  }
  for (const node of level1Map.values()) {
    nodes.push(node);
  }
  // Sort by path
  nodes.sort((a, b) => a.path.localeCompare(b.path));
  for (const n of nodes) {
    n.children.sort((a, b) => a.path.localeCompare(b.path));
  }
  return nodes;
}

function countPagesInNode(node: DirNode): number {
  return node.pageCount + node.children.reduce((s, c) => s + c.pageCount, 0);
}

function DirTreeNode({ node, excludedDirs, onToggle, color, depth }: {
  node: DirNode;
  excludedDirs: Set<string>;
  onToggle: (path: string, node: DirNode) => void;
  color: string;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const isExcluded = excludedDirs.has(node.path);
  const totalPages = countPagesInNode(node);
  const hasChildren = node.children.length > 0;

  // Check if any children are excluded (partial state)
  const someChildrenExcluded = hasChildren && node.children.some(c => excludedDirs.has(c.path));
  const allChildrenExcluded = hasChildren && node.children.every(c => excludedDirs.has(c.path));
  const isIndeterminate = !isExcluded && someChildrenExcluded && !allChildrenExcluded;

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 hover:bg-gray-50 transition-colors cursor-pointer select-none"
        style={{ paddingLeft: 12 + depth * 20, paddingRight: 12 }}
        onClick={() => onToggle(node.path, node)}
      >
        {/* Expand/collapse arrow */}
        {hasChildren ? (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ChevronRight size={12} className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
          </button>
        ) : (
          <span className="w-3" />
        )}

        {/* Checkbox */}
        <div
          className="flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-all"
          style={{
            borderColor: isExcluded ? "#d1d5db" : color,
            background: isExcluded ? "#fff" : isIndeterminate ? color + "40" : color + "15",
          }}
        >
          {!isExcluded && !isIndeterminate && (
            <svg width="10" height="10" viewBox="0 0 10 10">
              <path d="M2 5l2 2 4-4" stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
          {isIndeterminate && (
            <div className="w-2 h-0.5 rounded-full" style={{ background: color }} />
          )}
        </div>

        {/* Folder icon + label */}
        <FolderClosed size={13} className="flex-shrink-0" style={{ color: isExcluded ? "#d1d5db" : "#6b7280" }} />
        <span
          className="text-xs font-medium truncate"
          style={{ color: isExcluded ? "#d1d5db" : "#374151" }}
        >
          {node.label}
        </span>
        <span className="text-[10px] ml-auto flex-shrink-0" style={{ color: isExcluded ? "#e5e7eb" : "#9ca3af" }}>
          {totalPages} {totalPages === 1 ? "page" : "pages"}
        </span>
      </div>

      {/* Children */}
      {hasChildren && expanded && node.children.map(child => (
        <DirTreeNode
          key={child.path}
          node={child}
          excludedDirs={excludedDirs}
          onToggle={onToggle}
          color={color}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

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
    id: "website" as const,
    label: "Full Website",
    description: "Scan & crawl an entire site",
    icon: Globe,
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
  chatbotId?: string;
  getKnowledgeBaseId: () => Promise<string>;
  onClose: () => void;
  onAdded: () => void;
}

export function AddSourceModal({
  workspaceId,
  chatbotId,
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

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const [discoveredUrls, setDiscoveredUrls] = useState<string[] | null>(null);
  const [discoverySource, setDiscoverySource] = useState<string>("");
  const [excludedDirs, setExcludedDirs] = useState<Set<string>>(new Set());
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

  async function handleScan() {
    const trimmed = websiteUrl.trim();
    if (!trimmed) return;
    setScanError("");
    try {
      new URL(trimmed);
    } catch {
      setScanError("Please enter a valid URL");
      return;
    }
    setScanning(true);
    try {
      const result = await previewCrawl(workspaceId, trimmed);
      if (result.urls.length === 0) {
        setScanError("No pages found. Check that the URL is correct and the site is publicly accessible.");
        return;
      }
      setDiscoveredUrls(result.urls);
      setDiscoverySource(result.source);
      setExcludedDirs(new Set());
    } catch {
      setScanError("Failed to scan website. Check the URL and try again.");
    } finally {
      setScanning(false);
    }
  }

  function toggleDir(path: string, node: DirNode) {
    setExcludedDirs((prev) => {
      const next = new Set(prev);
      const isExcluded = next.has(path);
      if (isExcluded) {
        // Re-include this dir and all children
        next.delete(path);
        for (const child of node.children) {
          next.delete(child.path);
        }
      } else {
        // Exclude this dir and all children
        next.add(path);
        for (const child of node.children) {
          next.add(child.path);
        }
      }
      return next;
    });
  }

  const selectedPageCount = useMemo(() => {
    if (!discoveredUrls) return 0;
    return discoveredUrls.filter((url) => {
      try {
        const path = new URL(url).pathname;
        const segments = path.split("/").filter(Boolean);
        if (segments.length === 0) return !excludedDirs.has("/");
        const lvl1 = "/" + segments[0];
        if (excludedDirs.has(lvl1)) return false;
        if (segments.length >= 2) {
          const lvl2 = "/" + segments[0] + "/" + segments[1];
          if (excludedDirs.has(lvl2)) return false;
        }
        return true;
      } catch {
        return true;
      }
    }).length;
  }, [discoveredUrls, excludedDirs]);

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
      } else if (activeSource === "website" && discoveredUrls) {
        const excludePaths = Array.from(excludedDirs);
        await startCrawl(workspaceId, websiteUrl.trim(), [], excludePaths, chatbotId, knowledgeBaseId);
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
    (activeSource === "website" && discoveredUrls !== null && discoveredUrls.length > 0) ||
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
          background: "#fff",
          border: "1px solid #e5e7eb",
          boxShadow: "0 25px 60px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05)",
        }}
      >

        {/* Left sidebar — source picker */}
        <div
          className="flex-shrink-0 flex flex-col overflow-y-auto py-5"
          style={{
            width: 220,
            borderRight: "1px solid #f0f0f0",
            background: "#fafafa",
            gap: 0,
          }}
        >
          <div className="px-5 mb-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
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
                  background: isActive ? src.bg : "transparent",
                  borderLeft: isActive ? `2px solid ${src.color}` : "2px solid transparent",
                }}
              >
                <div
                  className="flex-shrink-0 flex items-center justify-center rounded-lg"
                  style={{
                    width: 32,
                    height: 32,
                    background: isActive ? src.color + "18" : "#f0f0f0",
                    color: isActive ? src.color : "#9ca3af",
                    transition: "all 0.2s",
                  }}
                >
                  <Icon size={15} />
                </div>
                <div>
                  <div
                    className="text-sm font-medium leading-none mb-0.5"
                    style={{ color: isActive ? "#111827" : "#6b7280", transition: "color 0.2s" }}
                  >
                    {src.label}
                  </div>
                  <div className="text-[11px] text-gray-400">
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
            style={{ borderBottom: "1px solid #f0f0f0" }}
          >
            <div className="flex items-center gap-3">
              <div
                className="flex items-center justify-center rounded-xl"
                style={{ width: 40, height: 40, background: active.color + "14", color: active.color }}
              >
                <active.icon size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold leading-none mb-1 text-gray-900">
                  {active.label}
                </h2>
                <p className="text-xs text-gray-400">
                  {active.description}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="flex items-center justify-center rounded-lg transition-all duration-200 hover:bg-gray-100"
              style={{
                width: 32,
                height: 32,
                background: "#f5f5f5",
                color: "#9ca3af",
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
                      background: "#f9fafb",
                      border: urlError ? "1px solid #ef4444" : "1px solid #e5e7eb",
                      color: "#111827",
                      fontFamily: "ui-monospace, monospace",
                    }}
                    onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                    onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = urlError ? "#ef4444" : "#e5e7eb"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
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
                        style={{ background: "#f9fafb", border: "1px solid #e5e7eb" }}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Globe size={13} style={{ color: active.color, flexShrink: 0 }} />
                          <span className="text-xs truncate" style={{ color: "#374151", fontFamily: "ui-monospace, monospace" }}>{url}</span>
                        </div>
                        <button onClick={() => setUrls((p) => p.filter((u) => u !== url))} className="ml-2 flex-shrink-0 transition-colors duration-200" style={{ color: "#d1d5db" }} onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#f87171"; }} onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#d1d5db"; }}>
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {urls.length === 0 && (
                  <p className="text-xs mt-1" style={{ color: "#d1d5db" }}>
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
                    border: isDragActive ? `2px dashed ${active.color}` : "2px dashed #e5e7eb",
                    background: isDragActive ? active.color + "10" : "#fafafa",
                  }}
                >
                  <input {...getInputProps()} />
                  <div
                    className="mx-auto mb-3 flex items-center justify-center rounded-2xl"
                    style={{ width: 48, height: 48, background: active.color + "20", color: active.color }}
                  >
                    <Upload size={20} />
                  </div>
                  <p className="text-sm font-medium mb-1" style={{ color: isDragActive ? active.color : "#374151" }}>
                    {isDragActive ? "Drop to add files" : "Drag & drop files here"}
                  </p>
                  <p className="text-xs" style={{ color: "#9ca3af" }}>
                    or click to browse · PDF, DOCX, TXT, CSV
                  </p>
                </div>
                {files.length > 0 && (
                  <div className="space-y-1.5">
                    {files.map((file, i) => (
                      <div key={`${file.name}-${i}`} className="flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "#f9fafb", border: "1px solid #e5e7eb" }}>
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={13} style={{ color: active.color, flexShrink: 0 }} />
                          <span className="text-xs truncate" style={{ color: "#374151" }}>{file.name}</span>
                          <span className="text-[10px] flex-shrink-0" style={{ color: "#9ca3af" }}>{formatFileSize(file.size)}</span>
                        </div>
                        <button onClick={() => setFiles((p) => p.filter((_, idx) => idx !== i))} className="ml-2 flex-shrink-0 transition-colors duration-200" style={{ color: "#d1d5db" }} onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#f87171"; }} onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#d1d5db"; }}>
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
                <div className="flex gap-1 rounded-lg p-1" style={{ background: "#f3f4f6" }}>
                  {(["plain", "qa"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setTextMode(mode)}
                      className="flex-1 rounded-md py-1.5 text-xs font-medium transition-all duration-200"
                      style={{
                        background: textMode === mode ? active.color + "30" : "transparent",
                        color: textMode === mode ? active.color : "#9ca3af",
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
                    background: "#f9fafb",
                    border: "1px solid #e5e7eb",
                    color: "#111827",
                    fontFamily: textMode === "qa" ? "ui-monospace, monospace" : "inherit",
                  }}
                  placeholder={textMode === "qa" ? "Q: What is your return policy?\nA: We offer 30-day returns on all items.\n\nQ: Do you ship internationally?\nA: Yes, we ship to 40+ countries." : "Paste your knowledge content here..."}
                  onFocus={(e) => { (e.target as HTMLTextAreaElement).style.borderColor = active.color; (e.target as HTMLTextAreaElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLTextAreaElement).style.borderColor = "#e5e7eb"; (e.target as HTMLTextAreaElement).style.boxShadow = "none"; }}
                />
              </div>
            )}

            {/* Full Website */}
            {activeSource === "website" && (
              <div className="space-y-3">
                {!discoveredUrls ? (
                  <>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="https://example.com"
                        value={websiteUrl}
                        onChange={(e) => { setWebsiteUrl(e.target.value); setScanError(""); }}
                        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleScan(); } }}
                        disabled={scanning}
                        className="flex-1 rounded-lg px-4 py-2.5 text-sm outline-none transition-all duration-200"
                        style={{
                          background: "#f9fafb",
                          border: scanError ? "1px solid #ef4444" : "1px solid #e5e7eb",
                          color: "#111827",
                          fontFamily: "ui-monospace, monospace",
                        }}
                        onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                        onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = scanError ? "#ef4444" : "#e5e7eb"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                      />
                      <button
                        onClick={handleScan}
                        disabled={scanning || !websiteUrl.trim()}
                        className="flex items-center gap-2 rounded-lg px-4 text-sm font-medium transition-all duration-200 disabled:opacity-40"
                        style={{ background: active.color + "20", color: active.color, border: `1px solid ${active.color}40` }}
                      >
                        {scanning ? (
                          <>
                            <div className="h-3.5 w-3.5 rounded-full border-2 border-current/30 border-t-current animate-spin" />
                            Scanning…
                          </>
                        ) : (
                          "Scan"
                        )}
                      </button>
                    </div>
                    {scanError && <p className="text-xs" style={{ color: "#f87171" }}>{scanError}</p>}
                    {!scanning && (
                      <p className="text-xs" style={{ color: "#9ca3af" }}>
                        Enter a website URL to discover its pages via sitemap or link crawling.
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    {/* Summary */}
                    <div className="flex items-center justify-between">
                      <p className="text-xs" style={{ color: "#6b7280" }}>
                        Found <span className="font-medium text-gray-900">{discoveredUrls.length}</span> pages
                        {discoverySource === "sitemap" ? " via sitemap" : " via link crawling"}
                      </p>
                      <button
                        onClick={() => { setDiscoveredUrls(null); setExcludedDirs(new Set()); setScanError(""); }}
                        className="text-xs transition-colors"
                        style={{ color: active.color }}
                      >
                        Rescan
                      </button>
                    </div>

                    {/* Directory tree */}
                    <div
                      className="rounded-lg overflow-y-auto"
                      style={{ border: "1px solid #e5e7eb", maxHeight: 260 }}
                    >
                      {buildDirTree(discoveredUrls).map((node) => (
                        <DirTreeNode
                          key={node.path}
                          node={node}
                          excludedDirs={excludedDirs}
                          onToggle={toggleDir}
                          color={active.color}
                          depth={0}
                        />
                      ))}
                    </div>

                    {/* Selected count */}
                    <p className="text-xs" style={{ color: "#9ca3af" }}>
                      {selectedPageCount} of {discoveredUrls.length} pages selected
                    </p>
                  </>
                )}
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
                  style={{ background: "#f9fafb", border: "1px solid #e5e7eb", color: "#111827", fontFamily: "ui-monospace, monospace" }}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "#e5e7eb"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                />
                <div className="rounded-lg px-4 py-3 text-xs space-y-1" style={{ background: "#f9fafb", border: "1px solid #e5e7eb" }}>
                  <p style={{ color: "#6b7280" }}>Paste a Google Doc, Sheet, or Drive folder URL. Connect Google Drive in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.</p>
                </div>
              </div>
            )}

            {/* Zendesk */}
            {activeSource === "zendesk" && (
              <div className="space-y-3">
                <div className="flex items-center rounded-lg overflow-hidden" style={{ border: "1px solid #e5e7eb" }}>
                  <span className="px-3 py-2.5 text-xs flex-shrink-0" style={{ background: "#f9fafb", color: "#9ca3af", borderRight: "1px solid #e5e7eb" }}>subdomain</span>
                  <input
                    type="text"
                    placeholder="mycompany"
                    value={zendeskSubdomain}
                    onChange={(e) => setZendeskSubdomain(e.target.value)}
                    className="flex-1 px-3 py-2.5 text-sm outline-none"
                    style={{ background: "#f9fafb", color: "#111827" }}
                  />
                  <span className="px-3 py-2.5 text-xs flex-shrink-0" style={{ background: "#f9fafb", color: "#9ca3af", borderLeft: "1px solid #e5e7eb" }}>.zendesk.com</span>
                </div>
                <p className="text-xs" style={{ color: "#9ca3af" }}>
                  All published Help Center articles will be ingested. Connect Zendesk in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.
                </p>
              </div>
            )}

            {/* Salesforce */}
            {activeSource === "salesforce" && (
              <div className="rounded-xl p-5 space-y-3" style={{ background: "#f9fafb", border: "1px solid #e5e7eb" }}>
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center rounded-lg" style={{ width: 40, height: 40, background: active.color + "20", color: active.color }}>
                    <Cloud size={18} />
                  </div>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "#111827" }}>Salesforce Knowledge</p>
                    <p className="text-xs" style={{ color: "#9ca3af" }}>All published articles will be synced</p>
                  </div>
                </div>
                <p className="text-xs" style={{ color: "#9ca3af" }}>
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
                  style={{ background: "#f9fafb", border: "1px solid #e5e7eb", color: "#111827", fontFamily: "ui-monospace, monospace" }}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = active.color; (e.target as HTMLInputElement).style.boxShadow = `0 0 0 3px ${active.color}20`; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "#e5e7eb"; (e.target as HTMLInputElement).style.boxShadow = "none"; }}
                />
                <p className="text-xs" style={{ color: "#9ca3af" }}>
                  Leave blank to ingest from root. Supported: .txt, .md, .csv, .rst. Connect Dropbox in <a href="/settings/integrations" className="underline" style={{ color: active.color }}>Settings → Integrations</a> first.
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div
            className="flex items-center justify-between px-7 py-4 flex-shrink-0"
            style={{ borderTop: "1px solid #f0f0f0" }}
          >
            <button
              onClick={onClose}
              className="text-sm px-4 py-2 rounded-lg transition-all duration-200 hover:bg-gray-100"
              style={{ color: "#6b7280", background: "#f9fafb", border: "1px solid #e5e7eb" }}
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
                boxShadow: canSubmit && !done ? `0 0 20px ${active.color}30` : "none",
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
                  {activeSource === "website" ? `Crawl ${selectedPageCount} pages` : `Add ${active.label}`}
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
