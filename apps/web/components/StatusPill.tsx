import { toneFromSeverity } from "@/lib/format";

export function StatusPill({
  value,
  tone,
}: {
  value: string;
  tone?: "critical" | "warning" | "success" | "info" | "neutral";
}) {
  const resolvedTone = tone ?? toneFromSeverity(value);
  return <span className={`status-pill status-pill-${resolvedTone}`}>{value}</span>;
}
