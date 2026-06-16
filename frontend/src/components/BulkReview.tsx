import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";
import { Button, Label, Select, Spinner } from "@/components/ui";
import { COPY_CONDITIONS } from "@/lib/utils";
import type { BookDetail } from "@/lib/types";

export interface ReviewItem {
  bookId: number;
  copyId: number;
  title: string | null;
}

/**
 * Step through the copies just added in bulk and set each one's cover,
 * condition, and location. Location starts from whatever the bulk add gave the
 * copy (the chosen destination), so you only change the few that go elsewhere.
 * Every change saves immediately via the existing per-book/per-copy endpoints.
 */
export function BulkReview({
  householdId,
  items,
  locationOptions,
  open,
  onClose,
}: {
  householdId: number;
  items: ReviewItem[];
  locationOptions: { id: number; label: string }[];
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [index, setIndex] = useState(0);

  // Restart at the first book whenever a new batch opens.
  useEffect(() => {
    if (open) setIndex(0);
  }, [open]);

  const item = items[index];
  const onError = (e: unknown) =>
    toast.push(e instanceof ApiError ? e.message : "Something went wrong", "error");

  const bookKey = ["book", householdId, String(item?.bookId)];
  const { data: book, isLoading } = useQuery({
    queryKey: bookKey,
    queryFn: () => api.get<BookDetail>(`/api/households/${householdId}/books/${item.bookId}`),
    enabled: open && !!item,
  });
  const copy = book?.copies.find((c) => c.id === item?.copyId);

  const selectCover = useMutation({
    mutationFn: (coverId: number) =>
      api.post<BookDetail>(
        `/api/households/${householdId}/books/${item.bookId}/select-cover/${coverId}`,
      ),
    onSuccess: (d) => qc.setQueryData(bookKey, d),
    onError,
  });
  const refreshCovers = useMutation({
    mutationFn: () =>
      api.post<BookDetail>(`/api/households/${householdId}/books/${item.bookId}/refresh-covers`),
    onSuccess: (d) => qc.setQueryData(bookKey, d),
    onError,
  });
  const patchCopy = useMutation({
    mutationFn: (body: { condition?: string | null; location_id?: number | null }) =>
      api.patch(`/api/households/${householdId}/copies/${item.copyId}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: bookKey }),
    onError,
  });

  if (!open || !item) return null;
  const isLast = index === items.length - 1;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Set up added books · ${index + 1} of ${items.length}`}
      wide
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            disabled={index === 0}
          >
            <ChevronLeft className="h-4 w-4" /> Back
          </Button>
          {isLast ? (
            <Button onClick={onClose}>Done</Button>
          ) : (
            <Button onClick={() => setIndex((i) => Math.min(items.length - 1, i + 1))}>
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          )}
        </>
      }
    >
      {isLoading || !book ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold leading-tight">{book.title}</h3>
            {book.authors.length > 0 && (
              <p className="text-sm text-muted-foreground">{book.authors.join(", ")}</p>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <Label className="mb-0">Cover</Label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refreshCovers.mutate()}
                loading={refreshCovers.isPending}
              >
                <RefreshCw className="h-3.5 w-3.5" /> Find covers online
              </Button>
            </div>
            {book.covers.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No covers found. Try “Find covers online”.
              </p>
            ) : (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {book.covers.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => selectCover.mutate(c.id)}
                    className={`h-28 w-20 shrink-0 overflow-hidden rounded-md border-2 ${
                      c.selected ? "border-primary" : "border-transparent hover:border-border"
                    }`}
                  >
                    {c.url ? (
                      <img
                        src={c.url}
                        alt=""
                        className="h-full w-full object-cover"
                        onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center bg-muted">
                        <BookOpen className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <Label>Condition</Label>
              <Select
                value={copy?.condition ?? ""}
                onChange={(e) => patchCopy.mutate({ condition: e.target.value || null })}
              >
                <option value="">Not set</option>
                {COPY_CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Location</Label>
              <Select
                value={copy?.location_id ?? ""}
                onChange={(e) =>
                  patchCopy.mutate({ location_id: e.target.value ? Number(e.target.value) : null })
                }
              >
                <option value="">Unassigned</option>
                {locationOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
