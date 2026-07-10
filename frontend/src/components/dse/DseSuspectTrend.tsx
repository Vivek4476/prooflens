"use client";
import type { Key } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DotProps } from "recharts";

import { ChartCard } from "@/components/ui/ChartCard";
import { ChartTooltip } from "@/components/analytics/ChartTooltip";
import type { TrendPoint } from "@/lib/analytics/chartData";
import { toDseTrendData } from "@/lib/dse/scorecard";
import type { DseTrendPoint } from "@/lib/api/types";
import { formatCount, formatPct } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/** ≤400ms per BRAND.md §11's chart draw-in ceiling — same as CaptureRiskTrend. */
const ANIMATION_DURATION_MS = 350;

/**
 * The DSE scorecard's suspect-rate trend — reuses CaptureRiskTrend's exact visual
 * language (accent area fill, hollow incomplete-bucket marker, same tooltip shape)
 * but scoped to a single agent_id's `trend[]` from /v1/dse/{agent_id}. Unlike the
 * page-level chart there is no comparable "previous period" aggregate in the DSE
 * contract, so the dashed reference line is omitted rather than faked.
 */
export function DseSuspectTrend({ trend }: { trend: DseTrendPoint[] }) {
  const reducedMotion = usePrefersReducedMotion();
  const data = toDseTrendData(trend);

  return (
    <ChartCard
      title="Suspect-rate trend"
      subtitle="This DSE's suspect rate per period."
      height={280}
    >
      {data.length < 2 ? (
        <p className="grid h-full place-items-center text-body-sm text-text-muted">
          Not enough buckets yet to chart a trend.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 12, right: 14, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="dseSuspectFill" x1="0" y1="0" x2="0" y2="1">
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
            <Tooltip content={<DseTrendTooltip />} cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }} />
            <Area
              type="monotone"
              dataKey="rate"
              stroke="var(--accent)"
              strokeWidth={2}
              fill="url(#dseSuspectFill)"
              dot={(props: DotProps & { payload?: TrendPoint; key?: Key }) => {
                // Pull `key` out of the spread — recharts passes it inside the props object,
                // and spreading a `key` into JSX warns in React 18+ (see React docs).
                const { key, ...rest } = props;
                return <DseTrendDot key={key} {...rest} />;
              }}
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

/** Same honesty device as CaptureRiskTrend's TrendDot: the current in-progress bucket
 *  gets a hollow marker so an unfinished period never reads as a completed dip. */
function DseTrendDot(props: DotProps & { payload?: TrendPoint }) {
  const { cx, cy, payload } = props;
  // `key` is applied by the parent `dot` render fn — this component only draws the marker.
  if (cx == null || cy == null || !payload?.incomplete) return <g />;
  return (
    <circle
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

function DseTrendTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TrendPoint }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <ChartTooltip
      title={point.label}
      titleNote={point.incomplete ? "(in progress)" : undefined}
      rows={[{ label: "Suspect rate", value: formatPct(point.rate) }]}
      footer={`${formatCount(point.total)} ${point.total === 1 ? "image scored" : "images scored"}`}
    />
  );
}
