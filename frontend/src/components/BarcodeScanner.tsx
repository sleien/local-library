import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader, type IScannerControls } from "@zxing/browser";
import { DecodeHintType, BarcodeFormat } from "@zxing/library";
import { CameraOff } from "lucide-react";

interface Props {
  // Called for each successful scan. Return false to ignore (e.g. duplicate).
  onDetected: (code: string) => void;
  // Keep scanning after a hit (mass-add). Otherwise the caller usually closes.
  continuous?: boolean;
}

// EAN-13 / ISBN barcodes are the relevant formats for books.
const hints = new Map();
hints.set(DecodeHintType.POSSIBLE_FORMATS, [
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
  BarcodeFormat.UPC_A,
  BarcodeFormat.CODE_128,
]);

export function BarcodeScanner({ onDetected, continuous }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const lastRef = useRef<{ code: string; at: number }>({ code: "", at: 0 });

  useEffect(() => {
    const reader = new BrowserMultiFormatReader(hints);
    let controls: IScannerControls | null = null;
    let cancelled = false;

    reader
      .decodeFromConstraints(
        { video: { facingMode: "environment" } },
        videoRef.current!,
        (result) => {
          if (!result) return;
          const code = result.getText();
          const now = Date.now();
          // Debounce repeated reads of the same barcode.
          if (code === lastRef.current.code && now - lastRef.current.at < 2500) return;
          lastRef.current = { code, at: now };
          onDetected(code);
        },
      )
      .then((c) => {
        if (cancelled) c.stop();
        else controls = c;
      })
      .catch((e) => setError(e?.message || "Camera unavailable"));

    return () => {
      cancelled = true;
      controls?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
        <CameraOff className="h-6 w-6" />
        <p>{error}</p>
        <p>Grant camera access or type the ISBN manually.</p>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-lg border bg-black">
      <video ref={videoRef} className="aspect-[4/3] w-full object-cover" muted playsInline />
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="h-24 w-3/4 rounded-md border-2 border-primary/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
      </div>
      {continuous && (
        <p className="absolute bottom-2 left-0 right-0 text-center text-xs text-white/90">
          Keep scanning — each book is added automatically
        </p>
      )}
    </div>
  );
}
