"use client";

import { useState } from "react";

import { ChartCard } from "@/components/ui/ChartCard";
import type { TopReason } from "@/lib/api/types";
import {
  rankTopReasons,
  TOP_REASONS_LIMIT_LABELS,
  TOP_REASONS_LIMIT_OPTIONS,
  type TopReasonsLimit,
} from "@/lib/analytics/topFlagReasons";
import { formatCount, formatPct } from "@/lib/format";

/** Fixed height, matched to CaptureRiskTrend/BandMixChart's 280px `ChartCard` so the
 *  two-up analytics grid stays row-aligned. The list scrolls internally when the chosen
 *  row count exceeds the card — it never spills out of the box. */
const CARD_HEIGHT = 280;

/**
 * Row click is a future drill-down into filtered history (e.g. `/history?reason=blur`),
 * but no such URL-param contract exists on `/history` yet (confirmed: it only supports a
 * free-text `q` search client-side). Rather than invent a route the backend/history page
 * doesn't honor, this is a deferred no-op — swap in real navigation once the contract
 * exists (see Task 6's carried-forward note on the same gap for InsightsPanel).
 */
function onRowSelect(_reasonCode: string) {
  // Intentionally deferred — no /history?reason= contract exists yet.
}

export function TopFlagReasons({ topReasons }: { topReasons: TopReason[] }) {
  const [limit, setLimit] = useState<TopReasonsLimit>(5);
  const rows = rankTopReasons(topReasons, limit);
  const hasMoreThanDefault = rankTopReasons(topReasons, "all").length > 5;

  // The row-count control lives in the card header, opposite the title — not floating
  // above the list. Only shown when there is actually something to expand.
  const selector = (
    <label className="flex shrink-0 items-center gap-2 text-caption text-text-muted">
      Show
      <select
        value={String(limit)}
        onChange={(e) => {
          const v = e.target.value;
          setLimit(v === "all" ? "all" : (Number(v) as TopReasonsLimit));
        }}
        disabled={!hasMoreThanDefault}
        aria-label="Number of flag reasons to show"
        className="h-8 rounded-md border border-border bg-surface px-2 text-caption text-text disabled:opacity-50"
      >
        {TOP_REASONS_LIMIT_OPTIONS.map((opt) => (
          <option key={String(opt)} value={String(opt)}>
            {TOP_REASONS_LIMIT_LABELS[opt]}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <ChartCard
      title="Top flag reasons"
      subtitle="What is actually driving Doubtful and Suspect verdicts."
      height={CARD_HEIGHT}
      action={rows.length > 0 ? selector : undefined}
    >
      {rows.length === 0 ? (
        <p className="grid h-full place-items-center text-center text-body-sm text-text-muted">
          No flags yet — every verdict is Clear.
        </p>
      ) : (
        <ol className="flex h-full flex-col gap-1 overflow-y-auto pr-1">
          {rows.map((r) => (
            <li key={r.reason_code} className="shrink-0">
              <button
                type="button"
                title={r.reason}
                onClick={() => onRowSelect(r.reason_code)}
                className="group relative flex w-full items-center gap-3 overflow-hidden rounded-md px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
              >
                {/* Magnitude bar — width relative to the top reason. Soft accent wash (the
                    same data colour as the trend line), never a verdict hue. */}
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-y-1 left-0 rounded-[6px] bg-[color-mix(in_srgb,var(--accent)_11%,transparent)] transition-[width] duration-500 ease-out group-hover:bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]"
                  style={{ width: `${Math.max(r.barPct, 2)}%` }}
                />
                <span className="relative z-10 w-4 shrink-0 text-caption tabular-nums text-text-muted">{r.rank}</span>
                <span className="relative z-10 min-w-0 flex-1 truncate text-body-sm text-text">{r.short_label}</span>
                <span className="relative z-10 shrink-0 text-body-sm tabular-nums text-text-secondary">
                  {formatCount(r.count)} · {formatPct(r.pctOfFlags)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </ChartCard>
  );
}
