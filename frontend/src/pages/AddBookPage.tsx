import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { BookOpen, Camera, Plus, Search, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { Badge, Button, Card, Input, Label, Select, Spinner } from "@/components/ui";
import type { BookDetail, CopyOut, LocationNode, LookupResult } from "@/lib/types";

function flatten(nodes: LocationNode[], depth = 0): { id: number; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"  ".repeat(depth)}${n.name}` },
    ...flatten(n.children, depth + 1),
  ]);
}

export function AddBookPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const toast = useToast();
  const navigate = useNavigate();

  const [isbn, setIsbn] = useState("");
  const [scanning, setScanning] = useState(false);
  const [looking, setLooking] = useState(false);
  const [result, setResult] = useState<LookupResult | null>(null);
  const [coverIndex, setCoverIndex] = useState(0);
  const [extraTags, setExtraTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [locationId, setLocationId] = useState("");
  const [saving, setSaving] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });
  const locationOptions = useMemo(() => (locations ? flatten(locations) : []), [locations]);

  const doLookup = async (code: string) => {
    const clean = code.trim();
    if (!clean) return;
    setLooking(true);
    setNotFound(false);
    setResult(null);
    try {
      const data = await api.get<LookupResult>(`/api/lookup/isbn/${encodeURIComponent(clean)}`);
      setResult(data);
      setCoverIndex(0);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
      else toast.push(err instanceof ApiError ? err.message : "Lookup failed", "error");
    } finally {
      setLooking(false);
    }
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !extraTags.includes(t)) setExtraTags([...extraTags, t]);
    setTagInput("");
  };

  const save = async () => {
    if (!result || !hid) return;
    setSaving(true);
    try {
      const book = await api.post<BookDetail>(`/api/households/${hid}/books/from-lookup`, {
        isbn: isbn || result.isbn13 || result.isbn10,
        lookup: result,
        selected_cover_index: coverIndex,
        extra_tags: extraTags,
      });
      await api.post<CopyOut>(`/api/households/${hid}/books/${book.id}/copies`, {
        location_id: locationId ? Number(locationId) : null,
      });
      toast.push(`Added "${book.title}"`, "success");
      navigate(`/books/${book.id}`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Could not save", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Add a book</h1>

      <Card className="p-4">
        <Label>Scan a barcode or enter an ISBN</Label>
        <div className="flex gap-2">
          <Input
            value={isbn}
            onChange={(e) => setIsbn(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doLookup(isbn)}
            placeholder="978... (or point a handheld scanner here)"
            inputMode="numeric"
            autoComplete="off"
            autoFocus
          />
          <Button variant="outline" onClick={() => doLookup(isbn)} loading={looking}>
            <Search className="h-4 w-4" /> Look up
          </Button>
          <Button
            variant={scanning ? "default" : "subtle"}
            size="icon"
            onClick={() => setScanning((s) => !s)}
            aria-label="Scan barcode"
          >
            <Camera className="h-4 w-4" />
          </Button>
        </div>

        {scanning && (
          <div className="mt-3">
            <BarcodeScanner
              onDetected={(code) => {
                setIsbn(code);
                setScanning(false);
                doLookup(code);
              }}
            />
          </div>
        )}

        {notFound && (
          <p className="mt-3 text-sm text-muted-foreground">
            No metadata found.{" "}
            <button
              className="font-medium text-primary hover:underline"
              onClick={() => navigate("/add?manual=1")}
            >
              Enter details manually
            </button>{" "}
            (or check the number).
          </p>
        )}
      </Card>

      {looking && (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      )}

      {result && (
        <Card className="space-y-4 p-4">
          <div className="flex gap-4">
            <div className="h-36 w-24 shrink-0 overflow-hidden rounded-md border bg-muted">
              {result.covers[coverIndex] ? (
                <img
                  src={result.covers[coverIndex].url}
                  alt=""
                  className="h-full w-full object-cover"
                  onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <BookOpen className="h-8 w-8" />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold leading-tight">{result.title}</h2>
              {result.subtitle && (
                <p className="text-sm text-muted-foreground">{result.subtitle}</p>
              )}
              <p className="mt-1 text-sm">{result.authors.join(", ")}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {[result.publisher, result.published_date].filter(Boolean).join(" · ")}
              </p>
            </div>
          </div>

          {result.covers.length > 1 && (
            <div>
              <Label>Choose the correct cover</Label>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {result.covers.map((c, i) => (
                  <button
                    key={`${c.url}-${i}`}
                    onClick={() => setCoverIndex(i)}
                    className={`h-28 w-20 shrink-0 overflow-hidden rounded-md border-2 ${
                      i === coverIndex ? "border-primary" : "border-transparent"
                    }`}
                  >
                    <img
                      src={c.url}
                      alt=""
                      className="h-full w-full object-cover"
                      onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                    />
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label>Location (optional)</Label>
            <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Unassigned</option>
              {locationOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label>Tags</Label>
            <div className="flex gap-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                placeholder="Add a custom tag"
              />
              <Button variant="outline" size="icon" onClick={addTag} aria-label="Add tag">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {result.subjects.slice(0, 6).map((s) => (
                <Badge key={s} className="opacity-70">
                  {s}
                </Badge>
              ))}
              {extraTags.map((t) => (
                <Badge key={t} className="bg-primary text-primary-foreground" onClick={() => setExtraTags(extraTags.filter((x) => x !== t))}>
                  {t} <X className="ml-1 h-3 w-3" />
                </Badge>
              ))}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Subjects from the catalog are added automatically as tags.
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setResult(null)}>
              Cancel
            </Button>
            <Button onClick={save} loading={saving}>
              Add to library
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
