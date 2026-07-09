"use client";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ui/ChartCard";
import { ChartTooltip } from "@/components/analytics/ChartTooltip";
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
            <BarChart
              data={data}
              margin={{ top: 12, right: 8, left: 0, bottom: 0 }}
              barCategoryGap={data.length > 20 ? "8%" : "24%"}
              maxBarSize={40}
            >
              <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: "var(--border)" }}
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                minTickGap={24}
              />
              <YAxis
                tickFormatter={(v) => `${Math.round(v)}%`}
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickLine={false}
                axisLine={false}
                width={42}
                tick={{ fontSize: 11, fill: "var(--text-muted)" }}
              />
              <Tooltip content={<BandMixTooltip />} cursor={{ fill: "var(--text-muted)", opacity: 0.08 }} />
              <Legend
                iconType="circle"
                iconSize={8}
                verticalAlign="bottom"
                height={28}
                wrapperStyle={{ fontSize: 11, color: "var(--text-muted)", paddingTop: 4 }}
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
    <ChartTooltip
      title={label ?? point.label}
      titleNote={point.incomplete ? "(in progress)" : undefined}
      rows={[
        { label: "Clear", value: formatCount(point.rawClear), swatchColor: "var(--verdict-clear)" },
        { label: "Doubtful", value: formatCount(point.rawDoubtful), swatchColor: "var(--verdict-doubtful)" },
        { label: "Suspect", value: formatCount(point.rawSuspect), swatchColor: "var(--verdict-suspect)" },
      ]}
      // No per-bucket "previous" exists (backend's `previous` is a single period
      // aggregate, not per-bucket) — omitted here rather than fabricated. The total
      // row stands in as the footer instead of a dishonest comparison.
      footer={`Total ${formatCount(point.total)}`}
    />
  );
}
