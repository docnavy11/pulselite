import { useState, useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { getDataRetention, updateDataRetention } from "@/lib/api-functions";
import { useWorkspaceStore } from "@/stores/workspace-store";

type RetentionOption = "forever" | "90" | "180" | "365" | "custom";

function daysToOption(days: number | null): RetentionOption {
  if (days === null) return "forever";
  if (days === 90) return "90";
  if (days === 180) return "180";
  if (days === 365) return "365";
  return "custom";
}

export default function DataRetentionPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [selectedOption, setSelectedOption] = useState<RetentionOption>("forever");
  const [customDays, setCustomDays] = useState<number>(30);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    setLoading(true);
    getDataRetention(workspace.id)
      .then((data) => {
        const days = data.data_retention_days;
        const opt = daysToOption(days);
        setSelectedOption(opt);
        if (opt === "custom" && days !== null) {
          setCustomDays(days);
        }
      })
      .catch(() => setError("Failed to load data retention settings."))
      .finally(() => setLoading(false));
  }, [workspace]);

  function getEffectiveDays(): number | null {
    if (selectedOption === "forever") return null;
    if (selectedOption === "90") return 90;
    if (selectedOption === "180") return 180;
    if (selectedOption === "365") return 365;
    return customDays;
  }

  async function handleSave() {
    if (!workspace) return;
    setError(null);
    setSuccess(false);
    setSaving(true);
    const days = getEffectiveDays();
    try {
      await updateDataRetention(workspace.id, days);
      setSuccess(true);
    } catch {
      setError("Failed to save data retention settings. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8 text-primary-500" />
      </div>
    );
  }

  const options: { value: RetentionOption; label: string }[] = [
    { value: "forever", label: "Keep forever" },
    { value: "90", label: "90 days" },
    { value: "180", label: "180 days" },
    { value: "365", label: "1 year (365 days)" },
    { value: "custom", label: "Custom" },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Data Retention</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure how long conversation data is stored. After the retention window,
          conversations and messages are permanently deleted.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            {options.map((opt) => (
              <label key={opt.value} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="retention"
                  value={opt.value}
                  checked={selectedOption === opt.value}
                  onChange={() => setSelectedOption(opt.value)}
                  className="h-4 w-4 text-primary-500 border-gray-300"
                />
                <span className="text-sm font-medium text-gray-700">{opt.label}</span>
                {opt.value === "custom" && selectedOption === "custom" && (
                  <input
                    type="number"
                    min={30}
                    value={customDays}
                    onChange={(e) => setCustomDays(Math.max(30, Number(e.target.value)))}
                    className="ml-2 w-28 border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                    placeholder="Days (min 30)"
                  />
                )}
              </label>
            ))}
          </div>

          <div className="mt-6 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800">
              Deleted data cannot be recovered. This applies to all conversations in this workspace.
            </p>
          </div>

          {error && (
            <p className="mt-4 text-sm text-red-600">{error}</p>
          )}
          {success && (
            <p className="mt-4 text-sm text-green-600">Data retention settings saved successfully.</p>
          )}

          <div className="mt-6">
            <Button onClick={handleSave} loading={saving}>
              Save settings
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
