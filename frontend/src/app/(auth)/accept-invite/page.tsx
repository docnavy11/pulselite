"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

function AcceptInviteForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const router = useRouter();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAccept() {
    setLoading(true);
    setError("");
    try {
      await api.post("/api/v1/invites/accept", { token, full_name: name, password });
      router.push("/login?accepted=1");
    } catch {
      setError("Invalid or expired invite link.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm space-y-4 p-8 bg-white rounded-xl shadow-sm border border-gray-200">
        <h1 className="text-xl font-bold text-gray-900">Accept Invitation</h1>
        <p className="text-sm text-gray-500">Create your account to join the workspace.</p>
        <Input label="Your name" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <Button onClick={handleAccept} loading={loading} className="w-full" disabled={!name || !password}>
          Join Workspace
        </Button>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return <Suspense><AcceptInviteForm /></Suspense>;
}
