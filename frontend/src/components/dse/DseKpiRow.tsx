import { MetricCard } from "@/components/ui/MetricCard";
import { formatCount, formatPct, formatScore } from "@/lib/format";
import { isSparseDse, MIN_TOTAL_FOR_CONFIDENT_RATE } from "@/lib/dse/scorecard";

/**
 * The scorecard's three headline KPIs. Same small-sample honesty as the analytics
 * KpiRow's delta guard, but framed for a single DSE: below MIN_TOTAL_FOR_CONFIDENT_RATE
 * scored captures, the rate/score are still shown (real numbers, never hidden) but
 * captioned as low-confidence rather than presented as a settled read on this person.
 */
export function DseKpiRow({
  total,
  suspectRate,
  avgScore,
}: {
  total: number;
  suspectRate: number;
  avgScore: number;
}) {
  const sparse = isSparseDse(total);
  const sparseNote = `Fewer than ${MIN_TOTAL_FOR_CONFIDENT_RATE} scored — not enough volume to read confidently.`;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <MetricCard label="Total scored" value={formatCount(total)} sub={sparse ? sparseNote : undefined} />
      <MetricCard
        label="Suspect rate"
        value={formatPct(suspectRate * 100)}
        sub={sparse ? sparseNote : undefined}
        accent
      />
      <MetricCard
        label="Avg score"
        value={formatScore(avgScore)}
        suffix="/ 100"
        sub={sparse ? sparseNote : undefined}
      />
    </div>
  );
}
