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
      scope="col"
      aria-sort={
        k ? (active ? (sortDir === "asc" ? "ascending" : "descending") : "none") : undefined
      }
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
  const open = (id: string) => router.push(`/verdict/${id}`);
  return (
    <>
      {/* Mobile: stacked cards below the sm breakpoint */}
      <ul className="flex flex-col gap-3 sm:hidden">
        {items.map((r) => (
          <li key={r.id}>
            <div
              onClick={() => open(r.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") open(r.id);
              }}
              tabIndex={0}
              role="link"
              aria-label={`Open verdict ${r.band}, score ${Math.round(r.score)}`}
              className="flex cursor-pointer flex-col gap-3 rounded-[var(--radius)] border border-border p-4 hover:bg-surface-2/60 focus-visible:bg-surface-2"
            >
              <div className="flex items-center justify-between gap-2">
                <VerdictBadge band={r.band} size="sm" />
                <span className="text-body font-semibold tabular-nums text-text">
                  {Math.round(r.score)}
                </span>
              </div>
              <p className="text-body-sm text-text-secondary">{r.reason}</p>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-caption">
                {!compact && (
                  <div className="flex flex-col gap-0.5">
                    <dt className="uppercase tracking-wide text-text-muted">Rep</dt>
                    <dd className="tabular-nums text-text-secondary">{r.rep_id ?? "—"}</dd>
                  </div>
                )}
                {!compact && (
                  <div className="flex flex-col gap-0.5">
                    <dt className="uppercase tracking-wide text-text-muted">Opportunity</dt>
                    <dd className="tabular-nums text-text-secondary">{r.opportunity_id ?? "—"}</dd>
                  </div>
                )}
                {!compact && (
                  <div className="flex flex-col gap-0.5">
                    <dt className="uppercase tracking-wide text-text-muted">Source</dt>
                    <dd>
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-caption text-text-muted">
                        {r.source}
                      </span>
                    </dd>
                  </div>
                )}
                <div className="flex flex-col gap-0.5">
                  <dt className="uppercase tracking-wide text-text-muted">Processing</dt>
                  <dd className="tabular-nums text-text-secondary">{formatMs(r.processing_ms)}</dd>
                </div>
                <div className="flex flex-col gap-0.5">
                  <dt className="uppercase tracking-wide text-text-muted">Time</dt>
                  <dd className="text-text-secondary">{formatDateTime(r.created_at)}</dd>
                </div>
              </dl>
            </div>
          </li>
        ))}
      </ul>

      {/* Desktop: the full table at sm and up */}
      <div className="hidden overflow-x-auto sm:block">
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
              onClick={() => open(r.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") open(r.id);
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
    </>
  );
}
