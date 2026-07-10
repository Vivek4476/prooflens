"use client";

import { Suspense, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";
import { Search, UserSearch } from "lucide-react";

import { ChainBreadcrumb } from "@/components/dse/ChainBreadcrumb";
import { DseBandMix } from "@/components/dse/DseBandMix";
import { DseKpiRow } from "@/components/dse/DseKpiRow";
import { DseRecentCaptures } from "@/components/dse/DseRecentCaptures";
import { DseSearchBox } from "@/components/dse/DseSearchBox";
import { DseSuspectTrend } from "@/components/dse/DseSuspectTrend";
import { DseTopReasons } from "@/components/dse/DseTopReasons";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CardsSkeleton, Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useDseScorecard } from "@/lib/api/hooks";
import { isSparseDse } from "@/lib/dse/scorecard";

function ScorecardSkeleton() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-20 w-full" />
      <CardsSkeleton count={3} className="grid-cols-1 gap-4 sm:grid-cols-3" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-[280px] w-full" />
        <Skeleton className="h-[280px] w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function DsePageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const agentId = searchParams.get("agent") ?? undefined;

  const { data, isLoading, isError, refetch, isPlaceholderData } = useDseScorecard(agentId);

  function selectAgent(id: string) {
    router.push(`/dse?agent=${encodeURIComponent(id)}`);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="DSE scorecard"
        description="Look up a DSE (agent) by name or ID to see their capture-risk history."
      />

      <Card className="p-4">
        <DseSearchBox onSelect={selectAgent} autoFocus={!agentId} />
      </Card>

      {!agentId ? (
        <EmptyState
          icon={UserSearch}
          title="Search for a DSE"
          what="Enter a DSE's name or agent ID above to open their scorecard — capture volume, suspect rate, trend, and flagged captures."
          why="With ~266 DSEs and most having too few captures to rank fairly, a look-up-a-DSE scorecard is the honest way to see one person's history."
        />
      ) : isError ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
          <p className="text-body-sm text-text-secondary">Couldn&apos;t load this DSE&apos;s scorecard.</p>
          <Button variant="secondary" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
      ) : isLoading || !data || isPlaceholderData ? (
        // The only query variable is agentId, so placeholder data here is the
        // PREVIOUS agent's scorecard held while the new one loads — showing it
        // under the new URL would mislabel another DSE's name/numbers. Show the
        // skeleton across the identity switch instead.
        <ScorecardSkeleton />
      ) : (
        <div className="space-y-8">
          <Card className="p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="text-h1 text-text">{data.name}</h2>
                <p className="text-body-sm tabular-nums text-text-muted">{data.agent_id}</p>
              </div>
            </div>
            <div className="mt-3">
              <ChainBreadcrumb chain={data.chain} />
            </div>
          </Card>

          {isSparseDse(data.total) && (
            <p className="text-caption text-text-muted">
              This DSE has {data.total} scored {data.total === 1 ? "capture" : "captures"} in range — limited data;
              treat the rate and score below as directional, not conclusive.
            </p>
          )}

          <DseKpiRow total={data.total} suspectRate={data.suspect_rate} avgScore={data.avg_score} />

          <div className="grid gap-6 lg:grid-cols-2">
            <DseSuspectTrend trend={data.trend} />
            <DseBandMix bandDistribution={data.band_distribution} total={data.total} />
          </div>

          <DseTopReasons agentId={data.agent_id} reasons={data.top_reasons} />

          <DseRecentCaptures agentId={data.agent_id} recent={data.recent} />
        </div>
      )}
    </div>
  );
}

function DsePageFallback() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="DSE scorecard"
        description="Look up a DSE (agent) by name or ID to see their capture-risk history."
      />
      <Card className="p-4">
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <div className="h-11 w-full rounded-md border border-border bg-surface pl-9" />
        </div>
      </Card>
      <ScorecardSkeleton />
    </div>
  );
}

export default function DsePage() {
  return (
    <Suspense fallback={<DsePageFallback />}>
      <DsePageInner />
    </Suspense>
  );
}
