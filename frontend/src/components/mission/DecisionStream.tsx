"use client";

import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { formatRelative } from "@/lib/utils";
import type { ResultItem } from "@/lib/api/types";

export function DecisionStream({
  items,
  newIds,
  onSelect,
}: {
  items: ResultItem[];
  newIds: Set<string>;
  onSelect: (r: ResultItem) => void;
}) {
  return (
    <div className="flex flex-col">
      {items.map((r) => {
        const written = r.band !== "Unassessed";
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r)}
            className={`grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-border px-4 py-2.5 text-left hover:bg-surface-2 ${newIds.has(r.id) ? "motion-safe:animate-[fadein_.45s_ease]" : ""}`}
          >
            <div>
              <div className="text-[13px] font-semibold">{r.rep_id ?? r.opportunity_id}</div>
              <div className="font-mono text-[10px] text-text-muted">{r.opportunity_id}</div>
            </div>
            <VerdictBadge band={r.band} size="sm" />
            <div className="text-right">
              <div className="text-[11px] text-text-muted">{written ? "✓ LSQ" : "◷ retry"}</div>
              <div className="text-[10px] tabular-nums text-text-muted">{formatRelative(r.created_at)}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
