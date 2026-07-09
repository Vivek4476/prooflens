import { TenantLogo } from "@/components/brand/TenantLogo";

/**
 * Tenant identity — the customer whose workspace this is. Per BRAND.md §9 the tenant's brand
 * lives ONLY in this bottom chip, never as the app's hero. Uses the tenant's own logo artwork
 * (its native crimson is allowed here — it's the tenant's mark, not interface chrome).
 */
export function TenantChip() {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-caption text-text-muted">Workspace</span>
      <TenantLogo size="sm" />
    </div>
  );
}
