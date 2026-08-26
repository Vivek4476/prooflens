import type { AnalyticsSummary } from "@/lib/api/types";

/** Derive system-level alerts from the analytics summary. Pure, testable-by-eye. */
export function AlertsPanel({ a }: { a: AnalyticsSummary | undefined }) {
  const alerts: { cls: string; title: string; body: string }[] = [];
  if (a) {
    if ((a.suspect_pct ?? 0) >= 8)
      alerts.push({ cls: "text-verdict-suspect-fg", title: "Fraud rate elevated",
        body: `Suspect rate at ${a.suspect_pct}% today (threshold 8%).` });
    const health = a.system_health;
    if (health) {
      const pct = health.scored_without_content_pct ?? 0;
      if (pct >= 10)
        alerts.push({ cls: "text-verdict-doubtful-fg", title: "Vision degradation",
          body: `${pct}% scored without vision (fail-open).` });
    }
  }
  if (alerts.length === 0)
    return <p className="px-4 py-6 text-body-sm text-text-muted">No active alerts. System nominal.</p>;
  return (
    <div className="flex flex-col">
      {alerts.map((al, i) => (
        <div key={i} className="border-b border-border px-4 py-3 last:border-b-0">
          <b className={`text-caption font-semibold ${al.cls}`}>{al.title}</b>
          <p className="mt-0.5 text-caption text-text-secondary">{al.body}</p>
        </div>
      ))}
    </div>
  );
}
