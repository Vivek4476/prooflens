"use client";

import { BarChart3, Copy, Gauge, ShieldAlert, TrendingDown, TrendingUp } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { ChartCard } from "@/components/ui/ChartCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricCard } from "@/components/ui/MetricCard";
import { CardsSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { useAnalytics } from "@/lib/api/hooks";

/* ────────────────────────────────────────────────────────────────────────────
 * Custom Tooltip — shared across the bar chart
 * ──────────────────────────────────────────────────────────────────────────── */

interface BandTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      date: string;
      Clear: number;
      Doubtful: number;
      Suspect: number;
      totalVolume: number;
      avgScore: number;
    };
  }>;
  label?: string;
}

function BandTooltip({ active, payload, label }: BandTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const total = d.totalVolume ?? 0;
  const avg = d.avgScore ?? 0;
  const clear = d.Clear ?? 0;
  const doubtful = d.Doubtful ?? 0;
  const suspect = d.Suspect ?? 0;
  const sum = clear + doubtful + suspect || 1;

  const rows = [
    { label: "Clear", count: clear, color: "var(--verdict-clear)" },
    { label: "Doubtful", count: doubtful, color: "var(--verdict-doubtful)" },
    { label: "Suspect", count: suspect, color: "var(--verdict-suspect)" },
  ];

  return (
    <div className="rounded-lg border border-border bg-surface p-3 shadow-2 text-body-sm space-y-2 min-w-[180px] max-w-[calc(100vw-48px)]">
      <p className="font-semibold text-text">{label}</p>
      <div className="border-b border-border pb-1.5 flex items-center justify-between text-caption text-text-secondary">
        <span>Volume</span>
        <span className="font-medium text-text tabular-nums">
          {total} {total === 1 ? "image" : "images"}
        </span>
      </div>
      <div className="space-y-1 text-caption">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-text-secondary">
              <span className="h-2 w-2 rounded-sm shrink-0" style={{ backgroundColor: r.color }} />
              {r.label}
            </span>
            <span className="font-medium text-text tabular-nums">
              {r.count} ({Math.round((r.count / sum) * 100)}%)
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-border pt-1.5 flex items-center justify-between text-caption font-semibold text-text">
        <span>Avg Score</span>
        <span className="tabular-nums">{Math.round(avg)}/100</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────────
 * Score Trend Tooltip
 * ──────────────────────────────────────────────────────────────────────────── */

interface ScoreTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { date: string; avgScore: number; totalVolume: number } }>;
  label?: string;
}

