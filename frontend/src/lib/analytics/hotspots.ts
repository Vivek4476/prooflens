import type { AnalyticsGroup } from "@/lib/api/types";

/** The backend's catch-all node for captures whose rep isn't in the hierarchy. */
export const UNMAPPED_NODE = "Unmapped";

export interface HotspotRanking {
  /** Team-like nodes with enough volume, sorted by suspect rate desc, capped to maxRows. */
  ranked: AnalyticsGroup[];
  /** Count of team nodes excluded for being below the volume threshold. */
  belowCount: number;
  /** Scored captures not attributable to any node (the "Unmapped" bucket). */
  unmappedTotal: number;
  /** Largest suspect rate among the ranked rows, floored so bar widths never divide by 0. */
  maxRate: number;
}

/**
 * Rank team-like nodes by suspect rate for the "where to look" hotspot list.
 *
 * Two honesty guards:
 * - **"Unmapped" is never rankable.** It's captures whose rep isn't in the hierarchy, not a
 *   team an operator can act on. It's removed from the ranking and reported separately as
 *   `unmappedTotal`, so it can't masquerade as the worst "zone".
 * - **Small samples don't rank.** Nodes below `minTotal` scored are excluded and counted in
 *   `belowCount`, so a branch with 1 Suspect out of 2 never shows as a "50% hotspot".
 */
export function rankHotspots(
  groups: AnalyticsGroup[],
  { minTotal, maxRows }: { minTotal: number; maxRows: number },
): HotspotRanking {
  const teams = groups.filter((g) => g.node !== UNMAPPED_NODE);
  const unmappedTotal = groups.find((g) => g.node === UNMAPPED_NODE)?.total ?? 0;
  const eligible = teams.filter((g) => g.total >= minTotal);
  const ranked = [...eligible].sort((a, b) => b.suspect_rate - a.suspect_rate).slice(0, maxRows);
  const maxRate = Math.max(0.0001, ...ranked.map((g) => g.suspect_rate));
  return { ranked, belowCount: teams.length - eligible.length, unmappedTotal, maxRate };
}
