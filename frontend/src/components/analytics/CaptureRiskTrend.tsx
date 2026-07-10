"use client";
import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DotProps } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import { CardAggChip, CardAggSelect } from "@/components/analytics/CardAggControl";
import { useAnalytics } from "@/lib/api/hooks";
import type { AnalyticsBucket, AnalyticsParams, Bucket, PeriodAggregate } from "@/lib/api/types";
import { previousPeriodRate, toTrendData, type TrendPoint } from "@/lib/analytics/chartData";
import { effectiveBucket, isOverridden } from "@/lib/analytics/cardOverride";
import { TREND_AGG_PARAM, useCardAggOverride } from "@/lib/analytics/useCardAggOverride";
import { formatCount, formatPct } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/** ≤400ms per BRAND.md §11's chart draw-in ceiling. */
const ANIMATION_DURATION_MS = 350;

export function CaptureRiskTrend({
  buckets,
  previous,
  bucket: globalBucket,
  from,
  to,
}: {
  buckets: AnalyticsBucket[];
  previous: PeriodAggregate;
  /** The page's global bucket + resolved range — needed so this card can gate
   *  its own override options and, when overridden, run its own query. */
  bucket: Bucket;
  from?: string;
  to?: string;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const [choice, setChoice] = useCardAggOverride(TREND_AGG_PARAM);
  const overridden = isOverridden(choice, globalBucket);
  const cardBucket = effectiveBucket(choice, globalBucket);

  // Only fetch a second, card-owned query when genuinely overridden — the
  // "Follow page" (or same-as-global) path renders the page's own props with
  // zero extra requests. Memoized so useAnalytics's 300ms debounce can settle.
  const ownParams: AnalyticsParams = useMemo(
    () => ({ start_date: from, end_date: to, bucket: cardBucket, group_by: "none" }),
    [from, to, cardBucket],
  );
  const ownEnabled = overridden && Boolean(from && to);
  const { data: ownData, isError: ownIsError, isPlaceholderData: ownIsPlaceholder } = useAnalytics(
    ownParams,
    ownEnabled,
  );

  const effectiveBuckets = overridden ? (ownData?.buckets ?? []) : buckets;
  const effectivePrevious = overridden ? (ownData?.previous ?? previous) : previous;
  const data = toTrendData(effectiveBuckets);
  const prevRate = previousPeriodRate(effectivePrevious);

  const action = (
    <div className="flex flex-col items-end gap-1.5">
      <CardAggSelect
        choice={choice}
        onChange={setChoice}
        from={from}
        to={to}
        label="Capture-risk trend aggregation"
      />
      {overridden && <CardAggChip bucket={cardBucket} onResync={() => setChoice("page")} />}
    </div>
  );

  return (
    <ChartCard
      title="Capture-risk trend"
      subtitle="Suspect rate per period, vs the previous period's average."
      height={280}
      action={action}
    >
      {overridden && ownEnabled && ownIsError ? (
        <p className="grid h-full place-items-center text-center text-body-sm text-text-muted">
          Couldn&apos;t load this card&apos;s {cardBucket} view — try resyncing to the page aggregation.
        </p>
      ) : data.length < 2 ? (
        <p className="grid h-full place-items-center text-body-sm text-text-muted">
          Not enough buckets yet to chart a trend.
        </p>
      ) : (
        <ResponsiveContainer
          width="100%"
          height="100%"
          className={overridden && ownIsPlaceholder ? "opacity-60 transition-opacity" : "transition-opacity"}
        >
          <AreaChart data={data} margin={{ top: 12, right: 14, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="captureRiskFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.16} />
                <stop offset="92%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }}
              minTickGap={28}
            />
            <YAxis
              tickFormatter={(v) => `${Math.round(v)}%`}
              tickLine={false}
              axisLine={false}
              width={40}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }}
            />
            <ReferenceLine
              y={prevRate}
              stroke="var(--text-muted)"
              strokeDasharray="4 4"
              strokeOpacity={0.7}
              label={{
                value: "Prev avg",
                position: "insideTopLeft",
                dy: -4,
                fontSize: 11,
                fill: "var(--text-muted)",
              }}
            />
            <Tooltip
              content={<TrendTooltip prevRate={prevRate} />}
              cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
            />
            <Area
              type="monotone"
              dataKey="rate"
              stroke="var(--accent)"
              strokeWidth={2}
              fill="url(#captureRiskFill)"
              dot={(props: DotProps & { payload?: TrendPoint }) => <TrendDot {...props} />}
              activeDot={{ r: 4, fill: "var(--accent)", stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={!reducedMotion}
              animationDuration={ANIMATION_DURATION_MS}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

/**
 * Static dots are suppressed to keep dense daily trends clean; the line + area carries the
 * shape and hovering reveals per-point values. The one exception is the current in-progress
 * bucket, which gets a hollow marker so an unfinished period never reads as a completed dip.
 */
function TrendDot(props: DotProps & { payload?: TrendPoint }) {
  const { cx, cy, payload, key } = props;
  if (cx == null || cy == null || !payload?.incomplete) return <g key={key} />;
  return (
    <circle
      key={key}
      cx={cx}
      cy={cy}
      r={4}
      fill="var(--surface)"
      stroke="var(--accent)"
      strokeWidth={2}
      opacity={0.9}
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
    <ChartTooltip
      title={point.label}
      titleNote={point.incomplete ? "(in progress)" : undefined}
      rows={[
        { label: "Suspect rate", value: formatPct(point.rate) },
        // There's no per-bucket "previous" — the backend only gives us a single
        // previous-PERIOD aggregate, the same value the reference line plots.
        { label: "Prev period avg", value: formatPct(prevRate) },
      ]}
      footer={`${formatCount(point.total)} ${point.total === 1 ? "image scored" : "images scored"}`}
    />
  );
}
