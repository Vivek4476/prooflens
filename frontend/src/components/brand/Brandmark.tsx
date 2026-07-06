import { Aperture } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * ProofLens PRODUCT wordmark — the app's own identity. The tenant it's deployed
 * for (Aditya Birla Capital) is shown separately by <TenantSwitcher>, so the
 * product and the customer read as a deliberate co-brand, not a conflict.
 */
export function Brandmark({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-brand-crimson text-white shadow-1">
        <Aperture size={19} strokeWidth={2.25} />
      </span>
      {!collapsed && (
        <span className="flex flex-col leading-none">
          <span className="text-body font-semibold tracking-tight text-text">ProofLens</span>
          <span className="mt-0.5 text-caption text-text-muted">Capture Integrity</span>
        </span>
      )}
    </div>
  );
}
