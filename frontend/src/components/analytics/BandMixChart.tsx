"use client";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import type { AnalyticsBucket } from "@/lib/api/types";
import { bucketsWithData, MIN_BAND_MIX_BUCKETS, toBandMixData, type BandMixPoint } from "@/lib/analytics/chartData";
import { formatCount } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/** ≤400ms per BRAND.md §11's chart draw-in ceiling. */
const ANIMATION_DURATION_MS = 350;

export function BandMixChart({ buckets }: { buckets: AnalyticsBucket[] }) {
  const reducedMotion = usePrefersReducedMotion();
  const withData = bucketsWithData(buckets);

  // Zero data-bearing buckets: nothing to plot, no X-domain — replace the chart body
  // with a caption entirely (matches the ChartCard body-slot pattern used elsewhere).
  if (withData.length === 0) {
    return (
      <ChartCard title="Band mix" subtitle="Clear / Doubtful / Suspect share per period." height={280}>
        <p className="grid h-full place-items-center text-center text-body-sm text-text-muted">
          Not enough scored volume yet to show a band mix — check back once more periods have data.
        </p>
      </ChartCard>
    );
  }

  // 1-2 data-bearing buckets: still render what exists (X-domain = only buckets with
  // data, per the brief) but caption it so a two-point "trend" isn't over-read.
  const thin = withData.length < MIN_BAND_MIX_BUCKETS;
  const data = toBandMixData(buckets);

  return (
    <ChartCard title="Band mix" subtitle="Clear / Doubtful / Suspect share per period." height={280}>
      <div className="flex h-full flex-col">
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
              <YAxis
                tickFormatter={(v) => `${v}%`}
                domain={[0, 100]}
                tick={{ fontSize: 12, fill: "var(--text-muted)" }}
                stroke="var(--border)"
              />
              <Tooltip content={<BandMixTooltip />} />
              <Legend
                iconType="square"
                iconSize={10}
                verticalAlign="bottom"
                wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }}
              />
              <Bar
                dataKey="Clear"
                stackId="mix"
                fill="var(--verdict-clear)"
                isAnimationActive={!reducedMotion}
                animationDuration={ANIMATION_DURATION_MS}
              />
              <Bar
                dataKey="Doubtful"
                stackId="mix"
                fill="var(--verdict-doubtful)"
                isAnimationActive={!reducedMotion}
                animationDuration={ANIMATION_DURATION_MS}
              />
              <Bar
                dataKey="Suspect"
                stackId="mix"
                fill="var(--verdict-suspect)"
                radius={[3, 3, 0, 0]}
                isAnimationActive={!reducedMotion}
                animationDuration={ANIMATION_DURATION_MS}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        {thin && (
          <p className="shrink-0 pt-1 text-center text-caption text-text-muted">
            Trends firm up as history accumulates.
          </p>
        )}
      </div>
    </ChartCard>
  );
}

function BandMixTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ payload: BandMixPoint }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="min-w-[200px] space-y-1.5 rounded-lg border border-border bg-surface p-3 text-body-sm shadow-2">
      <p className="font-semibold text-text">
        {label}
        {point.incomplete && <span className="ml-1.5 font-normal text-text-muted">(in progress)</span>}
      </p>
      <div className="space-y-1 text-caption">
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-2 w-2 rounded" style={{ backgroundColor: "var(--verdict-clear)" }} />
            Clear
          </span>
          <span className="font-medium tabular-nums text-text">{formatCount(point.rawClear)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-2 w-2 rounded" style={{ backgroundColor: "var(--verdict-doubtful)" }} />
            Doubtful
          </span>
          <span className="font-medium tabular-nums text-text">{formatCount(point.rawDoubtful)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-2 w-2 rounded" style={{ backgroundColor: "var(--verdict-suspect)" }} />
            Suspect
          </span>
          <span className="font-medium tabular-nums text-text">{formatCount(point.rawSuspect)}</span>
        </div>
      </div>
      <div className="border-t border-border pt-1.5 flex items-center justify-between text-caption font-semibold text-text">
        <span>Total</span>
        <span className="tabular-nums">{formatCount(point.total)}</span>
      </div>
    </div>
  );
}
