import { TenantLogo } from "@/components/brand/TenantLogo";

/**
 * ABSLI-first identity for the app chrome. The tenant (Aditya Birla Sun Life
 * Insurance) is the primary brand; ProofLens is credited as the engine below
 * (see <PoweredByProofLens>).
 */
export function AbsliMasthead() {
  return (
    <div className="flex flex-col gap-2.5">
      <TenantLogo size="md" />
      <div className="leading-tight">
        <p className="text-body-sm font-semibold text-text">Aditya Birla Sun Life Insurance</p>
        <p className="text-caption text-text-muted">Capture Integrity workspace</p>
      </div>
    </div>
  );
}
