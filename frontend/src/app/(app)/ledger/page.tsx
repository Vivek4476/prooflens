"use client";

import { useState } from "react";
import { FileSearch } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ResultsTable } from "@/components/history/ResultsTable";
import { useResults } from "@/lib/api/hooks";
import type { Band } from "@/lib/api/types";

const BANDS: (Band | "all")[] = ["all", "Suspect", "Doubtful", "Clear", "Unassessed"];

export default function LedgerPage() {
  const [band, setBand] = useState<Band | "all">("all");
  const q = useResults({ limit: 100, band: band === "all" ? undefined : band });
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Ledger"
        description="Every automated decision, immutable and searchable. Select a row to open its full record."
      />

      <div className="flex gap-2">
        {BANDS.map((b) => (
          <button
            key={b}
            onClick={() => setBand(b)}
            className={`rounded-full border px-3 py-1 text-xs ${band === b ? "border-text bg-text text-canvas" : "border-border text-text-secondary hover:border-border-strong"}`}
          >
            {b === "all" ? "All" : b}
          </button>
        ))}
      </div>

      <Card>
        {q.isLoading ? (
          <TableSkeleton rows={8} />
        ) : items.length === 0 ? (
          <EmptyState icon={FileSearch} title="No decisions" what="No decisions match this filter yet." />
        ) : (
          <ResultsTable items={items} />
        )}
      </Card>
    </div>
  );
}
