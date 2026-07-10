import { ChevronRight } from "lucide-react";

import type { DseChain } from "@/lib/api/types";
import { chainBreadcrumb } from "@/lib/dse/scorecard";

/** SM -> RSM -> SRSM -> Zone -> Branch, dropping any level the hierarchy lacks —
 *  never a fabricated placeholder for a missing level. */
export function ChainBreadcrumb({ chain }: { chain: DseChain }) {
  const parts = chainBreadcrumb(chain);
  if (parts.length === 0) {
    return <p className="text-body-sm text-text-muted">No manager chain on file for this DSE.</p>;
  }
  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-body-sm text-text-secondary">
      {parts.map((p, i) => (
        <li key={`${p}-${i}`} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight aria-hidden size={13} className="shrink-0 text-text-muted" />}
          <span className={i === parts.length - 1 ? "text-text" : undefined}>{p}</span>
        </li>
      ))}
    </ol>
  );
}
