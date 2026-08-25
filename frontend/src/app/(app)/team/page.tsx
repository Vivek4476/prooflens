"use client";

import { Suspense } from "react";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { CardsSkeleton } from "@/components/ui/Skeleton";
import { KpiRow } from "@/components/analytics/KpiRow";
import { CaptureRiskTrend } from "@/components/analytics/CaptureRiskTrend";
import { BandMixChart } from "@/components/analytics/BandMixChart";
import { TopFlagReasons } from "@/components/analytics/TopFlagReasons";
import { useAnalytics } from "@/lib/api/hooks";
import { useTeamFilters } from "@/lib/analytics/useTeamFilters";
import { rankHotspots } from "@/lib/analytics/hotspots";
import { formatPct, formatCount } from "@/lib/format";

/** Minimum scored volume before a rep's suspect rate is trustworthy enough to rank. */
const MIN_TOTAL_FOR_RATE = 20;
/** Cap member leaderboard — same discipline as ByTeamPanel. */
const MAX_MEMBER_ROWS = 20;

function TeamInner() {
  const router = useRouter();
  const { dim, node, params, bucket } = useTeamFilters();
  const { data: a, isLoading } = useAnalytics(params, Boolean(dim && node));

  if (!dim || !node) {
    return (
      <EmptyState
        icon={Users}
        title="No team selected"
        what="Open a team from the Analytics leaderboard to see its scorecard."
      />
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title={node} description={`Team scorecard · by ${dim}`} />
      {isLoading || !a ? (
        <CardsSkeleton count={4} className="grid-cols-2 gap-4 md:grid-cols-2 lg:grid-cols-4" />
      ) : a.total === 0 ? (
        <EmptyState
          icon={Users}
          title="No decisions"
          what={`No scored captures for ${node} in range.`}
        />
      ) : (
        <div className="space-y-8">
          <KpiRow analytics={a} />
          <div className="grid gap-6 lg:grid-cols-2">
            <CaptureRiskTrend
              buckets={a.buckets}
              previous={a.previous}
              bucket={bucket}
              from={a.period.from}
              to={a.period.to}
            />
            <BandMixChart
              buckets={a.buckets}
              bucket={bucket}
              from={a.period.from}
              to={a.period.to}
            />
          </div>
          <TopFlagReasons
            topReasons={a.top_reasons}
            from={a.period.from}
            to={a.period.to}
          />
          <Card>
            <CardHeader
              title="Members"
              subtitle="Reps in this team, highest risk first."
            />
            <ul className="p-2">
              {rankHotspots(a.groups, { minTotal: MIN_TOTAL_FOR_RATE, maxRows: MAX_MEMBER_ROWS }).ranked.map(
                (g, i) => (
                  <li key={g.agent_id ?? g.node}>
                    <button
                      type="button"
                      onClick={() =>
                        g.agent_id &&
                        router.push(`/dse?agent=${encodeURIComponent(g.agent_id)}`)
                      }
                      className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-surface-2"
                    >
                      <span className="w-4 shrink-0 text-caption tabular-nums text-text-muted">
                        {i + 1}
                      </span>
                      <span className="flex-1 truncate text-body-sm text-text">{g.node}</span>
                      <span className="shrink-0 text-body-sm tabular-nums text-text-secondary">
                        {formatPct(g.suspect_rate * 100)} · {formatCount(g.total)} scored
                      </span>
                    </button>
                  </li>
                ),
              )}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}

export default function TeamPage() {
  return (
    <Suspense fallback={<CardsSkeleton count={4} className="grid-cols-2 gap-4 md:grid-cols-2 lg:grid-cols-4" />}>
      <TeamInner />
    </Suspense>
  );
}
