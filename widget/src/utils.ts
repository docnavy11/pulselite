export function generateId(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

export function renderMarkdownLite(text: string): string {
  let html = escapeHtml(text);

  // Code blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="pulse-code-block">$1</pre>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="pulse-inline-code">$1</code>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Links (only allow http/https to prevent XSS via javascript: URLs)
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="pulse-list">$&</ul>');

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Line breaks
  html = html.replace(/\n/g, "<br>");

  return html;
}

export interface CitationSource {
  index: number;
  title: string;
  url: string;
}

export function renderMarkdownWithSources(text: string, sources: CitationSource[]): string {
  let html = renderMarkdownLite(text);

  if (sources.length === 0) return html;

  // Replace [1], [2] etc. with superscript links
  sources.forEach((source) => {
    const link = `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer" class="pulse-citation" title="${escapeHtml(source.title)}">[${source.index}]</a>`;
    html = html.replace(new RegExp(`\\[${source.index}\\]`, "g"), link);
  });

  // Append footnotes
  const footnotes = sources
    .map(
      (s) =>
        `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="pulse-footnote-link">${escapeHtml(s.title)}</a></li>`
    )
    .join("");
  html += `<ol class="pulse-footnotes">${footnotes}</ol>`;

  return html;
}
