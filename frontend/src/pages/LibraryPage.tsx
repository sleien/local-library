import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Filter, PlusCircle, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { hasSeenTour, startTour } from "@/onboarding/tour";
import type { BookSummary, LocationNode, Tag } from "@/lib/types";
import { BookCard } from "@/components/BookCard";
import { Badge, Button, buttonClass, EmptyState, Input, PageSpinner, Select } from "@/components/ui";

function flattenLocations(nodes: LocationNode[], depth = 0): { id: number; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"  ".repeat(depth)}${n.name}` },
    ...flattenLocations(n.children, depth + 1),
  ]);
}

export function LibraryPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [borrowed, setBorrowed] = useState("");
  const [locationId, setLocationId] = useState("");
  const [activeTags, setActiveTags] = useState<number[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // Run the onboarding tour once for new users.
  useEffect(() => {
    if (hasSeenTour()) return;
    const t = setTimeout(() => startTour(), 600);
    return () => clearTimeout(t);
  }, []);

  const { data: tags } = useQuery({
    queryKey: ["tags", hid],
    queryFn: () => api.get<Tag[]>(`/api/households/${hid}/tags`),
    enabled: !!hid,
  });
  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (hid) p.set("household_id", String(hid));
    if (q) p.set("q", q);
    if (status) p.set("status", status);
    if (borrowed) p.set("borrowed", borrowed);
    if (locationId) p.set("location_id", locationId);
    activeTags.forEach((t) => p.append("tag", String(t)));
    return p.toString();
  }, [hid, q, status, borrowed, locationId, activeTags]);

  const { data: books, isLoading } = useQuery({
    queryKey: ["search", params],
    queryFn: () => api.get<BookSummary[]>(`/api/search?${params}`),
    enabled: !!hid,
  });

  const locationOptions = useMemo(
    () => (locations ? flattenLocations(locations) : []),
    [locations],
  );

  const toggleTag = (id: number) =>
    setActiveTags((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));

  const hasFilters = status || borrowed || locationId || activeTags.length > 0;
  const canWrite = household?.role !== "viewer";

  return (
    <div className="space-y-4" data-tour="library">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">Library</h1>
          {!canWrite && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              Read-only
            </span>
          )}
        </div>
        {canWrite && (
          <Link to="/add" className={buttonClass("default", "md", "hidden md:inline-flex")}>
            <PlusCircle className="h-4 w-4" /> Add book
          </Link>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1" data-tour="search">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search title, author, ISBN..."
            className="pl-9"
          />
        </div>
        <Button
          variant={hasFilters ? "default" : "outline"}
          size="icon"
          onClick={() => setShowFilters((s) => !s)}
          aria-label="Filters"
          data-tour="filter"
        >
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {showFilters && (
        <div className="space-y-3 rounded-lg border bg-card p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Any read status</option>
              <option value="want">Want to read</option>
              <option value="reading">Reading</option>
              <option value="read">Read</option>
            </Select>
            <Select value={borrowed} onChange={(e) => setBorrowed(e.target.value)}>
              <option value="">Any availability</option>
              <option value="true">Currently borrowed</option>
              <option value="false">On the shelf</option>
            </Select>
            <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Any location</option>
              {locationOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
          {tags && tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => (
                <Badge
                  key={t.id}
                  onClick={() => toggleTag(t.id)}
                  className={activeTags.includes(t.id) ? "bg-primary text-primary-foreground" : ""}
                  color={activeTags.includes(t.id) ? null : t.color}
                >
                  {t.name}
                </Badge>
              ))}
            </div>
          )}
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStatus("");
                setBorrowed("");
                setLocationId("");
                setActiveTags([]);
              }}
            >
              <X className="h-3.5 w-3.5" /> Clear filters
            </Button>
          )}
        </div>
      )}

      {isLoading ? (
        <PageSpinner />
      ) : !books || books.length === 0 ? (
        <EmptyState
          title="No books found"
          hint={hasFilters || q ? "Try adjusting your search or filters." : "Add your first book to get started."}
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {books.map((b) => (
            <BookCard key={b.id} book={b} />
          ))}
        </div>
      )}
    </div>
  );
}
