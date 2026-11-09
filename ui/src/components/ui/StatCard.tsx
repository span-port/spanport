import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  /** A kind of step ("code", "db", "external", "llm"): shows its colour next to the label. */
  swatch?: string;
  /** "error", "warning" and "good" colour the card's left edge. */
  tone?: "error" | "warning" | "good";
  /** A short line under the value, e.g. "0.25% of requests". */
  note?: ReactNode;
}

/** One number with its name, e.g. "Requests 12,410" or "Database 0.2 s". */
export function StatCard({ label, value, swatch, tone, note }: StatCardProps) {
  return (
    <div className="stat-card" data-tone={tone}>
      <span className="stat-card-label">
        {swatch && <span className={`swatch step-${swatch}`} aria-hidden="true" />}
        {label}
      </span>
      <span className="stat-card-value">{value}</span>
      {note && <span className="text-muted text-xs">{note}</span>}
    </div>
  );
}
