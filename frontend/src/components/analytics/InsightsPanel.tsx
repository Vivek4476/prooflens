"use client";
import type { AnalyticsSummary } from "@/lib/api/types";
import { computeInsights, NO_SHIFTS_FALLBACK, type InsightSeverity } from "@/lib/analytics/insights";
import { Card, CardHeader } from "@/components/ui/Card";
import { formatDateRange } from "@/lib/format";
import { cn } from "@/lib/utils";

// "warn"/"high" borrow verdict hues because they genuinely mean "worth attention" /
// "needs review"; "info" is NOT a verdict (nothing is wrong) so it gets a neutral gray,
// never --verdict-clear (that would wrongly imply a positive verdict judgement here).
const DOT: Record<InsightSeverity, string> = {
  high: "bg-verdict-suspect",
  warn: "bg-verdict-doubtful",
  info: "bg-text-muted",
};

export function InsightsPanel({
  analytics,
  prevDuplicatesCaught,
}: {
  analytics: AnalyticsSummary;
  prevDuplicatesCaught: number | null;
}) {
  const insights = computeInsights(analytics, prevDuplicatesCaught);
  const subtitle = `Computed from ${formatDateRange(analytics.period.from, analytics.period.to)}, vs the previous period.`;
  return (
    <Card>
      <CardHeader title="What changed" subtitle={subtitle} />
      <div className="p-4">
        {insights.length === 0 ? (
          <p className="text-body-sm text-text-secondary">{NO_SHIFTS_FALLBACK}</p>
        ) : (
          <ul className="space-y-2.5">
            {insights.map((i) => (
              <li key={i.id} className="flex items-start gap-2.5 text-body-sm text-text">
                <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", DOT[i.severity])} aria-hidden />
                <span>{i.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
