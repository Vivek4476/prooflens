"use client";

import { ImageOff, ScanSearch } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricCard } from "@/components/ui/MetricCard";
import { CardsSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { ResultsTable } from "@/components/history/ResultsTable";
import { useAnalytics, useResults } from "@/lib/api/hooks";
import { formatMs } from "@/lib/utils";

export default function DashboardPage() {
  const analytics = useAnalytics();
  const recent = useResults({ limit: 8 });

  const a = analytics.data;
  const isEmpty = analytics.isSuccess && a?.total === 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Is the system healthy, and is risk elevated today?"
        actions={
          <Link href="/analyze">
            <Button variant="primary">
              <ScanSearch size={16} />
              Analyze Photo
            </Button>
          </Link>
        }
      />

      {analytics.isError ? (
        <ApiError onRetry={() => analytics.refetch()} />
      ) : isEmpty ? (
        <EmptyState
          icon={ImageOff}
          title="No verdicts yet"
          what="Score a photo, or seed the demo, to populate today's KPIs and the recent-verdicts table."
          why="Run `npm run seed:demo` to push the sample images through the real scoring API."
          cta={{ label: "Analyze a Photo", href: "/analyze" }}
        />
      ) : (
        <>
          {analytics.isLoading || !a ? (
            <CardsSkeleton />
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
              <MetricCard label="Images today" value={a.images_today} />
              <MetricCard label="Suspect %" value={a.suspect_pct} suffix="%" accent sub="of all verdicts" />
              <MetricCard label="Avg score" value={a.avg_score} suffix="/100" />
              <MetricCard label="Avg processing" value={formatMs(a.avg_processing_ms)} />
              <MetricCard label="Duplicates caught" value={a.duplicates_caught} className="col-span-2 md:col-span-1" />
            </div>
          )}

          <Card>
            <CardHeader
              title="Recent verdicts"
              subtitle="Newest first — band first."
              action={
                <Link href="/history" className="text-caption font-medium text-text-secondary hover:text-text">
                  View all →
                </Link>
              }
            />
            {recent.isLoading || !recent.data ? (
              <TableSkeleton />
            ) : recent.data.items.length === 0 ? (
              <p className="px-5 py-8 text-center text-body-sm text-text-muted">No verdicts yet.</p>
            ) : (
              <ResultsTable items={recent.data.items} compact />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function ApiError({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <p className="text-body-sm text-text-secondary">
        Couldn&apos;t reach the scoring API. Is the backend running on the configured URL?
      </p>
      <Button variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    </Card>
  );
}
