"use client";

import { Suspense, useMemo } from "react";

import { BarChart3 } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton, CardsSkeleton } from "@/components/ui/Skeleton";
import { FilterBar } from "@/components/analytics/FilterBar";
import { InsightsPanel } from "@/components/analytics/InsightsPanel";
import { KpiRow } from "@/components/analytics/KpiRow";
import { CaptureRiskTrend } from "@/components/analytics/CaptureRiskTrend";
import { BandMixChart } from "@/components/analytics/BandMixChart";
import { TopFlagReasons } from "@/components/analytics/TopFlagReasons";
import { useAnalytics } from "@/lib/api/hooks";
import { useAnalyticsFilters } from "@/lib/analytics/useAnalyticsFilters";
import type { AnalyticsParams } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** Full-page skeleton, matching the final layout — used both as the Suspense
 *  fallback (before useSearchParams resolves) and the first-load state below. */
function AnalyticsSkeleton() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-24 w-full" />
      {/* grid matches KpiRow exactly (grid-cols-2 lg:grid-cols-4, no md: step) so the
          loading state doesn't reflow once real data replaces the skeleton. */}
      <CardsSkeleton count={4} className="grid-cols-2 gap-4 md:grid-cols-2 lg:grid-cols-4" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[340px] w-full" />
        <Skeleton className="h-[340px] w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function AnalyticsPageInner() {
  const { params, preset, bucket, from, to, setPreset, setCustomRange, setBucket } = useAnalyticsFilters();
  const { data: a, isLoading, isError, refetch, isPlaceholderData } = useAnalytics(params);

  // Second, cheap query for the previous period's duplicates_caught (not on `previous`).
  // CRITICAL: memoized — a fresh object identity every render would reset useAnalytics's
  // 300ms debounce indefinitely, same reasoning as the primary `params` in
  // useAnalyticsFilters.
  const prevPeriodFrom = a?.previous_period.from;
  const prevPeriodTo = a?.previous_period.to;
  const prevParams: AnalyticsParams = useMemo(() => {
    if (!prevPeriodFrom || !prevPeriodTo) return {};
    return {
      start_date: prevPeriodFrom,
      end_date: prevPeriodTo,
      bucket: "daily",
    };
  }, [prevPeriodFrom, prevPeriodTo]);
  const hasPrevWindow = Boolean(a);
  const { data: prevA } = useAnalytics(prevParams, Boolean(prevPeriodFrom && prevPeriodTo));
  const prevDuplicatesCaught = hasPrevWindow ? (prevA?.duplicates_caught ?? null) : null;

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics" description="Is capture risk trending up, and where should you look?" />
      <FilterBar
        preset={preset}
        bucket={bucket}
        from={from}
        to={to}
        onPresetChange={setPreset}
        onCustomRangeChange={setCustomRange}
        onBucketChange={setBucket}
        period={a?.period}
        previousPeriod={a?.previous_period}
      />

      {isError ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
          <p className="text-body-sm text-text-secondary">Couldn&apos;t load analytics from the API.</p>
          <Button variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
      ) : isLoading || !a ? (
        <AnalyticsSkeleton />
      ) : a.total === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="No data to chart yet"
          what="Analytics summarise scored verdicts for the selected range. Score photos, widen the date range, or seed the demo to populate the charts."
          cta={{ label: "Analyze a photo", href: "/analyze" }}
        />
      ) : (
        <div className={cn("space-y-8 transition-opacity", isPlaceholderData && "opacity-60")}>
          <InsightsPanel analytics={a} prevDuplicatesCaught={prevDuplicatesCaught} />
          <KpiRow analytics={a} prevDuplicatesCaught={prevDuplicatesCaught} />
          <div className="grid gap-6 lg:grid-cols-2">
            <CaptureRiskTrend buckets={a.buckets} previous={a.previous} />
            <BandMixChart buckets={a.buckets} />
          </div>
          <TopFlagReasons topReasons={a.top_reasons} />
        </div>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<AnalyticsSkeleton />}>
      <AnalyticsPageInner />
    </Suspense>
  );
}
