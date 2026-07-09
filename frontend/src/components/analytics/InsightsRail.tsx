"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import type { AnalyticsSummary } from "@/lib/api/types";
import { computeInsights, NO_SHIFTS_FALLBACK, type InsightSeverity } from "@/lib/analytics/insights";
import { formatDateRange } from "@/lib/format";
import { cn } from "@/lib/utils";

// "high"/"warn" borrow verdict hues because they genuinely mean "worth attention" /
// "needs review"; "info" is NOT a verdict (nothing is wrong) so it stays neutral gray —
// never --verdict-clear, which would wrongly imply a positive verdict judgement.
const DOT: Record<InsightSeverity, string> = {
  high: "bg-verdict-suspect",
  warn: "bg-verdict-doubtful",
  info: "bg-text-muted",
};

/** "Data as of 14:32" — the wall-clock time this analytics response was last fetched, so a
 *  viewer knows how fresh the numbers are. 24h local time. */
function freshnessLabel(dataUpdatedAt: number): string | null {
  if (!dataUpdatedAt) return null;
  return new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

/**
 * The right-side insights rail (Pain 7). Skimmers read this without touching the charts:
 * the comparison window, the computed "what changed" bullets, and a data-freshness stamp.
 * The page renders it sticky in the right column on xl, and as a full-width block directly
 * after the KPI row below xl.
 */
export function InsightsRail({
  analytics,
  prevDuplicatesCaught,
  dataUpdatedAt,
}: {
  analytics: AnalyticsSummary;
  prevDuplicatesCaught: number | null;
  dataUpdatedAt: number;
}) {
  const insights = computeInsights(analytics, prevDuplicatesCaught);
  const window = `${formatDateRange(analytics.period.from, analytics.period.to)} · vs ${formatDateRange(
    analytics.previous_period.from,
    analytics.previous_period.to,
  )}`;
  const asOf = freshnessLabel(dataUpdatedAt);

  return (
    <Card>
      <CardHeader title="What changed" subtitle={window} />
      <div className="p-4">
        {insights.length === 0 ? (
          <p className="text-body-sm text-text-secondary">{NO_SHIFTS_FALLBACK}</p>
        ) : (
          <ul className="space-y-3">
            {insights.map((i) => (
              <li key={i.id} className="flex items-start gap-2.5 text-body-sm text-text">
                <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", DOT[i.severity])} aria-hidden />
                <span>{i.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {asOf && (
        <div className="border-t border-border px-4 py-2.5">
          <p className="text-caption text-text-muted">Data as of {asOf}</p>
        </div>
      )}
    </Card>
  );
}
