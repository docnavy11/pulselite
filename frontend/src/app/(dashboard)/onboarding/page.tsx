"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronRight, SkipForward } from "lucide-react";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { OnboardingState } from "@/lib/types";
import {
  getOnboardingState,
  updateOnboardingStep,
  completeOnboarding,
} from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

const stepLabels = [
  "Workspace Setup",
  "Create Chatbot",
  "Add Knowledge",
  "LLM Config",
  "Customize Widget",
  "Install Widget",
];

export default function OnboardingPage() {
  const router = useRouter();
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [, setState] = useState<OnboardingState | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Step form states
  const [workspaceName, setWorkspaceName] = useState("");
  const [chatbotName, setChatbotName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [confidenceThreshold, setConfidenceThreshold] = useState(70);

  useEffect(() => {
    if (!workspace) {
      setLoading(false);
      return;
    }
    getOnboardingState(workspace.id)
      .then((s) => {
        setState(s);
        setCurrentStep(s.current_step);
        setWorkspaceName(workspace.name);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  async function handleNext(data: Record<string, unknown> = {}) {
    if (!workspace) return;
    setSaving(true);
    try {
      const updated = await updateOnboardingStep(
        workspace.id,
        currentStep,
        data,
      );
      setState(updated);
      if (currentStep < 5) {
        setCurrentStep(currentStep + 1);
      }
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    if (!workspace) return;
    setSaving(true);
    try {
      await completeOnboarding(workspace.id);
      router.push("/dashboard");
    } catch {
      // handle error
    } finally {
      setSaving(false);
    }
  }

  function handleSkip() {
    if (currentStep < 5) {
      setCurrentStep(currentStep + 1);
    }
  }

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-8rem)] items-center justify-center">
        <Spinner className="h-8 w-8 text-primary-600" />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-8rem)] px-4">
      {/* Progress */}
      <div className="w-full max-w-2xl mb-8">
        <div className="flex items-center justify-between mb-2">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex items-center">
              <div
                className={clsx(
                  "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-all duration-200",
                  i < currentStep
                    ? "bg-primary-600 text-white"
                    : i === currentStep
                      ? "bg-primary-100 text-primary-700 ring-2 ring-primary-600"
                      : "bg-gray-100 text-gray-400",
                )}
              >
                {i < currentStep ? (
                  <Check className="h-4 w-4" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 5 && (
                <div
                  className={clsx(
                    "h-0.5 w-8 sm:w-12 mx-1",
                    i < currentStep ? "bg-primary-600" : "bg-gray-200",
                  )}
                />
              )}
            </div>
          ))}
        </div>
        <p className="text-center text-sm text-gray-500">
          Step {currentStep + 1} of 6: {stepLabels[currentStep]}
        </p>
      </div>

      <Card className="w-full max-w-lg">
        <CardContent className="pt-8 pb-8">
          {currentStep === 0 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                Set up your workspace
              </h2>
              <Input
                label="Workspace Name"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="My Company"
              />
              <Input label="Timezone" defaultValue="UTC" />
              <Button
                className="w-full"
                onClick={() =>
                  handleNext({ name: workspaceName })
                }
                loading={saving}
              >
                Continue
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {currentStep === 1 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                Create your first chatbot
              </h2>
              <Input
                label="Chatbot Name"
                value={chatbotName}
                onChange={(e) => setChatbotName(e.target.value)}
                placeholder="Support Bot"
              />
              <Button
                className="w-full"
                onClick={() =>
                  handleNext({ chatbot_name: chatbotName })
                }
                loading={saving}
              >
                Continue
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                Add knowledge sources
              </h2>
              <p className="text-sm text-gray-500 text-center">
                Add a URL to your docs or help center
              </p>
              <Input
                label="Documentation URL"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://docs.yoursite.com"
              />
              <Button
                className="w-full"
                onClick={() =>
                  handleNext({ source_url: sourceUrl })
                }
                loading={saving}
              >
                Continue
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {currentStep === 3 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                Configure AI settings
              </h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Confidence Threshold: {confidenceThreshold}%
                </label>
                <input
                  type="range"
                  min={30}
                  max={95}
                  value={confidenceThreshold}
                  onChange={(e) =>
                    setConfidenceThreshold(Number(e.target.value))
                  }
                  className="w-full accent-primary-600"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Below this threshold, conversations will be escalated to a
                  human
                </p>
              </div>
              <Button
                className="w-full"
                onClick={() =>
                  handleNext({
                    confidence_threshold: confidenceThreshold / 100,
                  })
                }
                loading={saving}
              >
                Continue
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                Customize your widget
              </h2>
              <p className="text-sm text-gray-500 text-center">
                You can customize your widget in detail later from the chatbot
                settings.
              </p>
              <Button
                className="w-full"
                onClick={() => handleNext({})}
                loading={saving}
              >
                Continue
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}

          {currentStep === 5 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-gray-900 text-center">
                You&apos;re all set!
              </h2>
              <p className="text-sm text-gray-500 text-center">
                Your chatbot is ready. Install the widget on your website or
                share the link with customers.
              </p>
              <Button
                className="w-full"
                onClick={handleComplete}
                loading={saving}
              >
                Go to Dashboard
              </Button>
            </div>
          )}

          {currentStep < 5 && (
            <button
              onClick={handleSkip}
              className="flex items-center justify-center gap-1 w-full mt-3 text-sm text-gray-400 hover:text-gray-600 transition-all duration-200"
            >
              <SkipForward className="h-3.5 w-3.5" />
              Skip this step
            </button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
