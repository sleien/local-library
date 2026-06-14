import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ScanLine, Trash2, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { BarcodeScanner } from "@/components/BarcodeScanner";
import { Button, Card, EmptyState, Label, Select } from "@/components/ui";
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
  const [scanning, setScanning] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [result, setResult] = useState<BulkAddResult | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: locations } = useQuery({
    queryKey: ["locations", hid],
    queryFn: () => api.get<LocationNode[]>(`/api/households/${hid}/locations`),
    enabled: !!hid,
  });
  const locationOptions = useMemo(() => (locations ? flatten(locations) : []), [locations]);
  const locationLabel = locationOptions.find((o) => String(o.id) === locationId)?.label.trim();

  const onDetected = (code: string) => {
    setCodes((prev) => {
      if (prev.includes(code)) return prev;
      toast.push(`Scanned ${code}`, "info");
      return [...prev, code];
    });
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
      setScanning(false);
      toast.push(`Added ${res.added} book${res.added === 1 ? "" : "s"}`, "success");
    } catch (err) {
      toast.push(err instanceof ApiError ? err.message : "Bulk add failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Mass add</h1>
        <p className="text-sm text-muted-foreground">
          Pick a location, then scan as many barcodes as you like. They are all added at once.
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

        <Button
          variant={scanning ? "destructive" : "default"}
          className="w-full"
          onClick={() => setScanning((s) => !s)}
        >
          <ScanLine className="h-4 w-4" />
          {scanning ? "Stop scanning" : "Start scanning"}
        </Button>

        {scanning && <BarcodeScanner onDetected={onDetected} continuous />}
      </Card>

      {codes.length > 0 && (
        <Card className="p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="font-medium">
              {codes.length} scanned{locationLabel ? ` → ${locationLabel}` : ""}
            </p>
            <Button variant="ghost" size="sm" onClick={() => setCodes([])}>
              Clear
            </Button>
          </div>
          <ul className="divide-y rounded-md border">
            {codes.map((c) => (
              <li key={c} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="font-mono">{c}</span>
                <button
                  onClick={() => setCodes(codes.filter((x) => x !== c))}
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

      {codes.length === 0 && !result && !scanning && (
        <EmptyState title="Nothing scanned yet" hint="Start scanning to build a batch." />
      )}
    </div>
  );
}
