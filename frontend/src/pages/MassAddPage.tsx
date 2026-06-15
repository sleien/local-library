import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Camera,
  CheckCircle2,
  Plus,
  RefreshCw,
  RotateCw,
  ScanLine,
  SearchX,
  Trash2,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { Button, Card, EmptyState, Input, Label, Select } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { BulkAddItem, BulkAddResult, LocationNode } from "@/lib/types";

function flatten(nodes: LocationNode[]): { id: number; label: string }[] {
  return nodes.flatMap((n) => [{ id: n.id, label: n.path }, ...flatten(n.children)]);
}

interface HistoryItem {
  isbn: string;
  title: string | null;
  status: string; // added | copy_added | not_found | error
  ts: number;
  available?: boolean; // recheck found it in the catalog
}

type StatusFilter = "all" | "added" | "not_found" | "error";

const isSuccess = (s: string) => s === "added" || s === "copy_added";

export function MassAddPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const toast = useToast();
  const qc = useQueryClient();
  const [locationId, setLocationId] = useState("");
  const [camera, setCamera] = useState(false);
  const [entry, setEntry] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [busyIsbn, setBusyIsbn] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const historyKey = hid ? `bibliothek-bulk-history-${hid}` : "";

  // Load the per-library history from localStorage.
  useEffect(() => {
    if (!historyKey) return;
    try {
      const raw = localStorage.getItem(historyKey);
      setHistory(raw ? (JSON.parse(raw) as HistoryItem[]) : []);
    } catch {
      setHistory([]);
    }
  }, [historyKey]);

  const persist = (next: HistoryItem[]) => {
    setHistory(next);
    if (historyKey) localStorage.setItem(historyKey, JSON.stringify(next));
  };

  // Insert/replace history rows keyed by ISBN (newest first).
  const upsert = (items: { isbn: string; title?: string | null; status: string }[]) => {
    const map = new Map(history.map((h) => [h.isbn, h]));
    const now = Date.now();
    for (const it of items) {
      const prev = map.get(it.isbn);
      map.set(it.isbn, {
        isbn: it.isbn,
        title: it.title ?? prev?.title ?? null,
        status: it.status,
        ts: now,
        available: isSuccess(it.status) ? undefined : prev?.available,
      });
    }
    persist([...map.values()].sort((a, b) => b.ts - a.ts));
  };

  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });
  const locationOptions = useMemo(() => (locations ? flatten(locations) : []), [locations]);
  const locationLabel = locationOptions.find((o) => String(o.id) === locationId)?.label;

  const addCode = (raw: string) => {
    const code = raw.trim();
    if (!code) return;
    setCodes((prev) => [...prev, code]);
    toast.push(`Added ${code}`, "info");
  };

  const onEntryKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCode(entry);
      setEntry("");
    }
  };

  const commit = async () => {
    if (!hid || codes.length === 0) return;
    setBusy(true);
    try {
      const res = await api.post<BulkAddResult>(`/api/households/${hid}/copies/bulk`, {
        location_id: locationId ? Number(locationId) : null,
        isbns: codes,
      });
      upsert(res.items.map((i: BulkAddItem) => ({ isbn: i.isbn, title: i.title, status: i.status })));
      setCodes([]);
      qc.invalidateQueries({ queryKey: ["search"] });
      toast.push(`Added ${res.added}, ${res.failed} failed`, res.failed ? "info" : "success");
      inputRef.current?.focus();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Bulk add failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const retry = async (item: HistoryItem) => {
    if (!hid) return;
    setBusyIsbn(item.isbn);
    try {
      const res = await api.post<BulkAddResult>(`/api/households/${hid}/copies/bulk`, {
        location_id: locationId ? Number(locationId) : null,
        isbns: [item.isbn],
      });
      const r = res.items[0];
      upsert([{ isbn: item.isbn, title: r?.title, status: r?.status ?? "error" }]);
      qc.invalidateQueries({ queryKey: ["search"] });
      toast.push(
        isSuccess(r?.status ?? "") ? `Added ${r.title ?? item.isbn}` : "Still couldn't add it",
        isSuccess(r?.status ?? "") ? "success" : "info",
      );
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Retry failed", "error");
    } finally {
      setBusyIsbn(null);
    }
  };

  // Re-check whether the ISBN is in the online catalog now (without adding).
  const recheck = async (item: HistoryItem) => {
    setBusyIsbn(item.isbn);
    try {
      await api.get(`/api/lookup/isbn/${encodeURIComponent(item.isbn)}`);
      persist(history.map((h) => (h.isbn === item.isbn ? { ...h, available: true } : h)));
      toast.push("Found in the catalog now — press Retry to add", "success");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        persist(history.map((h) => (h.isbn === item.isbn ? { ...h, available: false } : h)));
        toast.push("Still not in the catalog", "info");
      } else {
        toast.push("Recheck failed", "error");
      }
    } finally {
      setBusyIsbn(null);
    }
  };

  const visible = history.filter((h) => {
    if (filter === "all") return true;
    if (filter === "added") return isSuccess(h.status);
    return h.status === filter;
  });
  const failedCount = history.filter((h) => !isSuccess(h.status)).length;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Bulk add</h1>
        <p className="text-sm text-muted-foreground">
          Pick a location, then scan a stack of barcodes (handheld scanner or phone camera) and
          add them all at once. Anything that fails stays in the history below to retry later.
        </p>
      </div>

      <Card className="space-y-3 p-4">
        <div>
          <Label>Destination location</Label>
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
          <Label>Scan or type a barcode</Label>
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={entry}
              onChange={(e) => setEntry(e.target.value)}
              onKeyDown={onEntryKey}
              placeholder="Point a handheld scanner here, or type an ISBN and press Enter"
              inputMode="numeric"
              autoFocus
              autoComplete="off"
            />
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 shrink-0"
              aria-label="Add barcode"
              onClick={() => {
                addCode(entry);
                setEntry("");
                inputRef.current?.focus();
              }}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            A USB/Bluetooth scanner that types like a keyboard works here — each scan adds a row.
          </p>
        </div>

        <Button
          variant={camera ? "destructive" : "subtle"}
          className="w-full"
          onClick={() => setCamera((c) => !c)}
        >
          {camera ? <ScanLine className="h-4 w-4" /> : <Camera className="h-4 w-4" />}
          {camera ? "Stop camera" : "Use phone camera instead"}
        </Button>

        {camera && <BarcodeScanner onDetected={addCode} continuous />}
      </Card>

      {codes.length > 0 && (
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="font-medium">
              {codes.length} to add{locationLabel ? ` → ${locationLabel}` : ""}
            </p>
            <Button variant="ghost" size="sm" onClick={() => setCodes([])}>
              Clear
            </Button>
          </div>
          <ul className="divide-y rounded-md border">
            {codes.map((c, i) => (
              <li key={i} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="font-mono">{c}</span>
                <button
                  onClick={() => setCodes(codes.filter((_, idx) => idx !== i))}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label="Remove"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
          <Button className="mt-3 w-full" onClick={commit} loading={busy}>
            Add {codes.length} book{codes.length === 1 ? "" : "s"}
          </Button>
        </Card>
      )}

      {history.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">
              History{failedCount > 0 ? ` · ${failedCount} to fix` : ""}
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => confirm("Clear the bulk-add history?") && persist([])}
            >
              Clear history
            </Button>
          </div>

          <div className="flex flex-wrap gap-1 text-sm">
            {(
              [
                ["all", "All"],
                ["added", "Added"],
                ["not_found", "Not found"],
                ["error", "Errors"],
              ] as [StatusFilter, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={cn(
                  "rounded-full border px-3 py-1",
                  filter === key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {visible.length === 0 ? (
            <EmptyState title="Nothing here" hint="No items match this filter." />
          ) : (
            <ul className="divide-y rounded-md border">
              {visible.map((item) => (
                <li key={item.isbn} className="flex items-center gap-3 px-3 py-2">
                  <StatusIcon status={item.status} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      {item.title ?? <span className="text-muted-foreground">Unknown title</span>}
                    </p>
                    <p className="font-mono text-xs text-muted-foreground">
                      {item.isbn}
                      {item.available ? " · available now" : ""}
                    </p>
                  </div>
                  {!isSuccess(item.status) && (
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busyIsbn === item.isbn}
                        onClick={() => recheck(item)}
                        title="Check the online catalog again"
                      >
                        <RefreshCw className="h-3.5 w-3.5" /> Recheck
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        loading={busyIsbn === item.isbn}
                        onClick={() => retry(item)}
                      >
                        <RotateCw className="h-3.5 w-3.5" /> Retry
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {codes.length === 0 && history.length === 0 && !camera && (
        <EmptyState title="Nothing scanned yet" hint="Scan a stack to add them all at once." />
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (isSuccess(status)) return <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />;
  if (status === "not_found") return <SearchX className="h-4 w-4 shrink-0 text-amber-500" />;
  return <XCircle className="h-4 w-4 shrink-0 text-destructive" />;
}
