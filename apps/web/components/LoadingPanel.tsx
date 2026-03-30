export function LoadingPanel({ label = "Loading planner data..." }: { label?: string }) {
  return (
    <div className="loading-panel" role="status" aria-live="polite">
      <span className="loading-dot" />
      <span>{label}</span>
    </div>
  );
}
