import Link from "next/link";

import type { SystemHealth } from "@/lib/api/types";
import { formatPct } from "@/lib/format";

/**
 * Two quiet system-health signals under the KPI row (Pain 9), so a vision-backend outage
 * reads as a system issue rather than a fraud spike: the fail-open degradation rate and the
 * median time-to-score. A "How scores work" methodology link sits opposite.
 */
export function SystemHealthLine({ health }: { health: SystemHealth }) {
  const { scored_without_content_pct: pct, median_processing_ms: ms } = health;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-1 text-caption text-text-muted">
      <span>
        <span className="tabular-nums text-text-secondary">{pct == null ? "—" : formatPct(pct)}</span> scored without
        content check
      </span>
      <span aria-hidden className="text-border-strong">
        ·
      </span>
      <span>
        median time-to-score{" "}
        <span className="tabular-nums text-text-secondary">{ms == null ? "—" : `${Math.round(ms)} ms`}</span>
      </span>
      <Link href="/methodology" className="ml-auto font-medium text-accent hover:underline">
        How scores work →
      </Link>
    </div>
  );
}
