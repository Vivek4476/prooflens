"use client";

import { useRouter } from "next/navigation";

import { ChartCard } from "@/components/ui/ChartCard";
import type { DseTopReason } from "@/lib/api/types";
import { formatCount, formatPct } from "@/lib/format";

const CARD_HEIGHT = 280;

function historyHref(agentId: string, reasonCode: string): string {
  const qs = new URLSearchParams();
  qs.set("rep_id", agentId);
  qs.set("reason", reasonCode);
  return `/history?${qs.toString()}`;
}

/** This DSE's top flag reasons — same bar-list visual language as the analytics
 *  TopFlagReasons card (neutral accent magnitude bar, rank, count + % of flags),
 *  scoped to a single agent_id and drilling into /history?rep_id=&reason=. */
export function DseTopReasons({ agentId, reasons }: { agentId: string; reasons: DseTopReason[] }) {
  const router = useRouter();
  const sorted = [...reasons].sort((a, b) => b.count - a.count);
  const total = sorted.reduce((sum, r) => sum + r.count, 0) || 1;
  const maxCount = Math.max(1, ...sorted.map((r) => r.count));

  return (
    <ChartCard title="Top flag reasons" subtitle="What is driving this DSE's Doubtful and Suspect verdicts." height={CARD_HEIGHT}>
      {sorted.length === 0 ? (
        <p className="grid h-full place-items-center text-center text-body-sm text-text-muted">
          No flags yet — every verdict for this DSE is Clear.
        </p>
      ) : (
        <ol className="flex h-full flex-col gap-1 overflow-y-auto pr-1">
          {sorted.map((r, i) => (
            <li key={r.reason_code} className="shrink-0">
              <button
                type="button"
                title={r.short_label}
                onClick={() => router.push(historyHref(agentId, r.reason_code))}
                className="group relative flex w-full items-center gap-3 overflow-hidden rounded-md px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
              >
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-y-1 left-0 rounded-[6px] bg-[color-mix(in_srgb,var(--accent)_11%,transparent)] transition-[width] duration-500 ease-out group-hover:bg-[color-mix(in_srgb,var(--accent)_18%,transparent)]"
                  style={{ width: `${Math.max((r.count / maxCount) * 100, 2)}%` }}
                />
                <span className="relative z-10 w-4 shrink-0 text-caption tabular-nums text-text-muted">{i + 1}</span>
                <span className="relative z-10 min-w-0 flex-1 truncate text-body-sm text-text">{r.short_label}</span>
                <span className="relative z-10 shrink-0 text-body-sm tabular-nums text-text-secondary">
                  {formatCount(r.count)} · {formatPct((r.count / total) * 100)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </ChartCard>
  );
}
