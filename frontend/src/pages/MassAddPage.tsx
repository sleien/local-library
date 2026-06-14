import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, CheckCircle2, Plus, ScanLine, Trash2, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { Button, Card, Input, Label, Select } from "@/components/ui";
import type { BulkAddResult, LocationNode } from "@/lib/types";

function flatten(nodes: LocationNode[], depth = 0): { id: number; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"  ".repeat(depth)}${n.name}` },
    ...flatten(n.children, depth + 1),
  ]);
}

export function MassAddPage() {
  const { household } = useAuth();
  const hid = household?.id;
  const toast = useToast();
  const [locationId, setLocationId] = useState("");
  const [camera, setCamera] = useState(false);
  const [entry, setEntry] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [result, setResult] = useState<BulkAddResult | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });
  const locationOptions = useMemo(() => (locations ? flatten(locations) : []), [locations]);
  const locationLabel = locationOptions.find((o) => String(o.id) === locationId)?.label.trim();

  // Append a scanned code. Duplicates are allowed so the same title can be
  // added as several copies.
  const addCode = (raw: string) => {
    const code = raw.trim();
    if (!code) return;
    setCodes((prev) => [...prev, code]);
    toast.push(`Added ${code}`, "info");
  };

  const onEntryKey = (e: React.KeyboardEvent) => {
    // A handheld (keyboard-wedge) scanner types the digits then sends Enter.
    if (e.key === "Enter") {
      e.preventDefault();
      addCode(entry);
      setEntry("");
    }
  };

  const commit = async () => {
    if (!hid || codes.length === 0) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await api.post<BulkAddResult>(`/api/households/${hid}/copies/bulk`, {
        location_id: locationId ? Number(locationId) : null,
        isbns: codes,
      });
      setResult(res);
      setCodes([]);
      toast.push(`Added ${res.added} book${res.added === 1 ? "" : "s"}`, "success");
      inputRef.current?.focus();
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Bulk add failed", "error");
    } finally {
      setBusy(false);
    }
  };

  // Keep the scan field focused so a handheld scanner just works.
  useEffect(() => {
    if (!camera) inputRef.current?.focus();
  }, [camera]);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Mass add</h1>
        <p className="text-sm text-muted-foreground">
          Pick a location, then scan a stack of barcodes (handheld scanner or phone camera) and
          add them all at once.
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

      {result && (
        <Card className="p-4">
          <p className="mb-2 font-medium">
            {result.added} added, {result.failed} failed
          </p>
          <ul className="divide-y rounded-md border">
            {result.items.map((item, i) => (
              <li key={`${item.isbn}-${i}`} className="flex items-center gap-2 px-3 py-2 text-sm">
                {item.status === "added" || item.status === "copy_added" ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                )}
                <span className="font-mono text-xs text-muted-foreground">{item.isbn}</span>
                <span className="truncate">
                  {item.title ?? (item.status === "not_found" ? "Not found" : item.message)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
