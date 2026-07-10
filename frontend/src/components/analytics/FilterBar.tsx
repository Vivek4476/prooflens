"use client";

import type { Bucket, PeriodBounds } from "@/lib/api/types";
import { RANGE_PRESET_LABELS, type RangePreset } from "@/lib/analytics/dateRanges";
import { formatDateRange } from "@/lib/format";
import { cn } from "@/lib/utils";

const RANGE_PRESETS: RangePreset[] = ["7d", "30d", "90d", "month", "custom"];
const BUCKETS: Bucket[] = ["daily", "weekly", "monthly"];
const BUCKET_LABELS: Record<Bucket, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
};

/** Shared pill styling for both segmented groups: selected = neutral fill
 *  (`--surface-2`/`--text`), never accent — accent is reserved for the
 *  keyboard focus ring (global `:focus-visible`), keeping accent coverage
 *  well under the ≤10% brand ceiling. */
function segmentClass(active: boolean) {
  return cn(
    "min-h-[44px] rounded px-2.5 py-1 text-caption font-medium transition-colors sm:min-h-0",
    active ? "bg-surface-2 text-text" : "text-text-muted hover:text-text-secondary",
  );
}

export interface FilterBarProps {
  preset: RangePreset;
  bucket: Bucket;
  from?: string;
  to?: string;
  onPresetChange: (preset: RangePreset) => void;
  onCustomRangeChange: (from: string, to: string) => void;
  onBucketChange: (bucket: Bucket) => void;
  /** Backend-resolved period bounds — the caption is derived from these, not
   *  recomputed client-side from the preset, since the server's resolution
   *  is the source of truth (e.g. "month" semantics may differ subtly). */
  period?: PeriodBounds;
  previousPeriod?: PeriodBounds;
}

/** The global analytics filter bar: date-range + aggregation, plus the
 *  comparison-window caption. Rendered directly under the page H1. */
export function FilterBar({
  preset,
  bucket,
  from,
  to,
  onPresetChange,
  onCustomRangeChange,
  onBucketChange,
  period,
  previousPeriod,
}: FilterBarProps) {
  const showCustomInputs = preset === "custom";

  return (
    <div className="flex flex-col gap-2">
      {/* Interactive range/bucket controls — hidden in print; the caption below keeps the
          printed report's window unambiguous. */}
      <div className="no-print flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap items-center gap-1 rounded-md border border-border bg-surface p-1">
          {RANGE_PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={preset === p}
              onClick={() => onPresetChange(p)}
              className={segmentClass(preset === p)}
            >
              {RANGE_PRESET_LABELS[p]}
            </button>
          ))}
        </div>

        {showCustomInputs && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={from ?? ""}
              onChange={(e) => onCustomRangeChange(e.target.value, to ?? e.target.value)}
              className="h-9 min-h-[44px] rounded-md border border-border bg-surface px-3 text-body-sm text-text sm:min-h-0"
              aria-label="Custom range start date"
            />
            <span className="text-text-muted">–</span>
            <input
              type="date"
              value={to ?? ""}
              onChange={(e) => onCustomRangeChange(from ?? e.target.value, e.target.value)}
              className="h-9 min-h-[44px] rounded-md border border-border bg-surface px-3 text-body-sm text-text sm:min-h-0"
              aria-label="Custom range end date"
            />
          </div>
        )}

        <div className="flex items-center gap-1 rounded-md border border-border bg-surface p-1 sm:ml-auto">
          {BUCKETS.map((b) => (
            <button
              key={b}
              type="button"
              aria-pressed={bucket === b}
              onClick={() => onBucketChange(b)}
              className={segmentClass(bucket === b)}
            >
              {BUCKET_LABELS[b]}
            </button>
          ))}
        </div>
      </div>

      {period && previousPeriod && (
        <span className="text-caption text-text-muted">
          {formatDateRange(period.from, period.to)} · compared with{" "}
          {formatDateRange(previousPeriod.from, previousPeriod.to)}
        </span>
      )}
    </div>
  );
}
