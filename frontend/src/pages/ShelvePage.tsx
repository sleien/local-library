import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, MapPin, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { Card, EmptyState, Input, Label } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { ShelfLocate } from "@/lib/types";

interface Result {
  id: number;
  data: ShelfLocate;
}

export function ShelvePage() {
  const { household } = useAuth();
  const hid = household?.id;
  const toast = useToast();
  const [entry, setEntry] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const counter = useRef(0);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const locate = async (raw: string) => {
    const code = raw.trim();
    if (!code || !hid) return;
    try {
      const data = await api.get<ShelfLocate>(
        `/api/households/${hid}/locate?isbn=${encodeURIComponent(code)}`,
      );
      setResults((prev) => [{ id: ++counter.current, data }, ...prev]);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Lookup failed", "error");
    } finally {
      // Clear the field but keep focus so the next scan is ready.
      setEntry("");
      inputRef.current?.focus();
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Put a book away</h1>
        <p className="text-sm text-muted-foreground">
          Scan a book (or type an ISBN) and it shows where it belongs. The field clears after
          each scan so you can go straight to the next one.
        </p>
      </div>

      <Card className="p-4">
        <Label>Scan or type a barcode</Label>
        <Input
          ref={inputRef}
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              locate(entry);
            }
          }}
          placeholder="Point a handheld scanner here, or type an ISBN and press Enter"
          inputMode="numeric"
          autoComplete="off"
          autoFocus
        />
      </Card>

      {results.length === 0 ? (
        <EmptyState title="Nothing scanned yet" hint="Scan a book to see where it goes." />
      ) : (
        <div className="space-y-2">
          {results.map((r, i) => (
            <ResultCard key={r.id} data={r.data} highlight={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}

function ResultCard({ data, highlight }: { data: ShelfLocate; highlight: boolean }) {
  if (!data.found) {
    return (
      <Card className={cn("flex items-center gap-3 p-3", highlight && "border-destructive/50")}>
        <XCircle className="h-5 w-5 shrink-0 text-destructive" />
        <div>
          <p className="text-sm font-medium">Not in this library</p>
          <p className="font-mono text-xs text-muted-foreground">{data.isbn}</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className={cn("flex gap-3 p-3", highlight && "border-primary")}>
      <div className="h-20 w-14 shrink-0 overflow-hidden rounded bg-muted">
        {data.cover_url ? (
          <img
            src={data.cover_url}
            alt=""
            className="h-full w-full object-cover"
            onError={(e) => (e.currentTarget.style.visibility = "hidden")}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <BookOpen className="h-5 w-5" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <Link to={`/books/${data.book_id}`} className="font-medium hover:underline">
          {data.title}
        </Link>
        {data.authors.length > 0 && (
          <p className="text-xs text-muted-foreground">{data.authors.join(", ")}</p>
        )}
        <div className="mt-2 space-y-1">
          {data.copies.map((c) => (
            <div key={c.copy_id} className="flex items-start gap-1.5 text-sm">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span>
                {c.location_path ?? <span className="text-muted-foreground">No shelf assigned</span>}
                {c.is_borrowed && (
                  <span className="text-muted-foreground"> · lent to {c.borrowed_by}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
