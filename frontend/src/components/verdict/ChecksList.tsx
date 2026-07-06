import { cn } from "@/lib/utils";
import {
  CHECK_LABEL,
  STATE_WORD,
  checkConfidence,
  checkState,
} from "@/lib/verdict";
import type { CheckOutcome } from "@/lib/api/types";

import { StateIcon, stateClass } from "./StateIcon";

/**
 * AI Explainability — one row per check the backend ACTUALLY ran (checks[] is
 * truth). We never invent checks the API doesn't return. Transparency: what was
 * found, why, how confident.
 */
export function ChecksList({
  checks,
  rubricVersion,
}: {
  checks: CheckOutcome[];
  rubricVersion?: string;
}) {
  return (
    <div>
      <ul className="divide-y divide-border">
        {checks.map((c) => {
          const state = checkState(c);
          const confidence = checkConfidence(c);
          const stub =
            c.name === "content" && c.available && c.data?.is_real_backend === false;
          return (
            <li key={c.name} className="flex items-start gap-3.5 px-5 py-3.5">
              <div className="mt-0.5">
                <StateIcon state={state} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-body-sm font-medium text-text">
                    {CHECK_LABEL[c.name] ?? c.name}
                  </span>
                  <span className={cn("text-caption font-semibold", stateClass(state))}>
                    {STATE_WORD[state]}
                  </span>
                  {stub && (
                    <span className="rounded bg-surface-2 px-1.5 py-0.5 text-caption text-text-muted">
                      demo model
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-body-sm text-text-secondary">{c.summary}</p>
              </div>
              {confidence != null && (
                <div className="w-24 shrink-0 text-right">
                  <div className="text-caption text-text-muted">confidence</div>
                  <div className="text-body-sm font-medium tabular-nums text-text">
                    {Math.round(confidence)}%
                  </div>
                  <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-text-secondary"
                      style={{ width: `${Math.max(0, Math.min(100, confidence))}%` }}
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {rubricVersion && (
        <div className="border-t border-border px-5 py-2.5">
          <p className="text-caption text-text-muted">
            Rubric {rubricVersion} · signals fuse independently; no single check decides.
          </p>
        </div>
      )}
    </div>
  );
}
