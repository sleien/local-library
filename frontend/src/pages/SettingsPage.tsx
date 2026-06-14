import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, LogOut, Moon, Sun, Trash2, UserPlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useTheme } from "@/theme/ThemeProvider";
import { useToast } from "@/components/Toast";
import { Button, Card, Input, Label, Select } from "@/components/ui";
import type { Invite, Member } from "@/lib/types";

export function SettingsPage() {
  const { me, household, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const toast = useToast();
  const qc = useQueryClient();
  const hid = household?.id;
  const isOwner = household?.role === "owner";
  const [inviteRole, setInviteRole] = useState("member");

  const { data: members } = useQuery({
    queryKey: ["members", hid],
    queryFn: () => api.get<Member[]>(`/api/households/${hid}/members`),
    enabled: !!hid,
  });
  const { data: invites } = useQuery({
    queryKey: ["invites", hid],
    queryFn: () => api.get<Invite[]>(`/api/households/${hid}/invites`),
    enabled: !!hid && isOwner,
  });

  const createInvite = useMutation({
    mutationFn: () =>
      api.post<Invite>(`/api/households/${hid}/invites`, { role: inviteRole }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invites", hid] }),
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });
  const revokeInvite = useMutation({
    mutationFn: (inviteId: number) => api.del(`/api/households/${hid}/invites/${inviteId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invites", hid] }),
  });
  const removeMember = useMutation({
    mutationFn: (userId: number) => api.del(`/api/households/${hid}/members/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members", hid] }),
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });

  const inviteLink = (token: string) => `${window.location.origin}/?invite=${token}`;
  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.push("Copied to clipboard", "success");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card className="p-4">
        <h2 className="mb-3 font-semibold">Appearance</h2>
        <Button variant="outline" onClick={toggle}>
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {theme === "dark" ? "Switch to light" : "Switch to dark"}
        </Button>
      </Card>

      <Card className="p-4">
        <h2 className="mb-1 font-semibold">{household?.name}</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Members share full read and write access to this library.
        </p>
        <div className="space-y-1.5">
          {members?.map((m) => (
            <div key={m.user_id} className="flex items-center justify-between rounded-md border px-3 py-2">
              <div>
                <p className="text-sm font-medium">{m.display_name}</p>
                <p className="text-xs text-muted-foreground">{m.email}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs capitalize text-muted-foreground">{m.role}</span>
                {isOwner && m.user_id !== me?.user.id && (
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Remove member"
                    onClick={() => confirm(`Remove ${m.display_name}?`) && removeMember.mutate(m.user_id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {isOwner && (
        <Card className="p-4">
          <h2 className="mb-1 font-semibold">Invitations</h2>
          <p className="mb-3 text-sm text-muted-foreground">
            Share an invite link so others (like your partner) can join this library.
          </p>
          <div className="flex gap-2">
            <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="max-w-[10rem]">
              <option value="member">Member</option>
              <option value="owner">Owner</option>
            </Select>
            <Button onClick={() => createInvite.mutate()} loading={createInvite.isPending}>
              <UserPlus className="h-4 w-4" /> Create invite
            </Button>
          </div>
          {invites && invites.length > 0 && (
            <div className="mt-3 space-y-2">
              {invites.map((inv) => (
                <div key={inv.id} className="flex items-center gap-2 rounded-md border px-3 py-2">
                  <code className="flex-1 truncate text-xs text-muted-foreground">
                    {inviteLink(inv.token)}
                  </code>
                  <Button variant="ghost" size="icon" aria-label="Copy" onClick={() => copy(inviteLink(inv.token))}>
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Revoke" onClick={() => revokeInvite.mutate(inv.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card className="p-4">
        <h2 className="mb-3 font-semibold">Account</h2>
        <div className="space-y-3">
          <div>
            <Label>Name</Label>
            <Input value={me?.user.display_name ?? ""} disabled />
          </div>
          <div>
            <Label>Email</Label>
            <Input value={me?.user.email ?? ""} disabled />
          </div>
          <Button variant="outline" onClick={() => logout()}>
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>
      </Card>
    </div>
  );
}
