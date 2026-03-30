export function MetricCard({
  label,
  value,
  detail,
  accent = "teal",
}: {
  label: string;
  value: string;
  detail: string;
  accent?: "teal" | "amber" | "ink" | "rose" | "primary";
}) {
  return (
    <article className={`metric-card metric-card-${accent}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      <p className="metric-detail">{detail}</p>
    </article>
  );
}
