"use client";

import { BarChart3 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
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
import { formatMs } from "@/lib/utils";

interface CustomTooltipProps {
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

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const total = data.totalVolume ?? 0;
    const avgScore = data.avgScore ?? 0;
    const clear = data.Clear ?? 0;
    const doubtful = data.Doubtful ?? 0;
    const suspect = data.Suspect ?? 0;
    const sum = clear + doubtful + suspect || 1;

    const clearPct = Math.round((clear / sum) * 100);
    const doubtfulPct = Math.round((doubtful / sum) * 100);
    const suspectPct = Math.round((suspect / sum) * 100);

    return (
      <div className="rounded-lg border border-border bg-surface p-3 shadow-2 text-body-sm space-y-2 min-w-[200px]">
        <p className="font-semibold text-text">{label}</p>
        <div className="border-b border-border pb-1.5 flex items-center justify-between text-caption text-text-secondary">
          <span>Total volume</span>
          <span className="font-medium text-text tabular-nums">{total} {total === 1 ? "image" : "images"}</span>
        </div>
        <div className="space-y-1 text-caption">
          <div className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-text-secondary">
              <span className="h-2 w-2 rounded bg-verdict-clear" style={{ backgroundColor: "var(--verdict-clear)" }} />
              Clear
            </span>
            <span className="font-medium text-text tabular-nums">{clear} ({clearPct}%)</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-text-secondary">
              <span className="h-2 w-2 rounded bg-verdict-doubtful" style={{ backgroundColor: "var(--verdict-doubtful)" }} />
              Doubtful
            </span>
            <span className="font-medium text-text tabular-nums">{doubtful} ({doubtfulPct}%)</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-text-secondary">
              <span className="h-2 w-2 rounded bg-verdict-suspect" style={{ backgroundColor: "var(--verdict-suspect)" }} />
              Suspect
            </span>
            <span className="font-medium text-text tabular-nums">{suspect} ({suspectPct}%)</span>
          </div>
        </div>
        <div className="border-t border-border pt-1.5 flex items-center justify-between text-caption font-semibold text-text">
          <span>Avg Score</span>
          <span className="tabular-nums">{Math.round(avgScore)}/100</span>
        </div>
      </div>
    );
  }
  return null;
}

export default function AnalyticsPage() {
  const { data: a, isLoading, isError, refetch } = useAnalytics();

  if (isError) {
    return (
      <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <p className="text-body-sm text-text-secondary">Couldn&apos;t load analytics from the API.</p>
        <button onClick={() => refetch()} className="text-caption font-medium text-text-secondary underline">
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

  const flagReasons = (a?.top_reasons ?? []).filter((r) => r.reason_code !== "clear");
  const maxReason = Math.max(1, ...flagReasons.map((r) => r.count));
  const series = (a?.series ?? []).map((d) => ({
    date: d.date.slice(5),
    Clear: d.clear,
    Doubtful: d.doubtful,
    Suspect: d.suspect,
    totalVolume: d.count,
    avgScore: d.avg_score,
  }));

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Where is capture risk trending?" />

      {isLoading || !a ? (
        <CardsSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Total scored" value={a.total} />
          <MetricCard label="Suspect %" value={a.suspect_pct} suffix="%" accent />
          <MetricCard label="Avg score" value={a.avg_score} suffix="/100" />
          <MetricCard label="Duplicates caught" value={a.duplicates_caught} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
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
                  <BarChart data={series} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend
                      iconType="square"
                      iconSize={10}
                      wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }}
                    />
                    <Bar dataKey="Clear" stackId="b" fill="var(--verdict-clear)" maxBarSize={64} />
                    <Bar dataKey="Doubtful" stackId="b" fill="var(--verdict-doubtful)" maxBarSize={64} />
                    <Bar dataKey="Suspect" stackId="b" fill="var(--verdict-suspect)" maxBarSize={64} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <table className="sr-only">
                <caption>
                  Band mix over time: daily counts of Clear, Doubtful, and Suspect verdicts.
                </caption>
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

        <ChartCard
          title="Top flag reasons"
          subtitle="What is actually driving Doubtful and Suspect verdicts."
        >
          {isLoading || !a ? (
            <Skeleton className="h-full w-full" />
          ) : flagReasons.length === 0 ? (
            <p className="grid h-full place-items-center text-body-sm text-text-muted">
              No flags yet — every verdict is Clear.
            </p>
          ) : (
            <ul className="space-y-4">
              {flagReasons.map((r) => (
                <li
                  key={r.reason_code}
                  className="group rounded-lg p-2 -mx-2 hover:bg-surface-2 transition-colors duration-200"
                >
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <span className="truncate text-body-sm text-text-secondary group-hover:text-text transition-colors duration-200">
                      {r.reason}
                    </span>
                    <span className="shrink-0 text-body-sm font-medium tabular-nums text-text">
                      {r.count}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-text-secondary group-hover:bg-text transition-all duration-300"
                      style={{ width: `${(r.count / maxReason) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </ChartCard>
      </div>

      <p className="text-caption text-text-muted">
        Reason labels are the exact verdict vocabulary. Time series accrues as more images are scored.
      </p>
    </div>
  );
}
