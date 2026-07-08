"use client";

import { History as HistoryIcon, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ResultsTable, type SortKey } from "@/components/history/ResultsTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { useResults } from "@/lib/api/hooks";
import type { Band } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PAGE = 12;
const BANDS: (Band | "All")[] = ["All", "Clear", "Doubtful", "Suspect"];
const BAND_ORDER: Record<Band, number> = { Suspect: 0, Doubtful: 1, Clear: 2 };

function HistoryInner() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [band, setBand] = useState<Band | "All">("All");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  // Demo scale: fetch a page and do search/sort/filter/paginate client-side.
  // For very large stores this would move server-side (see BACKEND_REQUIREMENTS).
  const { data, isLoading, isError, refetch } = useResults({ limit: 200 });

  const rows = useMemo(() => {
    let items = data?.items ?? [];
    if (band !== "All") items = items.filter((r) => r.band === band);
    const needle = q.trim().toLowerCase();
    if (needle) {
      items = items.filter(
        (r) =>
          (r.rep_id ?? "").toLowerCase().includes(needle) ||
          (r.opportunity_id ?? "").toLowerCase().includes(needle) ||
          r.reason.toLowerCase().includes(needle),
      );
    }
    const dir = sortDir === "asc" ? 1 : -1;
    items = [...items].sort((a, b) => {
      if (sortKey === "band") return (BAND_ORDER[a.band] - BAND_ORDER[b.band]) * dir;
      if (sortKey === "score") return (a.score - b.score) * dir;
      if (sortKey === "processing_ms") return (a.processing_ms - b.processing_ms) * dir;
      return (a.created_at < b.created_at ? -1 : 1) * dir;
    });
    return items;
  }, [data, band, q, sortKey, sortDir]);

  const pageRows = rows.slice(page * PAGE, page * PAGE + PAGE);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE));

  function onSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir("desc");
    }
  }

  if (isError) {
    return (
      <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <p className="text-body-sm text-text-secondary">Couldn&apos;t load history from the API.</p>
        <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Upload history"
        description="Every scored image, newest first. No thumbnails — the backend never stores images. Select a row to open its full verdict."
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(0);
            }}
            placeholder="Search rep, opportunity, or reason…"
            className="h-9 w-full sm:w-72 rounded-md border border-border bg-surface pl-8 pr-3 text-body-sm text-text placeholder:text-text-muted"
          />
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border bg-surface p-1">
          {BANDS.map((b) => (
            <button
              key={b}
              onClick={() => {
                setBand(b);
                setPage(0);
              }}
              className={cn(
                "flex h-11 sm:h-auto items-center rounded px-3 sm:px-2.5 py-1 text-caption font-medium transition-colors",
                band === b ? "bg-surface-2 text-text" : "text-text-muted hover:text-text-secondary",
              )}
            >
              {b}
            </button>
          ))}
        </div>
        <span className="ml-auto text-caption text-text-muted">
          {rows.length} {rows.length === 1 ? "result" : "results"}
        </span>
      </div>

      <Card>
        {isLoading || !data ? (
          <TableSkeleton rows={PAGE} />
        ) : rows.length === 0 ? (
          <div className="p-2">
            <EmptyState
              icon={HistoryIcon}
              title="No matching uploads"
              what="No verdicts match your search and filters."
              cta={{ label: "Analyze a Photo", href: "/analyze" }}
            />
          </div>
        ) : (
          <>
            <ResultsTable items={pageRows} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            {pageCount > 1 && (
              <div className="flex items-center justify-between border-t border-border px-4 py-3">
                <span className="text-caption text-text-muted">
                  Page {page + 1} of {pageCount}
                </span>
                <div className="flex gap-2">
                  <Button variant="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={page >= pageCount - 1}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <Suspense fallback={<TableSkeleton rows={PAGE} />}>
      <HistoryInner />
    </Suspense>
  );
}
