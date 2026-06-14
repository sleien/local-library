import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { MessageSquare, Undo2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";
import {
  Button,
  Card,
  EmptyState,
  Label,
  PageSpinner,
  StarRating,
  Textarea,
} from "@/components/ui";
import { formatDate } from "@/lib/utils";
import type { Loan } from "@/lib/types";

export function LoansPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const canWrite = household?.role !== "viewer";
  const qc = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [feedbackFor, setFeedbackFor] = useState<Loan | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");

  const query = filter === "active" ? "?active=true" : "";
  const { data: loans, isLoading } = useQuery({
    queryKey: ["loans", hid, filter],
    queryFn: () => api.get<Loan[]>(`/api/households/${hid}/loans${query}`),
    enabled: !!hid,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["loans", hid] });
    qc.invalidateQueries({ queryKey: ["search"] });
  };

  const returnMut = useMutation({
    mutationFn: (loanId: number) =>
      api.post(`/api/households/${hid}/loans/${loanId}/return`, {}),
    onSuccess: () => {
      invalidate();
      toast.push("Marked as returned", "success");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });

  const feedbackMut = useMutation({
    mutationFn: (loanId: number) =>
      api.put(`/api/households/${hid}/loans/${loanId}/feedback`, { rating, comment: comment || null }),
    onSuccess: () => {
      invalidate();
      setFeedbackFor(null);
      toast.push("Feedback saved", "success");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Failed", "error"),
  });

  const openFeedback = (loan: Loan) => {
    setRating(loan.feedback?.rating ?? null);
    setComment(loan.feedback?.comment ?? "");
    setFeedbackFor(loan);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Loans</h1>
        <div className="flex rounded-md border p-0.5 text-sm">
          {(["active", "all"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded px-3 py-1 capitalize ${
                filter === f ? "bg-primary text-primary-foreground" : "text-muted-foreground"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !loans || loans.length === 0 ? (
        <EmptyState
          title={filter === "active" ? "Nothing is on loan" : "No loans yet"}
          hint="Lend a copy from any book's page."
        />
      ) : (
        <div className="space-y-2">
          {loans.map((loan) => (
            <Card key={loan.id} className="p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <Link to={`/books/${loan.book_id}`} className="font-medium hover:underline">
                    {loan.book_title}
                  </Link>
                  <p className="text-sm text-muted-foreground">
                    to{" "}
                    <Link to={`/people/${loan.person_id}`} className="hover:underline">
                      {loan.person_name}
                    </Link>
                  </p>
                </div>
                {loan.is_active && loan.is_overdue && (
                  <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">
                    Overdue
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatDate(loan.lent_at)}
                {loan.returned_at ? ` → ${formatDate(loan.returned_at)} (returned)` : " · on loan"}
                {loan.due_date && !loan.returned_at ? ` · due ${formatDate(loan.due_date)}` : ""}
              </p>
              {canWrite && (
                <div className="mt-2 flex gap-2">
                  {loan.is_active && (
                    <Button size="sm" variant="outline" onClick={() => returnMut.mutate(loan.id)}>
                      <Undo2 className="h-3.5 w-3.5" /> Return
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => openFeedback(loan)}>
                    <MessageSquare className="h-3.5 w-3.5" />
                    {loan.feedback ? "Edit feedback" : "Add feedback"}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={!!feedbackFor}
        onClose={() => setFeedbackFor(null)}
        title="Borrower feedback"
        footer={
          <>
            <Button variant="ghost" onClick={() => setFeedbackFor(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => feedbackFor && feedbackMut.mutate(feedbackFor.id)}
              loading={feedbackMut.isPending}
            >
              Save
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            What did {feedbackFor?.person_name} think of "{feedbackFor?.book_title}"?
          </p>
          <div>
            <Label>Rating</Label>
            <StarRating value={rating} onChange={setRating} />
          </div>
          <div>
            <Label>Comment</Label>
            <Textarea value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
        </div>
      </Modal>
    </div>
  );
}
