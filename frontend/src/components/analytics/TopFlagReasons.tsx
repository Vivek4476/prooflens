"use client";

import { useState } from "react";

import { ChartCard } from "@/components/ui/ChartCard";
import type { TopReason } from "@/lib/api/types";
import {
  rankTopReasons,
  shouldScroll,
  TOP_REASONS_LIMIT_LABELS,
  TOP_REASONS_LIMIT_OPTIONS,
  type TopReasonsLimit,
} from "@/lib/analytics/topFlagReasons";
import { formatCount, formatPct } from "@/lib/format";

/** Fixed height, matched to CaptureRiskTrend/BandMixChart's 280px `ChartCard` so the
 *  two-up analytics grid stays row-aligned. */
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
  const scrolling = shouldScroll(limit);

  return (
    <ChartCard title="Top flag reasons" subtitle="What is actually driving Doubtful and Suspect verdicts." height={CARD_HEIGHT}>
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 items-center justify-end pb-3">
          <label className="flex items-center gap-2 text-caption text-text-muted">
            Show
            <select
              value={String(limit)}
              onChange={(e) => {
                const v = e.target.value;
                setLimit(v === "all" ? "all" : (Number(v) as TopReasonsLimit));
              }}
              disabled={!hasMoreThanDefault}
              aria-label="Number of flag reasons to show"
              className="h-8 min-h-[44px] rounded-md border border-border bg-surface px-2 text-caption text-text disabled:opacity-50 sm:min-h-0"
            >
              {TOP_REASONS_LIMIT_OPTIONS.map((opt) => (
                <option key={String(opt)} value={String(opt)}>
                  {TOP_REASONS_LIMIT_LABELS[opt]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {rows.length === 0 ? (
          <p className="grid flex-1 place-items-center text-center text-body-sm text-text-muted">
            No flags yet — every verdict is Clear.
          </p>
        ) : (
          <ol className={scrolling ? "min-h-0 flex-1 space-y-3 overflow-y-auto pr-1" : "min-h-0 flex-1 space-y-3"}>
            {rows.map((r) => (
              <li key={r.reason_code}>
                <button
                  type="button"
                  title={r.reason}
                  onClick={() => onRowSelect(r.reason_code)}
                  className="w-full space-y-1.5 rounded-lg p-1.5 text-left transition-colors hover:bg-surface-2"
                >
                  <div className="flex items-baseline justify-between gap-3 text-body-sm">
                    <span className="flex min-w-0 items-center gap-2 text-text">
                      <span className="w-4 shrink-0 text-caption tabular-nums text-text-muted">{r.rank}</span>
                      <span className="truncate">{r.short_label}</span>
                    </span>
                    <span className="shrink-0 tabular-nums text-text-secondary">
                      {formatCount(r.count)} · {formatPct(r.pctOfFlags)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
                    <div className="h-full rounded-full bg-text-muted" style={{ width: `${r.barPct}%` }} />
                  </div>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </ChartCard>
  );
}
