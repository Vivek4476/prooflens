import { ProofLensLogo } from "@/components/brand/ProofLensLogo";

/**
 * Host identity. ProofLens is the product that hosts every tenant workspace, so it sits at
 * the TOP of the shell (BRAND.md §9: "ProofLens mark at top"). The mark uses the ProofLens
 * accent (Focus Indigo) — never tenant crimson, which is confined to the bottom tenant chip.
 */
export function ProofLensMasthead() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent text-accent-fg">
        <ProofLensLogo className="h-5 w-5" />
      </span>
      <div className="min-w-0 leading-tight">
        <div className="text-body font-semibold text-text">ProofLens</div>
        <div className="text-caption text-text-muted">Capture Integrity</div>
      </div>
    </div>
  );
}
