import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { api } from "@/lib/api";
import { EmptyState, PageSpinner, StarRating } from "@/components/ui";
import { formatDate } from "@/lib/utils";
import type { ReadingLogEntry } from "@/lib/types";

function groupKey(e: ReadingLogEntry): string {
  const d = e.finished_at ?? e.started_at;
  if (!d) return "Undated";
  return String(new Date(d).getFullYear());
}

export function TimelinePage() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["reading-log"],
    queryFn: () => api.get<ReadingLogEntry[]>("/api/reading-log"),
  });

  const groups = useMemo(() => {
    const map = new Map<string, ReadingLogEntry[]>();
    for (const e of entries ?? []) {
      const k = groupKey(e);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(e);
    }
    // Years descending, "Undated" last.
    return [...map.entries()].sort((a, b) => {
      if (a[0] === "Undated") return 1;
      if (b[0] === "Undated") return -1;
      return Number(b[0]) - Number(a[0]);
    });
  }, [entries]);

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Reading timeline</h1>
        <p className="text-sm text-muted-foreground">
          When you read which book. Mark books as read with a finish date to place them here.
        </p>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !entries || entries.length === 0 ? (
        <EmptyState
          title="Nothing read yet"
          hint="Set a book's status to Read (with a finish date) to start your timeline."
        />
      ) : (
        <div className="space-y-6">
          {groups.map(([year, items]) => (
            <div key={year}>
              <h2 className="mb-2 text-sm font-semibold text-muted-foreground">{year}</h2>
              <ol className="relative space-y-3 border-l pl-5">
                {items.map((e) => (
                  <li key={`${e.book_id}-${e.finished_at}`} className="relative">
                    <span className="absolute -left-[1.42rem] top-2 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
                    <Link
                      to={`/books/${e.book_id}`}
                      className="flex gap-3 rounded-lg border bg-card p-2.5 transition-colors hover:bg-accent"
                    >
                      <div className="h-16 w-11 shrink-0 overflow-hidden rounded bg-muted">
                        {e.cover_url ? (
                          <img
                            src={e.cover_url}
                            alt=""
                            className="h-full w-full object-cover"
                            onError={(ev) => (ev.currentTarget.style.visibility = "hidden")}
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center text-muted-foreground">
                            <BookOpen className="h-5 w-5" />
                          </div>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-1 text-sm font-medium">{e.title}</p>
                        {e.authors.length > 0 && (
                          <p className="line-clamp-1 text-xs text-muted-foreground">
                            {e.authors.join(", ")}
                          </p>
                        )}
                        <div className="mt-1 flex items-center gap-2">
                          {e.finished_at && (
                            <span className="text-xs text-muted-foreground">
                              {formatDate(e.finished_at)}
                            </span>
                          )}
                          {e.rating && <StarRating value={e.rating} readOnly />}
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
