import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Mail, Phone, UserPlus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";
import { Button, Card, EmptyState, Input, Label, PageSpinner, Textarea } from "@/components/ui";
import type { Person } from "@/lib/types";

interface Draft {
  name: string;
  email: string;
  phone: string;
  notes: string;
}

const empty: Draft = { name: "", email: "", phone: "", notes: "" };

export function PeoplePage() {
  const { household } = useAuth();
  const hid = household?.id;
  const canWrite = household?.role !== "viewer";
  const qc = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Draft | null>(null);

  const { data: people, isLoading } = useQuery({
    queryKey: ["people", hid],
    queryFn: () => api.get<Person[]>(`/api/households/${hid}/people`),
    enabled: !!hid,
  });

  const createMut = useMutation({
    mutationFn: (d: Draft) =>
      api.post(`/api/households/${hid}/people`, {
        name: d.name,
        email: d.email || null,
        phone: d.phone || null,
        notes: d.notes || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["people", hid] });
      setDraft(null);
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">People</h1>
        {canWrite && (
          <Button onClick={() => setDraft({ ...empty })}>
            <UserPlus className="h-4 w-4" /> Add person
          </Button>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !people || people.length === 0 ? (
        <EmptyState title="No people yet" hint="Add the people you lend books to." />
      ) : (
        <div className="space-y-2">
          {people.map((p) => (
            <Link key={p.id} to={`/people/${p.id}`}>
              <Card className="flex items-center justify-between p-3 transition-colors hover:bg-accent">
                <div className="min-w-0">
                  <p className="font-medium">{p.name}</p>
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    {p.email && (
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3" />
                        {p.email}
                      </span>
                    )}
                    {p.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="h-3 w-3" />
                        {p.phone}
                      </span>
                    )}
                  </div>
                </div>
                {p.active_loan_count > 0 && (
                  <span className="rounded-full bg-primary/15 px-2.5 py-0.5 text-xs font-medium text-primary">
                    {p.active_loan_count} out
                  </span>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}

      <Modal
        open={!!draft}
        onClose={() => setDraft(null)}
        title="Add person"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => draft && createMut.mutate(draft)}
              loading={createMut.isPending}
              disabled={!draft?.name}
            >
              Save
            </Button>
          </>
        }
      >
        {draft && (
          <div className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input
                autoFocus
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </div>
            <div>
              <Label>Email (optional)</Label>
              <Input
                type="email"
                value={draft.email}
                onChange={(e) => setDraft({ ...draft, email: e.target.value })}
              />
            </div>
            <div>
              <Label>Phone (optional)</Label>
              <Input
                value={draft.phone}
                onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
              />
            </div>
            <div>
              <Label>Notes (optional)</Label>
              <Textarea
                value={draft.notes}
                onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
