"use client";
import { MetricCard } from "@/components/ui/MetricCard";
import { formatCount, formatPct, formatScore } from "@/lib/format";
import { computeDelta } from "@/lib/analytics/deltas";
import type { AnalyticsSummary } from "@/lib/api/types";

// `prevDuplicatesCaught` sourcing (wired in Task 9): the page-level component runs a
// SECOND `useAnalytics({ start_date: previous_period.from, end_date: previous_period.to,
// bucket: "daily" })` query (previous_period bounds come from this same `analytics`
// response) and passes its `.data?.duplicates_caught ?? null` down to both `KpiRow` and
// `InsightsPanel` — the primary AnalyticsSummary has no server-side
// `previous.duplicates_caught` field, so this is the only way to get a comparable prior
// value. That params object must be memoized (useMemo) like the primary query's, or the
// 300ms debounce in `useAnalytics` never settles (see Task 3/4 carry-forward note).
export function KpiRow({
  analytics,
  prevDuplicatesCaught,
}: {
  analytics: AnalyticsSummary;
  prevDuplicatesCaught: number | null;
}) {
  const a = analytics;
  const totalDelta = computeDelta(a.total, a.previous.total, a.previous.total, {
    higherIsBad: false,
    unit: "count",
  });
  const suspectRateDelta = computeDelta(a.suspect_pct, ratePct(a.previous), a.previous.total, {
    higherIsBad: true,
    unit: "pts",
  });
  const avgScoreDelta = computeDelta(a.avg_score, a.previous.avg_score, a.previous.total, {
    higherIsBad: false,
    unit: "pts",
  });
  const dupDelta =
    prevDuplicatesCaught == null
      ? null
      : computeDelta(a.duplicates_caught, prevDuplicatesCaught, a.previous.total, {
          higherIsBad: true,
          unit: "count",
        });

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <MetricCard
        label="Total scored"
        value={formatCount(a.total)}
        sub={deltaSub(totalDelta)}
        subTone={totalDelta.sentiment}
      />
      <MetricCard
        label="Suspect rate"
        value={formatPct(a.suspect_pct)}
        sub={deltaSub(suspectRateDelta)}
        subTone={suspectRateDelta.sentiment}
        accent
      />
      <MetricCard
        label="Avg score"
        value={formatScore(a.avg_score)}
        suffix="/ 100"
        sub={deltaSub(avgScoreDelta)}
        subTone={avgScoreDelta.sentiment}
      />
      <MetricCard
        label="Duplicates caught"
        value={formatCount(a.duplicates_caught)}
        sub={dupDelta ? deltaSub(dupDelta) : "Loading previous period…"}
        subTone={dupDelta ? dupDelta.sentiment : "neutral"}
      />
    </div>
  );
}

function ratePct(p: { suspect: number; total: number }): number {
  return p.total ? (p.suspect / p.total) * 100 : 0;
}

function deltaSub(d: ReturnType<typeof computeDelta>): string {
  if (d.insufficientHistory) return "Insufficient history for comparison";
  return d.words ?? "No change vs previous period";
}
