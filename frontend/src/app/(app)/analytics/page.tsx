"use client";

import { BarChart3, Copy, Gauge, ShieldAlert } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
  }));

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Where is capture risk trending?" />

      {isLoading || !a ? (
        <CardsSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Total scored" value={a.total} icon={BarChart3} />
          <MetricCard label="Suspect %" value={a.suspect_pct} suffix="%" icon={ShieldAlert} accent />
          <MetricCard label="Avg score" value={a.avg_score} suffix="/100" icon={Gauge} />
          <MetricCard label="Duplicates caught" value={a.duplicates_caught} icon={Copy} />
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
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "var(--text-muted)" }} stroke="var(--border)" />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="Clear" stackId="b" fill="var(--verdict-clear)" maxBarSize={64} />
                <Bar dataKey="Doubtful" stackId="b" fill="var(--verdict-doubtful)" maxBarSize={64} />
                <Bar dataKey="Suspect" stackId="b" fill="var(--verdict-suspect)" maxBarSize={64} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
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
            <ul className="space-y-3">
              {flagReasons.map((r) => (
                <li key={r.reason_code}>
                  <div className="mb-1 flex items-baseline justify-between gap-3">
                    <span className="truncate text-body-sm text-text-secondary">{r.reason}</span>
                    <span className="shrink-0 text-body-sm font-medium tabular-nums text-text">{r.count}</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-text-secondary"
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
