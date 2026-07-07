import { Aperture } from "lucide-react";

/** ProofLens as the engine credit under the ABSLI-first brand. */
export function PoweredByProofLens() {
  return (
    <div className="flex items-center gap-2">
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-brand-crimson text-white">
        <Aperture size={12} strokeWidth={2.5} />
      </span>
      <span className="text-caption text-text-muted">
        Powered by <span className="font-medium text-text-secondary">ProofLens</span> · Capture Integrity
      </span>
    </div>
  );
}
