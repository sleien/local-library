import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  HandHelping,
  Images,
  MapPin,
  Plus,
  Trash2,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";
import {
  Badge,
  Button,
  Card,
  Input,
  Label,
  PageSpinner,
  Select,
  StarRating,
  Textarea,
} from "@/components/ui";
import { formatDate } from "@/lib/utils";
import type { BookDetail, CopyOut, Loan, LocationNode, Person, UserSelect } from "@/lib/types";

function flatten(nodes: LocationNode[], depth = 0): { id: number; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"  ".repeat(depth)}${n.name}` },
    ...flatten(n.children, depth + 1),
  ]);
}

export function BookDetailPage() {
  const { id } = useParams();
  const { household } = useAuth();
  const hid = household?.id;
  const canWrite = household?.role !== "viewer";
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const bookKey = ["book", hid, id];
  const { data: book, isLoading } = useQuery({
    queryKey: bookKey,
    queryFn: () => api.get<BookDetail>(`/api/households/${hid}/books/${id}`),
    enabled: !!hid && !!id,
  });
  const { data: people } = useQuery({
    queryKey: ["people", hid],
    queryFn: () => api.get<Person[]>(`/api/households/${hid}/people`),
    enabled: !!hid,
  });
  const { data: allUsers } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserSelect[]>("/api/users"),
    enabled: !!hid,
  });
  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });
  const { data: activeLoans } = useQuery({
    queryKey: ["loans", hid, "active"],
    queryFn: () => api.get<Loan[]>(`/api/households/${hid}/loans?active=true`),
    enabled: !!hid,
  });

  const loanByCopy = useMemo(() => {
    const map = new Map<number, Loan>();
    activeLoans?.forEach((l) => map.set(l.copy_id, l));
    return map;
  }, [activeLoans]);
  const locationOptions = useMemo(() => (locations ? flatten(locations) : []), [locations]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: bookKey });
    qc.invalidateQueries({ queryKey: ["loans", hid] });
    qc.invalidateQueries({ queryKey: ["search"] });
  };
  const onError = (e: unknown) =>
    toast.push(e instanceof ApiError ? e.message : "Something went wrong", "error");

  // --- mutations ---
  const tagAdd = useMutation({
    mutationFn: (name: string) => api.post(`/api/households/${hid}/books/${id}/tags`, { name }),
    onSuccess: refresh,
    onError,
  });
  const tagRemove = useMutation({
    mutationFn: (tagId: number) => api.del(`/api/households/${hid}/books/${id}/tags/${tagId}`),
    onSuccess: refresh,
    onError,
  });
  const deleteBook = useMutation({
    mutationFn: () => api.del(`/api/households/${hid}/books/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["search"] });
      navigate("/");
    },
    onError,
  });
  const deleteCopy = useMutation({
    mutationFn: (copyId: number) => api.del(`/api/households/${hid}/copies/${copyId}`),
    onSuccess: refresh,
    onError,
  });
  const moveCopy = useMutation({
    mutationFn: ({ copyId, locationId }: { copyId: number; locationId: number | null }) =>
      api.patch(`/api/households/${hid}/copies/${copyId}`, { location_id: locationId }),
    onSuccess: refresh,
    onError,
  });
  const returnLoan = useMutation({
    mutationFn: (loanId: number) => api.post(`/api/households/${hid}/loans/${loanId}/return`, {}),
    onSuccess: () => {
      refresh();
      toast.push("Returned", "success");
    },
    onError,
  });
  const selectCover = useMutation({
    mutationFn: (coverId: number) =>
      api.post(`/api/households/${hid}/books/${id}/select-cover/${coverId}`),
    onSuccess: () => {
      refresh();
      setCoverOpen(false);
    },
    onError,
  });
  const coverFileRef = useRef<HTMLInputElement>(null);
  const uploadCover = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api.upload(`/api/households/${hid}/books/${id}/cover`, form);
    },
    onSuccess: () => {
      refresh();
      setCoverOpen(false);
      toast.push("Cover updated", "success");
    },
    onError,
  });
  const onPickCover = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) uploadCover.mutate(f);
    e.target.value = ""; // let the same file be re-selected later
  };

  // --- local modal state ---
  const [tagInput, setTagInput] = useState("");
  const [statusOpen, setStatusOpen] = useState(false);
  const [status, setStatus] = useState("want");
  const [rating, setRating] = useState<number | null>(null);
  const [review, setReview] = useState("");
  const [startedAt, setStartedAt] = useState("");
  const [finishedAt, setFinishedAt] = useState("");
  const [lendCopy, setLendCopy] = useState<CopyOut | null>(null);
  const [lendTarget, setLendTarget] = useState(""); // "person:<id>" or "user:<id>"
  const [lendDue, setLendDue] = useState("");
  const [addCopyOpen, setAddCopyOpen] = useState(false);
  const [newCopyLocation, setNewCopyLocation] = useState("");
  const [newCopyCondition, setNewCopyCondition] = useState("");
  const [coverOpen, setCoverOpen] = useState(false);
  const [comment, setComment] = useState("");

  const saveStatus = useMutation({
    mutationFn: () =>
      api.put(`/api/households/${hid}/books/${id}/status`, {
        status,
        rating,
        review: review || null,
        started_at: startedAt || null,
        finished_at: finishedAt || null,
      }),
    onSuccess: () => {
      refresh();
      setStatusOpen(false);
    },
    onError,
  });
  const lend = useMutation({
    mutationFn: () => {
      const [kind, idStr] = lendTarget.split(":");
      const body: Record<string, unknown> = {
        copy_id: lendCopy!.id,
        due_date: lendDue ? new Date(lendDue).toISOString() : null,
      };
      if (kind === "user") body.user_id = Number(idStr);
      else body.person_id = Number(idStr);
      return api.post(`/api/households/${hid}/loans`, body);
    },
    onSuccess: () => {
      refresh();
      setLendCopy(null);
      setLendTarget("");
      setLendDue("");
      toast.push("Lent out", "success");
    },
    onError,
  });
  const addCopy = useMutation({
    mutationFn: () =>
      api.post(`/api/households/${hid}/books/${id}/copies`, {
        location_id: newCopyLocation ? Number(newCopyLocation) : null,
        condition: newCopyCondition || null,
      }),
    onSuccess: () => {
      refresh();
      setAddCopyOpen(false);
      setNewCopyLocation("");
      setNewCopyCondition("");
    },
    onError,
  });
  const addComment = useMutation({
    mutationFn: () => api.post(`/api/households/${hid}/books/${id}/comments`, { body: comment }),
    onSuccess: () => {
      refresh();
      setComment("");
    },
    onError,
  });
  const deleteComment = useMutation({
    mutationFn: (commentId: number) =>
      api.del(`/api/households/${hid}/books/${id}/comments/${commentId}`),
    onSuccess: refresh,
    onError,
  });

  if (isLoading || !book) return <PageSpinner />;

  const openStatus = () => {
    setStatus(book.my_book?.status ?? "want");
    setRating(book.my_book?.rating ?? null);
    setReview(book.my_book?.review ?? "");
    setStartedAt(book.my_book?.started_at ?? "");
    setFinishedAt(book.my_book?.finished_at ?? "");
    setStatusOpen(true);
  };

  return (
    <div className="space-y-5">
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>

      <div className="flex flex-col gap-5 sm:flex-row">
        <div className="mx-auto w-40 shrink-0 sm:mx-0">
          <div className="relative aspect-[2/3] overflow-hidden rounded-lg border bg-muted">
            {book.cover_url ? (
              <img src={book.cover_url} alt={book.title} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                <BookOpen className="h-10 w-10" />
              </div>
            )}
          </div>
          {canWrite && (
            <div className="mt-2 space-y-2">
              {book.covers.length > 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setCoverOpen(true)}
                >
                  <Images className="h-3.5 w-3.5" /> Change cover
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => coverFileRef.current?.click()}
                loading={uploadCover.isPending}
              >
                <Upload className="h-3.5 w-3.5" /> Upload cover
              </Button>
              <input
                ref={coverFileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={onPickCover}
              />
            </div>
          )}
        </div>

        <div className="flex-1 space-y-3">
          <div>
            <h1 className="text-2xl font-semibold leading-tight">{book.title}</h1>
            {book.subtitle && <p className="text-muted-foreground">{book.subtitle}</p>}
            {book.authors.length > 0 && <p className="mt-1">{book.authors.join(", ")}</p>}
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {book.publisher && <span>{book.publisher}</span>}
            {book.published_date && <span>{book.published_date}</span>}
            {book.page_count && <span>{book.page_count} pages</span>}
            {book.isbn13 && <span>ISBN {book.isbn13}</span>}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={openStatus}>
              {book.my_book ? (
                <>
                  <span className="capitalize">{book.my_book.status}</span>
                  {book.my_book.rating ? ` · ${book.my_book.rating}★` : ""}
                </>
              ) : (
                "Set reading status"
              )}
            </Button>
            {canWrite && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  confirm("Delete this book and all its copies?") && deleteBook.mutate()
                }
              >
                <Trash2 className="h-3.5 w-3.5 text-destructive" /> Delete
              </Button>
            )}
          </div>

          {book.description && (
            <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {book.description}
            </p>
          )}

          {/* Tags */}
          <div>
            <div className="flex flex-wrap items-center gap-1.5">
              {book.tags.map((t) => (
                <Badge key={t.id} color={t.color}>
                  {t.name}
                  {canWrite && (
                    <button
                      className="ml-1"
                      onClick={() => tagRemove.mutate(t.id)}
                      aria-label="Remove tag"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </Badge>
              ))}
            </div>
            {canWrite && (
              <div className="mt-2 flex max-w-xs gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && tagInput.trim()) {
                      tagAdd.mutate(tagInput.trim());
                      setTagInput("");
                    }
                  }}
                  placeholder="Add tag"
                  className="h-8"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Copies */}
      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Copies ({book.copies.length})</h2>
          {canWrite && (
            <Button size="sm" variant="outline" onClick={() => setAddCopyOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> Add copy
            </Button>
          )}
        </div>
        <div className="space-y-2">
          {book.copies.map((copy) => {
            const loan = loanByCopy.get(copy.id);
            return (
              <Card key={copy.id} className="p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    {canWrite ? (
                      <Select
                        value={copy.location_id ?? ""}
                        onChange={(e) =>
                          moveCopy.mutate({
                            copyId: copy.id,
                            locationId: e.target.value ? Number(e.target.value) : null,
                          })
                        }
                        className="h-8 w-auto min-w-[12rem]"
                      >
                        <option value="">Unassigned</option>
                        {locationOptions.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.label}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <span>{copy.location_path ?? "Unassigned"}</span>
                    )}
                    {copy.condition && (
                      <span className="text-xs text-muted-foreground">({copy.condition})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {copy.is_borrowed && (
                      <span className="text-xs text-muted-foreground">With {copy.borrowed_by}</span>
                    )}
                    {canWrite &&
                      (copy.is_borrowed ? (
                        loan && (
                          <Button size="sm" variant="outline" onClick={() => returnLoan.mutate(loan.id)}>
                            <Undo2 className="h-3.5 w-3.5" /> Return
                          </Button>
                        )
                      ) : (
                        <Button size="sm" variant="subtle" onClick={() => setLendCopy(copy)}>
                          <HandHelping className="h-3.5 w-3.5" /> Lend
                        </Button>
                      ))}
                    {canWrite && (
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label="Delete copy"
                        onClick={() => confirm("Delete this copy?") && deleteCopy.mutate(copy.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Comments */}
      <section>
        <h2 className="mb-2 font-semibold">Comments</h2>
        <div className="space-y-2">
          {book.comments.map((c) => (
            <Card key={c.id} className="p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{c.user_name}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{formatDate(c.created_at)}</span>
                  {canWrite && (
                    <button
                      onClick={() => deleteComment.mutate(c.id)}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Delete comment"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
              <p className="mt-1 whitespace-pre-line text-sm">{c.body}</p>
            </Card>
          ))}
        </div>
        {canWrite && (
          <div className="mt-2 flex gap-2">
            <Input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && comment.trim() && addComment.mutate()}
              placeholder="Write a comment..."
            />
            <Button
              onClick={() => comment.trim() && addComment.mutate()}
              loading={addComment.isPending}
            >
              Post
            </Button>
          </div>
        )}
      </section>

      {/* Reading status modal */}
      <Modal
        open={statusOpen}
        onClose={() => setStatusOpen(false)}
        title="Reading status"
        footer={
          <>
            <Button variant="ghost" onClick={() => setStatusOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => saveStatus.mutate()} loading={saveStatus.isPending}>
              Save
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label>Status</Label>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="want">Want to read</option>
              <option value="reading">Reading</option>
              <option value="read">Read</option>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Started</Label>
              <Input type="date" value={startedAt} onChange={(e) => setStartedAt(e.target.value)} />
            </div>
            <div>
              <Label>Finished</Label>
              <Input
                type="date"
                value={finishedAt}
                onChange={(e) => setFinishedAt(e.target.value)}
              />
            </div>
          </div>
          <div>
            <Label>Your rating</Label>
            <StarRating value={rating} onChange={setRating} />
          </div>
          <div>
            <Label>Review</Label>
            <Textarea value={review} onChange={(e) => setReview(e.target.value)} />
          </div>
        </div>
      </Modal>

      {/* Lend modal */}
      <Modal
        open={!!lendCopy}
        onClose={() => setLendCopy(null)}
        title="Lend this copy"
        footer={
          <>
            <Button variant="ghost" onClick={() => setLendCopy(null)}>
              Cancel
            </Button>
            <Button onClick={() => lend.mutate()} loading={lend.isPending} disabled={!lendTarget}>
              Lend
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label>To</Label>
            <Select value={lendTarget} onChange={(e) => setLendTarget(e.target.value)}>
              <option value="">Select a person or user</option>
              {people && people.length > 0 && (
                <optgroup label="People">
                  {people.map((p) => (
                    <option key={`p${p.id}`} value={`person:${p.id}`}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {allUsers && allUsers.length > 0 && (
                <optgroup label="Users">
                  {allUsers.map((u) => (
                    <option key={`u${u.id}`} value={`user:${u.id}`}>
                      {u.display_name} ({u.email})
                    </option>
                  ))}
                </optgroup>
              )}
            </Select>
          </div>
          <div>
            <Label>Due date (optional)</Label>
            <Input type="date" value={lendDue} onChange={(e) => setLendDue(e.target.value)} />
          </div>
        </div>
      </Modal>

      {/* Add copy modal */}
      <Modal
        open={addCopyOpen}
        onClose={() => setAddCopyOpen(false)}
        title="Add a copy"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddCopyOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => addCopy.mutate()} loading={addCopy.isPending}>
              Add
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label>Location</Label>
            <Select value={newCopyLocation} onChange={(e) => setNewCopyLocation(e.target.value)}>
              <option value="">Unassigned</option>
              {locationOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Condition (optional)</Label>
            <Input
              value={newCopyCondition}
              onChange={(e) => setNewCopyCondition(e.target.value)}
              placeholder="e.g. good, signed, worn"
            />
          </div>
        </div>
      </Modal>

      {/* Cover picker modal */}
      <Modal open={coverOpen} onClose={() => setCoverOpen(false)} title="Choose a cover" wide>
        <div className="mb-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => coverFileRef.current?.click()}
            loading={uploadCover.isPending}
          >
            <Upload className="h-3.5 w-3.5" /> Upload your own
          </Button>
        </div>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
          {book.covers.map((c) => (
            <button
              key={c.id}
              onClick={() => selectCover.mutate(c.id)}
              className={`overflow-hidden rounded-md border-2 ${
                c.selected ? "border-primary" : "border-transparent hover:border-border"
              }`}
            >
              {c.url ? (
                <img
                  src={c.url}
                  alt=""
                  className="aspect-[2/3] w-full object-cover"
                  onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                />
              ) : (
                <div className="flex aspect-[2/3] items-center justify-center bg-muted">
                  <BookOpen className="h-6 w-6 text-muted-foreground" />
                </div>
              )}
            </button>
          ))}
        </div>
      </Modal>
    </div>
  );
}
