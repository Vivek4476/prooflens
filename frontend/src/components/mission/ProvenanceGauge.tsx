export function ProvenanceGauge({ pct }: { pct: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <b className="text-xl tabular-nums">{pct}%</b>
        <span className="text-[11px] text-text-muted">captures signed</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded bg-surface-3">
        <div className="h-full rounded bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-[11px] leading-snug text-text-muted">
        Signed on-device capture is the lead trust metric. Unsigned captures cannot score Clear on provenance alone.
      </p>
    </div>
  );
}
