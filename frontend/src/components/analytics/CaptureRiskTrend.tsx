"use client";
import {
  Line,
  LineChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DotProps } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import type { AnalyticsBucket, PeriodAggregate } from "@/lib/api/types";
import { previousPeriodRate, toTrendData, type TrendPoint } from "@/lib/analytics/chartData";
import { formatCount, formatPct } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/** ≤400ms per BRAND.md §11's chart draw-in ceiling. */
const ANIMATION_DURATION_MS = 350;

export function CaptureRiskTrend({
  buckets,
  previous,
}: {
  buckets: AnalyticsBucket[];
  previous: PeriodAggregate;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const data = toTrendData(buckets);
  const prevRate = previousPeriodRate(previous);

  return (
    <ChartCard
      title="Capture-risk trend"
      subtitle="Suspect rate per period, vs the previous period's average."
      height={280}
    >
      {data.length < 2 ? (
        <p className="grid h-full place-items-center text-body-sm text-text-muted">
          Not enough buckets yet to chart a trend.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 12, fill: "var(--text-muted)" }}
              stroke="var(--border)"
            />
            <YAxis
              tickFormatter={(v) => `${Math.round(v)}%`}
              tick={{ fontSize: 12, fill: "var(--text-muted)" }}
              stroke="var(--border)"
            />
            <ReferenceLine
              y={prevRate}
              stroke="var(--text-muted)"
              strokeDasharray="4 4"
              label={{
                value: "Previous avg",
                position: "insideBottomLeft",
                dy: 10,
                fontSize: 12,
                fill: "var(--text-muted)",
              }}
            />
            <Tooltip content={<TrendTooltip prevRate={prevRate} />} />
            <Line
              type="monotone"
              dataKey="rate"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={(props: DotProps & { payload?: TrendPoint }) => <TrendDot {...props} />}
              isAnimationActive={!reducedMotion}
              animationDuration={ANIMATION_DURATION_MS}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

/**
 * Hollow, lighter dot for the current in-progress bucket so an unfinished period never
 * reads as a completed decline — filled dot for complete buckets.
 */
function TrendDot(props: DotProps & { payload?: TrendPoint }) {
  const { cx, cy, payload, key } = props;
  if (cx == null || cy == null) return <g key={key} />;
  const incomplete = payload?.incomplete ?? false;
  return (
    <circle
      key={key}
      cx={cx}
      cy={cy}
      r={4}
      fill={incomplete ? "var(--surface)" : "var(--accent)"}
      stroke="var(--accent)"
      strokeWidth={2}
      opacity={incomplete ? 0.6 : 1}
    />
  );
}

function TrendTooltip({
  active,
  payload,
  prevRate,
}: {
  active?: boolean;
  payload?: Array<{ payload: TrendPoint }>;
  prevRate: number;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="min-w-[180px] space-y-1.5 rounded-lg border border-border bg-surface p-3 text-body-sm shadow-2">
      <p className="font-semibold text-text">
        {point.label}
        {point.incomplete && <span className="ml-1.5 font-normal text-text-muted">(in progress)</span>}
      </p>
      <div className="flex items-center justify-between gap-4 text-caption text-text-secondary">
        <span>Suspect rate</span>
        <span className="font-medium tabular-nums text-text">{formatPct(point.rate)}</span>
      </div>
      <div className="flex items-center justify-between gap-4 text-caption text-text-secondary">
        <span>vs previous period</span>
        <span className="font-medium tabular-nums text-text">{formatPct(prevRate)}</span>
      </div>
      <div className="border-t border-border pt-1.5 text-caption text-text-muted">
        <span className="tabular-nums">{formatCount(point.total)}</span>{" "}
        {point.total === 1 ? "image scored" : "images scored"}
      </div>
    </div>
  );
}
