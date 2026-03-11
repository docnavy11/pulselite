import { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  FileQuestion,
  Users,
  MessageSquareText,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  Globe,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { useCopilot } from "@/components/copilot/CopilotProvider";

const sections = [
  {
    href: "/intelligence/gaps",
    label: "Documentation Gaps",
    description:
      "Identify topics your knowledge base doesn't cover and auto-generate draft articles.",
    icon: FileQuestion,
    color: "text-red-600 bg-red-50",
  },
  {
    href: "/intelligence/leads",
    label: "Lead Intelligence",
    description: "Score and tier contacts based on conversation signals.",
    icon: Users,
    color: "text-purple-600 bg-purple-50",
  },
  {
    href: "/intelligence/topics",
    label: "Topic Intelligence",
    description: "Discover what customers are asking about most.",
    icon: MessageSquareText,
    color: "text-blue-600 bg-blue-50",
  },
  {
    href: "/intelligence/sentiment",
    label: "Sentiment Trends",
    description: "Track customer satisfaction trends over time.",
    icon: TrendingUp,
    color: "text-green-600 bg-green-50",
  },
  {
    href: "/intelligence/features",
    label: "Feature Requests",
    description: "Extract and cluster feature requests from conversations.",
    icon: Lightbulb,
    color: "text-amber-600 bg-amber-50",
  },
  {
    href: "/intelligence/competitive",
    label: "Competitive Intelligence",
    description: "Track competitor mentions, churn risk, and expansion signals from conversations.",
    icon: TrendingDown,
    color: "text-orange-600 bg-orange-50",
  },
  {
    href: "/intelligence/geography",
    label: "Geography",
    description: "See which countries your chat visitors are coming from.",
    icon: Globe,
    color: "text-teal-600 bg-teal-50",
  },
];

export default function IntelligencePage() {
  const { register } = useCopilot();

  useEffect(() => {
    register({ page: "intelligence", data: {} });
  }, [register]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Intelligence</h1>
      <p className="text-sm text-gray-500 mb-6">
        AI-powered insights from your customer conversations.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sections.map((section) => (
          <Link key={section.label} href={section.href}>
            <Card className="cursor-pointer hover:shadow-md transition-all duration-200">
              <CardContent className="py-6">
                <div className="flex items-start gap-4">
                  <div
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${section.color}`}
                  >
                    <section.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">
                      {section.label}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500">
                      {section.description}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
