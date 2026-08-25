import type { AnalyticsSummary } from "@/lib/api/types";

const SEG = [
  { key: "Clear", cls: "bg-verdict-clear" },
  { key: "Doubtful", cls: "bg-verdict-doubtful" },
  { key: "Suspect", cls: "bg-verdict-suspect" },
  { key: "Unassessed", cls: "bg-verdict-unassessed" },
] as const;

export function DecisionMixBar({ dist }: { dist: AnalyticsSummary["band_distribution"] | undefined }) {
  const total = SEG.reduce((s, x) => s + (dist?.[x.key] ?? 0), 0) || 1;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-md">
        {SEG.map((s) => (
          <div key={s.key} className={s.cls} style={{ width: `${((dist?.[s.key] ?? 0) / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-2">
        {SEG.map((s) => (
          <div key={s.key} className="flex items-center gap-2 text-xs">
            <span className={`h-2.5 w-2.5 rounded-sm ${s.cls}`} />
            {s.key}
            <span className="ml-auto tabular-nums font-semibold">{dist?.[s.key] ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
