import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Copy,
  KeyRound,
  LogOut,
  Moon,
  PlayCircle,
  Share2,
  Sun,
  Trash2,
  UserPlus,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useTheme } from "@/theme/ThemeProvider";
import { useToast } from "@/components/Toast";
import { startTour } from "@/onboarding/tour";
import { Button, Card, Input, Label, Select } from "@/components/ui";
import type { ApiToken, Invite, Member, Share, TokenCreated } from "@/lib/types";

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

  // --- Sharing (read-only friends) ---
  const [shareEmail, setShareEmail] = useState("");
  const { data: shares } = useQuery({
    queryKey: ["shares", hid],
    queryFn: () => api.get<Share[]>(`/api/households/${hid}/shares`),
    enabled: !!hid && isOwner,
  });
  const createShare = useMutation({
    mutationFn: () => api.post<Share>(`/api/households/${hid}/shares`, { email: shareEmail }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shares", hid] });
      setShareEmail("");
      toast.push("Shared (read-only)", "success");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });
  const revokeShare = useMutation({
    mutationFn: (shareId: number) => api.del(`/api/households/${hid}/shares/${shareId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shares", hid] }),
  });

  // --- Personal API tokens ---
  const [tokenName, setTokenName] = useState("");
  const [newToken, setNewToken] = useState<TokenCreated | null>(null);
  const { data: tokens } = useQuery({
    queryKey: ["tokens"],
    queryFn: () => api.get<ApiToken[]>("/api/tokens"),
  });
  const createToken = useMutation({
    mutationFn: () => api.post<TokenCreated>("/api/tokens", { name: tokenName }),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["tokens"] });
      setNewToken(t);
      setTokenName("");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });
  const revokeToken = useMutation({
    mutationFn: (tokenId: number) => api.del(`/api/tokens/${tokenId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tokens"] }),
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
        <h2 className="mb-3 font-semibold">Appearance & help</h2>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={toggle}>
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === "dark" ? "Switch to light" : "Switch to dark"}
          </Button>
          <Button variant="outline" onClick={() => startTour()}>
            <PlayCircle className="h-4 w-4" /> Replay tour
          </Button>
        </div>
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

      {isOwner && (
        <Card className="p-4">
          <h2 className="mb-1 flex items-center gap-2 font-semibold">
            <Share2 className="h-4 w-4" /> Read-only sharing
          </h2>
          <p className="mb-3 text-sm text-muted-foreground">
            Let a friend browse this library without changing anything. They need a Bibliothek
            account first.
          </p>
          <div className="flex gap-2">
            <Input
              type="email"
              value={shareEmail}
              onChange={(e) => setShareEmail(e.target.value)}
              placeholder="friend@example.com"
            />
            <Button
              onClick={() => shareEmail && createShare.mutate()}
              loading={createShare.isPending}
            >
              Share
            </Button>
          </div>
          {shares && shares.length > 0 && (
            <div className="mt-3 space-y-2">
              {shares.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{s.viewer_name}</p>
                    <p className="text-xs text-muted-foreground">{s.viewer_email}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Revoke share"
                    onClick={() => revokeShare.mutate(s.id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card className="p-4">
        <h2 className="mb-1 flex items-center gap-2 font-semibold">
          <KeyRound className="h-4 w-4" /> API access
        </h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Create a personal token to use the REST API. Send it as an{" "}
          <code>Authorization: Bearer &lt;token&gt;</code> header. See the{" "}
          <a href="/api/docs" target="_blank" rel="noreferrer" className="text-primary hover:underline">
            API documentation
          </a>
          .
        </p>
        <div className="flex gap-2">
          <Input
            value={tokenName}
            onChange={(e) => setTokenName(e.target.value)}
            placeholder="Token name (e.g. scripts)"
          />
          <Button onClick={() => tokenName && createToken.mutate()} loading={createToken.isPending}>
            Create
          </Button>
        </div>
        {newToken && (
          <div className="mt-3 rounded-md border border-primary/40 bg-primary/10 p-3">
            <p className="text-sm font-medium">Copy your token now — it will not be shown again.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 truncate text-xs">{newToken.token}</code>
              <Button variant="ghost" size="icon" aria-label="Copy token" onClick={() => copy(newToken.token)}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
        {tokens && tokens.length > 0 && (
          <div className="mt-3 space-y-2">
            {tokens.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between rounded-md border px-3 py-2"
              >
                <div>
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {t.prefix}…
                    {t.last_used_at
                      ? ` · last used ${new Date(t.last_used_at).toLocaleDateString()}`
                      : " · never used"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Revoke token"
                  onClick={() => revokeToken.mutate(t.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

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
