"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";

import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import type { ResultItem } from "@/lib/api/types";
import { cn, formatDateTime, formatMs } from "@/lib/utils";

export type SortKey = "created_at" | "band" | "score" | "processing_ms";

function Th({
  label,
  k,
  sortKey,
  sortDir,
  onSort,
  align = "left",
}: {
  label: string;
  k?: SortKey;
  sortKey?: SortKey;
  sortDir?: "asc" | "desc";
  onSort?: (k: SortKey) => void;
  align?: "left" | "right";
}) {
  const active = k && sortKey === k;
  return (
    <th
      className={cn(
        "whitespace-nowrap px-4 py-2.5 text-caption font-medium uppercase tracking-wide text-text-muted",
        align === "right" ? "text-right" : "text-left",
      )}
    >
      {k && onSort ? (
        <button
          onClick={() => onSort(k)}
          className={cn(
            "inline-flex items-center gap-1 hover:text-text-secondary",
            align === "right" && "flex-row-reverse",
            active && "text-text-secondary",
          )}
        >
          {label}
          {active &&
            (sortDir === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
        </button>
      ) : (
        label
      )}
    </th>
  );
}

export function ResultsTable({
  items,
  compact = false,
  sortKey,
  sortDir,
  onSort,
}: {
  items: ResultItem[];
  compact?: boolean;
  sortKey?: SortKey;
  sortDir?: "asc" | "desc";
  onSort?: (k: SortKey) => void;
}) {
  const router = useRouter();
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body-sm">
        <thead>
          <tr className="border-b border-border">
            <Th label="Verdict" k="band" sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            <Th label="Score" k="score" sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <Th label="Reason" />
            {!compact && <Th label="Rep" />}
            {!compact && <Th label="Opportunity" />}
            {!compact && <Th label="Source" />}
            <Th label="Processing" k="processing_ms" sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <Th label="Time" k="created_at" sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr
              key={r.id}
              onClick={() => router.push(`/verdict/${r.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter") router.push(`/verdict/${r.id}`);
              }}
              tabIndex={0}
              role="link"
              aria-label={`Open verdict ${r.band}, score ${Math.round(r.score)}`}
              className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-2/60 focus-visible:bg-surface-2"
            >
              <td className="px-4 py-3">
                <VerdictBadge band={r.band} size="sm" />
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">{Math.round(r.score)}</td>
              <td className="px-4 py-3 text-text-secondary">{r.reason}</td>
              {!compact && <td className="px-4 py-3 tabular-nums text-text-secondary">{r.rep_id ?? "—"}</td>}
              {!compact && (
                <td className="px-4 py-3 tabular-nums text-text-secondary">{r.opportunity_id ?? "—"}</td>
              )}
              {!compact && (
                <td className="px-4 py-3">
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 text-caption text-text-muted">
                    {r.source}
                  </span>
                </td>
              )}
              <td className="px-4 py-3 text-right tabular-nums text-text-muted">{formatMs(r.processing_ms)}</td>
              <td className="whitespace-nowrap px-4 py-3 text-right text-text-muted">
                {formatDateTime(r.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
