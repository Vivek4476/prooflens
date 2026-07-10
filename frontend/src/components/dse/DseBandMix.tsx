import { Card, CardHeader } from "@/components/ui/Card";
import { formatCount, formatPct } from "@/lib/format";
import type { Band } from "@/lib/api/types";

const BAND_ORDER: Band[] = ["Clear", "Doubtful", "Suspect"];
const BAND_DOT: Record<Band, string> = {
  Clear: "bg-verdict-clear",
  Doubtful: "bg-verdict-doubtful",
  Suspect: "bg-verdict-suspect",
};

/** Simple horizontal band-mix summary — a lighter-weight sibling of BandMixChart's
 *  stacked-bar-over-time view, sized for a single DSE's overall totals rather than a
 *  per-bucket trend. */
export function DseBandMix({ bandDistribution, total }: { bandDistribution: Record<Band, number>; total: number }) {
  return (
    <Card>
      <CardHeader title="Band mix" subtitle="Share of Clear / Doubtful / Suspect across this DSE's scored captures." />
      <div className="p-4">
        {total === 0 ? (
          <p className="py-4 text-center text-body-sm text-text-muted">No scored captures yet.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-surface-2">
              {BAND_ORDER.map((band) => {
                const count = bandDistribution[band] ?? 0;
                const pct = total ? (count / total) * 100 : 0;
                if (pct <= 0) return null;
                return (
                  <span
                    key={band}
                    className={BAND_DOT[band]}
                    style={{ width: `${pct}%` }}
                    title={`${band}: ${formatCount(count)} (${formatPct(pct)})`}
                  />
                );
              })}
            </div>
            <ul className="flex flex-wrap gap-x-5 gap-y-2">
              {BAND_ORDER.map((band) => {
                const count = bandDistribution[band] ?? 0;
                const pct = total ? (count / total) * 100 : 0;
                return (
                  <li key={band} className="flex items-center gap-1.5 text-body-sm text-text-secondary">
                    <span aria-hidden className={`h-2 w-2 rounded-full ${BAND_DOT[band]}`} />
                    <span className="text-text">{band}</span>
                    <span className="tabular-nums text-text-muted">
                      {formatCount(count)} · {formatPct(pct)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}
