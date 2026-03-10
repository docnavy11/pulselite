"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  chatbotId: string;
}

const TABS = [
  { label: "Sources", href: (id: string) => `/chatbots/${id}` },
  { label: "Settings", href: (id: string) => `/chatbots/${id}` },
  { label: "Actions", href: (id: string) => `/chatbots/${id}/actions` },
  { label: "Chat", href: (id: string) => `/chatbots/${id}/chat` },
  { label: "Customize", href: (id: string) => `/chatbots/${id}/customize` },
  { label: "Deploy", href: (id: string) => `/chatbots/${id}/deploy` },
];

export function ChatbotTabNav({ chatbotId }: Props) {
  const pathname = usePathname();

  function isActive(label: string, href: string): boolean {
    if (label === "Sources" || label === "Settings") {
      return pathname === `/chatbots/${chatbotId}`;
    }
    return pathname.startsWith(href);
  }

  return (
    <div className="border-b border-gray-200 mb-6">
      <nav className="-mb-px flex gap-6 items-center">
        <Link
          href={`/chatbots/${chatbotId}`}
          className="text-sm text-gray-500 hover:text-gray-700 pb-3 block mr-4"
        >
          ← Back to Chatbots
        </Link>
        {TABS.map((tab) => {
          const href = tab.href(chatbotId);
          const active = isActive(tab.label, href);
          return (
            <Link
              key={tab.label}
              href={href}
              className={`pb-3 text-sm font-medium border-b-2 ${
                active
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
