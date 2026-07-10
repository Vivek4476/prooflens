import { TenantLogo } from "@/components/brand/TenantLogo";

/**
 * Tenant identity — the customer whose workspace this is. Per BRAND.md §9 the tenant's brand
 * lives ONLY in this bottom chip, never as the app's hero. The logo gets clear space in a
 * clean white card so it reads clearly in both themes.
 */
export function TenantChip() {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-caption text-text-muted">Workspace</span>
      <TenantLogo size="md" />
    </div>
  );
}
