import type { Classification } from "@/lib/artifacts";

const BAND_STYLES: Record<string, string> = {
  low: "bg-neutral-800 text-neutral-300",
  medium: "bg-amber-950 text-amber-300",
  high: "bg-red-950 text-red-300",
};

export function BandBadge({ band }: { band: string }) {
  return (
    <span className={`rounded px-2 py-0.5 font-mono text-xs ${BAND_STYLES[band] ?? ""}`}>
      {band}
    </span>
  );
}

const CLASSIFICATION_STYLES: Record<Classification, string> = {
  AGENTIC_CANDIDATE: "bg-emerald-950 text-emerald-300",
  HUMAN_GATE: "bg-sky-950 text-sky-300",
  KEEP_DETERMINISTIC: "bg-neutral-800 text-neutral-300",
};

export const CLASSIFICATION_LABELS: Record<Classification, string> = {
  AGENTIC_CANDIDATE: "agentic candidate",
  HUMAN_GATE: "human gate",
  KEEP_DETERMINISTIC: "keep deterministic",
};

export function ClassificationBadge({ classification }: { classification: Classification }) {
  return (
    <span
      className={`whitespace-nowrap rounded px-2 py-0.5 font-mono text-xs ${CLASSIFICATION_STYLES[classification]}`}
    >
      {CLASSIFICATION_LABELS[classification]}
    </span>
  );
}

export function SpecStatusBadge({ status }: { status: "draft" | "approved" | null }) {
  if (status === null) {
    return <span className="font-mono text-xs text-neutral-600">no spec</span>;
  }
  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-xs ${
        status === "approved"
          ? "bg-emerald-950 text-emerald-300"
          : "bg-amber-950 text-amber-300"
      }`}
    >
      {status}
    </span>
  );
}