function ScoreTooltip({ active, payload, label }: ScoreTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const score = d.avgScore ?? 0;
  const vol = d.totalVolume ?? 0;
  const band = score >= 70 ? "Clear" : score >= 40 ? "Doubtful" : "Suspect";
  const color =
    score >= 70
      ? "var(--verdict-clear)"
      : score >= 40
        ? "var(--verdict-doubtful)"
        : "var(--verdict-suspect)";

  return (
    <div className="rounded-lg border border-border bg-surface p-3 shadow-2 text-body-sm space-y-1.5 min-w-[160px] max-w-[calc(100vw-48px)]">
      <p className="font-semibold text-text">{label}</p>
      <div className="flex items-center justify-between text-caption">
        <span className="text-text-secondary">Avg Score</span>
        <span className="font-semibold tabular-nums text-text">{Math.round(score)}/100</span>
      </div>
      <div className="flex items-center justify-between text-caption">
        <span className="text-text-secondary">Band</span>
        <span className="font-medium" style={{ color }}>
          {band}
        </span>
      </div>
      <div className="flex items-center justify-between text-caption">
        <span className="text-text-secondary">Volume</span>
        <span className="font-medium text-text tabular-nums">{vol}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────────
 * Donut center label
 * ──────────────────────────────────────────────────────────────────────────── */

function DonutCenter({ avg, total }: { avg: number; total: number }) {
  return (
    <text
      x="50%"
      y="50%"
      textAnchor="middle"
      dominantBaseline="central"
      className="select-none"
    >
      <tspan
        x="50%"
        dy="-8"
        fill="var(--text)"
        fontSize="24"
        fontWeight="700"
        style={{ fontFeatureSettings: "'cv02', 'tnum'" }}
      >
        {Math.round(avg)}
      </tspan>
      <tspan x="50%" dy="18" fill="var(--text-muted)" fontSize="11" fontWeight="500">
        avg of {total}
      </tspan>
    </text>
  );
}

/* ────────────────────────────────────────────────────────────────────────────
 * Page
 * ──────────────────────────────────────────────────────────────────────────── */

const BAND_COLORS = {
  Clear: "var(--verdict-clear)",
  Doubtful: "var(--verdict-doubtful)",
  Suspect: "var(--verdict-suspect)",
} as const;

export default function AnalyticsPage() {
  const { data: a, isLoading, isError, refetch } = useAnalytics();

  if (isError) {
    return (
      <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <p className="text-body-sm text-text-secondary">
          Couldn&apos;t reach the scoring API. Is the backend running?
        </p>
        <button
          onClick={() => refetch()}
          className="text-caption font-medium text-text-secondary underline"
        >
          Retry
        </button>
      </Card>
    );
  }

  if (a && a.total === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No data to chart yet"
        what="Analytics summarise scored verdicts. Score photos or seed the demo to populate the charts."
        cta={{ label: "Analyze a Photo", href: "/analyze" }}
      />
    );
  }

  /* ── Derived data ──────────────────────────────────────────────────────── */

  const flagReasons = (a?.top_reasons ?? []).filter(
    (r) => r.reason_code !== "clear",
  );

  const series = (a?.series ?? []).map((d) => ({
    date: d.date.slice(5),
    Clear: d.clear,
    Doubtful: d.doubtful,
    Suspect: d.suspect,
    totalVolume: d.count,
    avgScore: d.avg_score,
  }));

  const bandDist = a?.band_distribution ?? { Clear: 0, Doubtful: 0, Suspect: 0 };
  const donutData = (
    Object.entries(bandDist) as [keyof typeof BAND_COLORS, number][]
  )
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  // Score trend direction
  const trendUp =
    series.length >= 2
      ? series[series.length - 1].avgScore >= series[series.length - 2].avgScore
      : true;

  const reasonBars = flagReasons.map((r) => ({
    reason: r.reason.length > 45 ? r.reason.slice(0, 42) + "…" : r.reason,
    fullReason: r.reason,
    count: r.count,
  }));

  /* ── Render ────────────────────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Where is capture risk trending?"
      />

      {/* ── KPI cards ────────────────────────────────────────────────────── */}
      {isLoading || !a ? (
        <CardsSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard
            label="Total scored"
            value={a.total}
            icon={BarChart3}
          />
          <MetricCard
            label="Suspect %"
            value={a.suspect_pct}
            suffix="%"
            icon={ShieldAlert}
            accent
            decimals={1}
          />
          <MetricCard
            label="Avg score"
            value={a.avg_score}
            suffix="/100"
            icon={trendUp ? TrendingUp : TrendingDown}
            decimals={1}
          />
          <MetricCard
            label="Duplicates caught"
            value={a.duplicates_caught}
            icon={Copy}
          />
        </div>
      )}

      {/* ── Charts grid ──────────────────────────────────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Band mix over time — stacked bar */}
        <ChartCard
          title="Band mix over time"
          subtitle="A rising Suspect share is the first sign of a capture or model shift."
        >
          {isLoading || !a ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <>
              <div className="h-full w-full" aria-hidden="true">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={series}
                    margin={{ top: 4, right: 8, left: -8, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="gClear" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--verdict-clear)" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="var(--verdict-clear)" stopOpacity={0.45} />
                      </linearGradient>
                      <linearGradient id="gDoubtful" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--verdict-doubtful)" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="var(--verdict-doubtful)" stopOpacity={0.45} />
                      </linearGradient>
                      <linearGradient id="gSuspect" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--verdict-suspect)" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="var(--verdict-suspect)" stopOpacity={0.45} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                      stroke="var(--border)"
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                      stroke="var(--border)"
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      content={<BandTooltip />}
                      cursor={{ fill: "var(--surface-2)", opacity: 0.5 }}
                    />
                    <Legend
                      iconType="square"
                      iconSize={10}
                      wrapperStyle={{ fontSize: 11, color: "var(--text-muted)", paddingTop: 4 }}
                    />
                    <Bar dataKey="Clear" stackId="b" fill="url(#gClear)" maxBarSize={56} />
                    <Bar dataKey="Doubtful" stackId="b" fill="url(#gDoubtful)" maxBarSize={56} />
                    <Bar
                      dataKey="Suspect"
                      stackId="b"
                      fill="url(#gSuspect)"
                      maxBarSize={56}
                      radius={[3, 3, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {/* Screen-reader accessible table */}
              <table className="sr-only">
                <caption>Band mix over time: daily counts of Clear, Doubtful, and Suspect.</caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Clear</th>
                    <th scope="col">Doubtful</th>
                    <th scope="col">Suspect</th>
                  </tr>
                </thead>
                <tbody>
                  {series.map((d) => (
                    <tr key={d.date}>
                      <th scope="row">{d.date}</th>
                      <td>{d.Clear}</td>
                      <td>{d.Doubtful}</td>
                      <td>{d.Suspect}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </ChartCard>

        {/* Band distribution — donut */}
        <ChartCard
          title="Band distribution"
          subtitle="Overall verdict breakdown across all scored images."
        >
          {isLoading || !a ? (
            <Skeleton className="h-full w-full" />
          ) : donutData.length === 0 ? (
            <p className="grid h-full place-items-center text-body-sm text-text-muted">
              No data yet.
            </p>
          ) : (
            <div className="h-full w-full" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius="60%"
                    outerRadius="82%"
                    paddingAngle={3}
                    strokeWidth={0}
                  >
                    {donutData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={BAND_COLORS[entry.name]}
                        className="transition-opacity duration-200 hover:opacity-80"
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => [
                      `${value} (${Math.round((value / a.total) * 100)}%)`,
                      name,
                    ]}
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 11, color: "var(--text-muted)", paddingTop: 4 }}
                  />
                  <DonutCenter avg={a.avg_score} total={a.total} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>

        {/* Average score trend — area chart (full width) */}
        <ChartCard
          title="Average score trend"
          subtitle="Daily average scoring health. Lines at 70 (Clear) and 40 (Suspect threshold)."
          fullWidth
          height={220}
        >
          {isLoading || !a ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <div className="h-full w-full" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={series}
                  margin={{ top: 8, right: 8, left: -8, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gScore" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--brand-crimson)" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="var(--brand-crimson)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                    stroke="var(--border)"
                    tickLine={false}
                  />
                  <YAxis
                    domain={[0, 100]}
                    ticks={[0, 20, 40, 60, 80, 100]}
                    tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                    stroke="var(--border)"
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<ScoreTooltip />} />
                  <ReferenceLine
                    y={70}
                    stroke="var(--verdict-clear)"
                    strokeDasharray="4 4"
                    strokeOpacity={0.6}
                    label={{
                      value: "Clear ≥ 70",
                      position: "insideTopRight",
                      fill: "var(--verdict-clear)",
                      fontSize: 10,
                    }}
                  />
                  <ReferenceLine
                    y={40}
                    stroke="var(--verdict-suspect)"
                    strokeDasharray="4 4"
                    strokeOpacity={0.6}
                    label={{
                      value: "Suspect < 40",
                      position: "insideBottomRight",
                      fill: "var(--verdict-suspect)",
                      fontSize: 10,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="avgScore"
                    stroke="var(--brand-crimson)"
                    strokeWidth={2}
                    fill="url(#gScore)"
                    dot={{ r: 3, fill: "var(--surface)", stroke: "var(--brand-crimson)", strokeWidth: 2 }}
                    activeDot={{ r: 5, fill: "var(--brand-crimson)", stroke: "var(--surface)", strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>

        {/* Top flag reasons — horizontal bar chart (full width) */}
        <ChartCard
          title="Top flag reasons"
          subtitle="What is actually driving Doubtful and Suspect verdicts."
          fullWidth
          height={Math.max(200, reasonBars.length * 48 + 32)}
        >
          {isLoading || !a ? (
            <Skeleton className="h-full w-full" />
          ) : flagReasons.length === 0 ? (
            <p className="grid h-full place-items-center text-body-sm text-text-muted">
              No flags yet — every verdict is Clear.
            </p>
          ) : (
            <div className="h-full w-full" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={reasonBars}
                  layout="vertical"
                  margin={{ top: 0, right: 24, left: 8, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gReason" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="var(--brand-crimson)" stopOpacity={0.7} />
                      <stop offset="100%" stopColor="var(--verdict-suspect)" stopOpacity={0.5} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--border)"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                    stroke="var(--border)"
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="reason"
                    width={220}
                    tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
                    stroke="var(--border)"
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value} verdicts`, "Count"]}
                    labelFormatter={(label: string) => {
                      const match = reasonBars.find((r) => r.reason === label);
                      return match?.fullReason ?? label;
                    }}
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill="url(#gReason)"
                    radius={[0, 4, 4, 0]}
                    maxBarSize={28}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>
      </div>

      <p className="text-caption text-text-muted">
        Reason labels are the exact verdict vocabulary. Time series accrues as
        more images are scored.
      </p>
    </div>
  );
}
