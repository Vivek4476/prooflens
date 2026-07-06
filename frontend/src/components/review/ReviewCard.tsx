"use client";

import { Check, CircleSlash, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StateIcon } from "@/components/verdict/StateIcon";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import type { ResultItem, ReviewDecision } from "@/lib/api/types";
import { CHECK_LABEL, checkConfidence, checkState } from "@/lib/verdict";
import { formatRelative } from "@/lib/utils";

export function ReviewCard({
  item,
  onDecide,
  status,
}: {
  item: ResultItem;
  onDecide: (d: ReviewDecision) => void;
  status: "idle" | "pending" | "attempted";
}) {
  // The signals that actually drove the flag (warn/fail), most severe first.
  const flags = item.checks
    .map((c) => ({ c, s: checkState(c) }))
    .filter((x) => x.s === "fail" || x.s === "warn")
    .sort((a, b) => (a.s === "fail" ? -1 : 1) - (b.s === "fail" ? -1 : 1));

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <VerdictBadge band={item.band} />
          <span className="text-body-sm tabular-nums text-text-muted">{Math.round(item.score)}/100</span>
        </div>
        <span className="text-caption text-text-muted">{formatRelative(item.created_at)}</span>
      </div>

      {/* Verbatim reason */}
      <p className="text-body font-medium leading-snug text-text">{item.reason}</p>

      {/* Evidence that fired */}
      {flags.length > 0 && (
        <div className="space-y-1.5 rounded-md bg-surface-2 p-3">
          {flags.map(({ c, s }) => {
            const conf = checkConfidence(c);
            return (
              <div key={c.name} className="flex items-start gap-2">
                <div className="mt-0.5">
                  <StateIcon state={s} size={15} />
                </div>
                <p className="flex-1 text-caption text-text-secondary">
                  <span className="font-medium text-text">{CHECK_LABEL[c.name] ?? c.name}:</span>{" "}
                  {c.summary}
                  {conf != null && <span className="text-text-muted"> · {Math.round(conf)}% conf.</span>}
                </p>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-center gap-3 text-caption text-text-muted">
        <span>Rep {item.rep_id ?? "—"}</span>
        <span>·</span>
        <span>Opp {item.opportunity_id ?? "—"}</span>
        <span>·</span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5">{item.source}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button variant="secondary" onClick={() => onDecide("approve")} disabled={status === "pending"}>
          <Check size={15} />
          Approve
        </Button>
        <Button variant="danger" onClick={() => onDecide("reject")} disabled={status === "pending"}>
          <X size={15} />
          Reject
        </Button>
        <Button variant="ghost" onClick={() => onDecide("false_positive")} disabled={status === "pending"}>
          <CircleSlash size={15} />
          False positive
        </Button>
        {status === "attempted" && (
          <span className="ml-auto text-caption text-warn">Pending backend endpoint</span>
        )}
      </div>
    </Card>
  );
}
