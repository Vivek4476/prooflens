"use client";

import { X } from "lucide-react";

import type { Bucket } from "@/lib/api/types";
import { availableBuckets, BUCKET_LABEL, type CardAggChoice } from "@/lib/analytics/cardOverride";

/** Compact card-header control (Pain 8): "Follow page" (default) + Daily/Weekly/
 *  Monthly, gated to the data span. Rendered in a ChartCard's `action` slot. */
export function CardAggSelect({
  choice,
  onChange,
  from,
  to,
  label,
}: {
  choice: CardAggChoice;
  onChange: (next: CardAggChoice) => void;
  from?: string;
  to?: string;
  /** Accessible name, e.g. "Capture-risk trend aggregation". */
  label: string;
}) {
  const gate = availableBuckets(from, to);
  return (
    <select
      value={choice}
      onChange={(e) => onChange(e.target.value as CardAggChoice)}
      aria-label={label}
      className="h-8 shrink-0 rounded-md border border-border bg-surface px-2 text-caption text-text"
    >
      <option value="page">Follow page</option>
      <option value="daily">Daily</option>
      <option value="weekly" disabled={!gate.weekly}>
        Weekly{!gate.weekly ? " (needs 14+ days)" : ""}
      </option>
      <option value="monthly" disabled={!gate.monthly}>
        Monthly{!gate.monthly ? " (needs 60+ days)" : ""}
      </option>
    </select>
  );
}

/** "Viewing: Weekly · differs from page" chip with a resync ✕ — shown only when
 *  the card's own bucket genuinely differs from the page's global bucket. */
export function CardAggChip({ bucket, onResync }: { bucket: Bucket; onResync: () => void }) {
  return (
    <div className="flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 text-caption text-text-secondary">
      <span>
        Viewing: {BUCKET_LABEL[bucket]} · differs from page
      </span>
      <button
        type="button"
        onClick={onResync}
        aria-label="Resync to page aggregation"
        className="grid h-4 w-4 shrink-0 place-items-center rounded-sm text-text-muted transition-colors hover:bg-surface hover:text-text"
      >
        <X aria-hidden className="h-3 w-3" />
      </button>
    </div>
  );
}
