import { Link } from "react-router-dom";
import { BookOpen, Check, Copy as CopyIcon } from "lucide-react";
import type { BookSummary } from "@/lib/types";
import { Badge } from "./ui";
import { cn } from "@/lib/utils";

const statusLabel: Record<string, string> = {
  read: "Read",
  reading: "Reading",
  want: "Want",
};

export function BookCard({ book }: { book: BookSummary }) {
  return (
    <Link
      to={`/books/${book.id}`}
      className="group flex flex-col overflow-hidden rounded-lg border bg-card transition-shadow hover:shadow-md"
    >
      <div className="relative aspect-[2/3] bg-muted">
        {book.cover_url ? (
          <img
            src={book.cover_url}
            alt={book.title}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <BookOpen className="h-10 w-10" />
          </div>
        )}
        {book.my_status && (
          <span
            className={cn(
              "absolute left-1.5 top-1.5 flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              book.my_status === "read"
                ? "bg-green-500/90 text-white"
                : "bg-primary/90 text-primary-foreground",
            )}
          >
            {book.my_status === "read" && <Check className="h-3 w-3" />}
            {statusLabel[book.my_status] ?? book.my_status}
          </span>
        )}
        {book.copy_count > 1 && (
          <span className="absolute right-1.5 top-1.5 flex items-center gap-1 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white">
            <CopyIcon className="h-3 w-3" />
            {book.copy_count}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <p className="line-clamp-2 text-sm font-medium leading-tight">{book.title}</p>
        {book.authors.length > 0 && (
          <p className="line-clamp-1 text-xs text-muted-foreground">{book.authors.join(", ")}</p>
        )}
        {book.tags.length > 0 && (
          <div className="mt-auto flex flex-wrap gap-1 pt-1">
            {book.tags.slice(0, 2).map((t) => (
              <Badge key={t.id} color={t.color} className="text-[10px]">
                {t.name}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
