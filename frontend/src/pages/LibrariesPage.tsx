import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, LibraryBig, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Button, Card, Input, Label } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { HouseholdSummary } from "@/lib/types";

const roleLabel: Record<string, string> = {
  owner: "Owner",
  member: "Member",
  viewer: "Read-only",
};

export function LibrariesPage() {
  const { me, household, setHouseholdId, refresh } = useAuth();
  const toast = useToast();
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: () => api.post<{ id: number; name: string }>("/api/households", { name: name.trim() }),
    onSuccess: async (created) => {
      await refresh();
      setHouseholdId(created.id);
      setName("");
      toast.push(`Created "${created.name}"`, "success");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });

  const households = me?.households ?? [];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center gap-2">
        <LibraryBig className="h-6 w-6" />
        <h1 className="text-2xl font-semibold">Libraries</h1>
      </div>
      <p className="text-sm text-muted-foreground">
        Every library you can access. Switch the active one, or create a new one.
      </p>

      <div className="space-y-2">
        {households.map((h: HouseholdSummary) => {
          const current = h.id === household?.id;
          return (
            <Card
              key={h.id}
              className={cn("flex items-center justify-between p-3", current && "border-primary")}
            >
              <div>
                <p className="font-medium">{h.name}</p>
                <p className="text-xs text-muted-foreground">{roleLabel[h.role] ?? h.role}</p>
              </div>
              {current ? (
                <span className="flex items-center gap-1 text-sm text-primary">
                  <Check className="h-4 w-4" /> Active
                </span>
              ) : (
                <Button variant="outline" size="sm" onClick={() => setHouseholdId(h.id)}>
                  Switch
                </Button>
              )}
            </Card>
          );
        })}
      </div>

      <Card className="p-4">
        <Label>Create a new library</Label>
        <div className="flex gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && name.trim() && create.mutate()}
            placeholder="e.g. Office, Holiday home, Comics..."
          />
          <Button onClick={() => name.trim() && create.mutate()} loading={create.isPending}>
            <Plus className="h-4 w-4" /> Create
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          You become the owner and can invite others from Settings.
        </p>
      </Card>
    </div>
  );
}
