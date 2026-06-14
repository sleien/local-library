import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Button, Card, EmptyState, PageSpinner, StarRating } from "@/components/ui";
import { formatDate } from "@/lib/utils";
import type { Loan, Person } from "@/lib/types";

export function PersonDetailPage() {
  const { id } = useParams();
  const { household } = useAuth();
  const hid = household?.id;
  const canWrite = household?.role !== "viewer";
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: person, isLoading } = useQuery({
    queryKey: ["person", hid, id],
    queryFn: () => api.get<Person>(`/api/households/${hid}/people/${id}`),
    enabled: !!hid && !!id,
  });
  const { data: loans } = useQuery({
    queryKey: ["person-loans", hid, id],
    queryFn: () => api.get<Loan[]>(`/api/households/${hid}/people/${id}/loans`),
    enabled: !!hid && !!id,
  });

  const deleteMut = useMutation({
    mutationFn: () => api.del(`/api/households/${hid}/people/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["people", hid] });
      navigate("/people");
    },
    onError: (e) => toast.push(e instanceof ApiError ? e.message : "Delete failed", "error"),
  });

  if (isLoading || !person) return <PageSpinner />;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate("/people")}>
        <ArrowLeft className="h-4 w-4" /> People
      </Button>

      <Card className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{person.name}</h1>
            <div className="mt-1 space-y-0.5 text-sm text-muted-foreground">
              {person.email && <p>{person.email}</p>}
              {person.phone && <p>{person.phone}</p>}
              {person.notes && <p className="text-foreground">{person.notes}</p>}
            </div>
          </div>
          {canWrite && (
            <Button
              variant="ghost"
              size="icon"
              aria-label="Delete person"
              onClick={() => confirm(`Delete ${person.name}?`) && deleteMut.mutate()}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          )}
        </div>
      </Card>

      <div>
        <h2 className="mb-2 font-semibold">Borrowing history</h2>
        {!loans || loans.length === 0 ? (
          <EmptyState title="Nothing borrowed yet" />
        ) : (
          <div className="space-y-2">
            {loans.map((loan) => (
              <Card key={loan.id} className="p-3">
                <div className="flex items-center justify-between gap-2">
                  <Link to={`/books/${loan.book_id}`} className="font-medium hover:underline">
                    {loan.book_title}
                  </Link>
                  {loan.is_active ? (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        loan.is_overdue
                          ? "bg-destructive/15 text-destructive"
                          : "bg-primary/15 text-primary"
                      }`}
                    >
                      {loan.is_overdue ? "Overdue" : "Out"}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">Returned</span>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatDate(loan.lent_at)}
                  {loan.returned_at ? ` → ${formatDate(loan.returned_at)}` : ""}
                </p>
                {loan.feedback && (loan.feedback.rating || loan.feedback.comment) && (
                  <div className="mt-2 rounded-md bg-muted p-2 text-sm">
                    {loan.feedback.rating && (
                      <StarRating value={loan.feedback.rating} readOnly />
                    )}
                    {loan.feedback.comment && <p className="mt-1">{loan.feedback.comment}</p>}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
