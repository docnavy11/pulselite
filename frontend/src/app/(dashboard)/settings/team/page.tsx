"use client";

import { useState, useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { Trash2 } from "lucide-react";
import { getInvites, createInvite, deleteInvite } from "@/lib/api-functions";
import { Invite } from "@/lib/types";

export default function TeamPage() {
  const workspace = useWorkspaceStore((s) => s.currentWorkspace);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!workspace) return;
    getInvites(workspace.id)
      .then((data) => setInvites(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [workspace]);

  async function handleInvite() {
    if (!workspace || !email) return;
    setSending(true);
    try {
      const invite = await createInvite(workspace.id, email, role);
      setInvites((prev) => [invite, ...prev]);
      setEmail("");
    } catch {
      // handle error
    } finally {
      setSending(false);
    }
  }

  async function handleRevoke(inviteId: string) {
    if (!workspace) return;
    await deleteInvite(workspace.id, inviteId);
    setInvites((prev) => prev.filter((i) => i.id !== inviteId));
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-8 w-8 text-primary-600" /></div>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Team</h1>

      <Card className="mb-6">
        <CardContent className="py-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Invite a team member</h2>
          <div className="flex gap-2">
            <Input
              placeholder="colleague@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleInvite()}
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 text-sm text-gray-700 focus:ring-2 focus:ring-primary-500 focus:outline-none"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <Button onClick={handleInvite} loading={sending} disabled={!email}>
              Send Invite
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-2">
        {invites.map((invite) => (
          <Card key={invite.id}>
            <CardContent className="py-3 flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-900">{invite.email}</span>
                <div className="flex gap-2 mt-1">
                  <Badge variant="default">{invite.role}</Badge>
                  {invite.accepted_at ? (
                    <Badge variant="success">Accepted</Badge>
                  ) : (
                    <Badge variant="warning">Pending</Badge>
                  )}
                </div>
              </div>
              {!invite.accepted_at && (
                <button
                  onClick={() => handleRevoke(invite.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-all duration-200"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </CardContent>
          </Card>
        ))}
        {invites.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">No invites sent yet.</p>
        )}
      </div>
    </div>
  );
}
