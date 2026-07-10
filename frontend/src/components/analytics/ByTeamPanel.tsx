"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ChartCard } from "@/components/ui/ChartCard";
import { useAnalytics } from "@/lib/api/hooks";
import type { AnalyticsParams, GroupBy } from "@/lib/api/types";
import { rankHotspots } from "@/lib/analytics/hotspots";
import { formatCount, formatPct } from "@/lib/format";

/** Matched to the reasons/chart cards so the two-up grid stays row-aligned. */
const CARD_HEIGHT = 280;

/** Minimum scored volume before a node's suspect rate is trustworthy enough to rank —
 *  mirrors the small-sample discipline the KPI deltas use. A branch with 2 captures and
 *  1 Suspect is not a "50% hotspot". */
const MIN_TOTAL_FOR_RATE = 20;

/** How many hotspots the fixed-height card shows before the list scrolls. */
const MAX_ROWS = 8;

const DIMENSIONS: { value: GroupBy; label: string }[] = [
  { value: "branch", label: "Branch" },
  { value: "city", label: "City" },
  { value: "sm", label: "Sales manager" },
  { value: "rsm", label: "Regional manager" },
  { value: "srsm", label: "Senior RSM" },
  { value: "zone", label: "Zone" },
  { value: "agent", label: "DSE" },
];

export function ByTeamPanel({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const router = useRouter();
  const [dimension, setDimension] = useState<GroupBy>("branch");

  /**
   * Row click would ideally drill down into filtered history (e.g. `/history?branch=…`),
   * but /v1/results has no team/branch/node filter — only band, reason, rep_id, from, to
   * (see api/scoring.py's list_results). Unlike TopFlagReasons and the suspect-rate/
   * dominant-reason/duplicates insights (which now navigate to /history?band=…&reason=…,
   * filters the backend genuinely honours), a team drill-down here would build a URL
   * /history can't apply — deferred no-op until /v1/results grows a node filter.
   *
   * The "DSE" dimension is the one exception: group_by=agent's rows ARE individual
   * DSEs (node = agent_id), so a row genuinely identifies a single scorecard — it
   * navigates to /dse?agent=<id> rather than deferring.
   */
  function onRowSelect(node: string) {
    if (dimension === "agent") router.push(`/dse?agent=${encodeURIComponent(node)}`);
  }

  // Own query, keyed on its own dimension — changing "By branch → By city" refetches only
  // this panel, not the whole page. Memoized so useAnalytics's 300ms debounce can settle.
  const params: AnalyticsParams = useMemo(
    () => ({ start_date: startDate, end_date: endDate, bucket: "daily", group_by: dimension }),
    [startDate, endDate, dimension],
  );
  const enabled = Boolean(startDate && endDate);
  const { data, isLoading, isError, isPlaceholderData } = useAnalytics(params, enabled);

  const label = DIMENSIONS.find((d) => d.value === dimension)?.label ?? "Branch";
  const labelLower = label.toLowerCase();

  // Ranking + honesty guards (exclude Unmapped, drop small samples) live in a tested
  // pure module; see hotspots.ts.
  const groups = data?.groups ?? [];
  const { ranked, belowCount, unmappedTotal, maxRate } = useMemo(
    () => rankHotspots(groups, { minTotal: MIN_TOTAL_FOR_RATE, maxRows: MAX_ROWS }),
    [groups],
  );

  const notParts: string[] = [];
  if (belowCount > 0) notParts.push(`${formatCount(belowCount)} below ${MIN_TOTAL_FOR_RATE} scored`);
  if (unmappedTotal > 0) notParts.push(`${formatCount(unmappedTotal)} unmapped`);
  const notRankedNote = notParts.length > 0 ? `Not ranked: ${notParts.join(", ")}.` : null;

  const selector = (
    <label className="flex shrink-0 items-center gap-2 text-caption text-text-muted">
      By
      <select
        value={dimension}
        onChange={(e) => setDimension(e.target.value as GroupBy)}
        aria-label="Group teams by"
        className="h-8 rounded-md border border-border bg-surface px-2 text-caption text-text"
      >
        {DIMENSIONS.map((d) => (
          <option key={d.value} value={d.value}>
            {d.label}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <ChartCard
      title="Where to look"
      subtitle={`Highest suspect rate by ${labelLower}.`}
      height={CARD_HEIGHT}
      action={selector}
    >
      {isError ? (
        <p className="grid h-full place-items-center text-center text-body-sm text-text-muted">
          Couldn&apos;t load the team breakdown.
        </p>
      ) : isLoading && !data ? (
        <p className="grid h-full place-items-center text-body-sm text-text-muted">Loading…</p>
      ) : ranked.length === 0 ? (
        <p className="grid h-full place-items-center px-4 text-center text-body-sm text-text-muted">
          {`No ${labelLower} has ${MIN_TOTAL_FOR_RATE}+ scored captures yet — not enough volume to rank a hotspot.`}
        </p>
      ) : (
        <div className={`flex h-full flex-col transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
          <ol className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-1">
            {ranked.map((g, i) => (
              <li key={g.node} className="shrink-0">
                <button
                  type="button"
                  title={`${g.node} — ${formatCount(g.suspect)} of ${formatCount(g.total)} scored are Suspect`}
                  onClick={() => onRowSelect(g.node)}
                  className="group relative flex w-full items-center gap-3 overflow-hidden rounded-md px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
                >
                  {/* Magnitude bar — width relative to the worst node's suspect rate. This IS
                      a suspect-rate metric, so a soft Suspect wash is meaning, not decoration;
                      the % is always shown alongside so it never relies on colour. */}
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-1 left-0 rounded-[6px] bg-[color-mix(in_srgb,var(--verdict-suspect)_14%,transparent)] transition-[width] duration-500 ease-out group-hover:bg-[color-mix(in_srgb,var(--verdict-suspect)_22%,transparent)]"
                    style={{ width: `${Math.max((g.suspect_rate / maxRate) * 100, 3)}%` }}
                  />
                  <span className="relative z-10 w-4 shrink-0 text-caption tabular-nums text-text-muted">{i + 1}</span>
                  <span className="relative z-10 min-w-0 flex-1 truncate text-body-sm text-text">{g.node}</span>
                  <span className="relative z-10 shrink-0 text-body-sm tabular-nums text-text-secondary">
                    {formatPct(g.suspect_rate * 100)} · {formatCount(g.total)} scored
                  </span>
                </button>
              </li>
            ))}
          </ol>
          {notRankedNote && (
            <p className="shrink-0 pt-2 text-caption text-text-muted">{notRankedNote}</p>
          )}
        </div>
      )}
    </ChartCard>
  );
}
