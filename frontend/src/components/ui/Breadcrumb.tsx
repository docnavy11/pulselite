"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SEGMENT_LABELS: Record<string, string> = {
  dashboard: "Overview",
  chatbots: "Chatbots",
  conversations: "Conversations",
  intelligence: "Intelligence",
  settings: "Settings",
  sources: "Knowledge",
  settings_tab: "Configure",
  actions: "Actions",
  customize: "Appearance",
  chat: "Test",
  deploy: "Publish",
  team: "Team",
  billing: "Billing",
  integrations: "Integrations",
  llm: "AI Models",
  security: "Security",
  "data-retention": "Data Retention",
  webhooks: "Webhooks",
};

function segmentLabel(seg: string): string {
  return SEGMENT_LABELS[seg] ?? seg.charAt(0).toUpperCase() + seg.slice(1);
}

export function Breadcrumb() {
  const pathname = usePathname();
  // Split path into segments, filter empty
  const rawSegments = pathname.split("/").filter(Boolean);

  // Build crumbs: skip UUIDs (they'll be shown as the chatbot name via a parent)
  const crumbs: { label: string; href: string }[] = [];
  let href = "";
  for (const seg of rawSegments) {
    href += `/${seg}`;
    // Skip UUID-looking segments at the top level label (they'd need async resolution)
    const isUuid = /^[0-9a-f-]{36}$/.test(seg);
    crumbs.push({ label: isUuid ? "…" : segmentLabel(seg), href });
  }

  if (crumbs.length === 0) return null;

  if (crumbs.length === 1) {
    return <span className="text-[13px] font-semibold text-gray-800">{crumbs[0].label}</span>;
  }

  return (
    <nav className="flex items-center gap-1 text-[12px]">
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={crumb.href} className="flex items-center gap-1">
            {i > 0 && <span className="text-gray-300">›</span>}
            {isLast ? (
              <span className="font-semibold text-gray-800">{crumb.label}</span>
            ) : (
              <Link href={crumb.href} className="text-gray-400 hover:text-gray-600 transition-colors">
                {crumb.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
