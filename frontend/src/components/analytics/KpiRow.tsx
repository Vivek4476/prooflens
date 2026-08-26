"use client";
import { MetricCard } from "@/components/ui/MetricCard";
import { formatCount, formatPct } from "@/lib/format";
import { computeDelta } from "@/lib/analytics/deltas";
import { bandRate } from "@/lib/analytics/bandRates";
import type { AnalyticsSummary } from "@/lib/api/types";

export function KpiRow({ analytics }: { analytics: AnalyticsSummary }) {
  const a = analytics;

  const totalDelta = computeDelta(a.total, a.previous.total, a.previous.total, {
    higherIsBad: false,
    unit: "count",
  });

  const suspectRateDelta = computeDelta(a.suspect_pct, ratePct(a.previous), a.previous.total, {
    higherIsBad: true,
    unit: "pts",
  });

  const doubtfulRateDelta = computeDelta(
    bandRate(a.band_distribution, a.total, "Doubtful"),
    a.previous.total ? (a.previous.doubtful / a.previous.total) * 100 : 0,
    a.previous.total,
    { higherIsBad: true, unit: "pts" },
  );

  const unassessedRateDelta = computeDelta(
    bandRate(a.band_distribution, a.total, "Unassessed"),
    a.previous.total ? (a.previous.unassessed / a.previous.total) * 100 : 0,
    a.previous.total,
    { higherIsBad: true, unit: "pts" },
  );

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <MetricCard
        label="Total scored"
        value={formatCount(a.total)}
        sub={deltaSub(totalDelta)}
        subDirection={totalDelta.direction}
      />
      <MetricCard
        label="Suspect rate"
        value={formatPct(a.suspect_pct)}
        sub={deltaSub(suspectRateDelta)}
        subDirection={suspectRateDelta.direction}
        accent
      />
      <MetricCard
        label="Doubtful rate"
        value={formatPct(bandRate(a.band_distribution, a.total, "Doubtful"))}
        sub={deltaSub(doubtfulRateDelta)}
        subDirection={doubtfulRateDelta.direction}
      />
      <MetricCard
        label="Unassessed rate"
        value={formatPct(bandRate(a.band_distribution, a.total, "Unassessed"))}
        sub={deltaSub(unassessedRateDelta)}
        subDirection={unassessedRateDelta.direction}
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
