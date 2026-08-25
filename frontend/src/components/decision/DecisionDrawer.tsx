"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { ChecksList } from "@/components/verdict/ChecksList";
import { Button } from "@/components/ui/Button";
import { provenanceSignal } from "@/lib/provenance";
import { formatRelative } from "@/lib/utils";
import type { ResultItem } from "@/lib/api/types";

export function DecisionDrawer({
  result,
  onClose,
}: {
  result: ResultItem | null;
  onClose: () => void;
}) {
  if (!result) return null;
  const prov = provenanceSignal(result.checks);
  const written = result.band !== "Unassessed";

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Decision detail">
      <div className="absolute inset-0 bg-black/55" onClick={onClose} />
      <aside className="absolute right-0 top-0 bottom-0 flex w-[560px] max-w-[94vw] flex-col border-l border-border-strong bg-canvas shadow-2xl">
        <header className="flex items-center gap-3 border-b border-border bg-surface px-5 py-4">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-text-muted">
              ProofLens · automated decision
            </div>
            <h2 className="text-[15px] font-semibold">{result.rep_id ?? result.opportunity_id ?? result.id}</h2>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="ml-auto rounded-md border border-border p-2 text-text-muted hover:bg-surface-2"
          >
            <X size={16} />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-5">
          <div
            className={`mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${
              written
                ? "bg-verdict-clear-bg text-verdict-clear-fg"
                : "bg-verdict-unassessed-bg text-verdict-unassessed-fg"
            }`}
          >
            {written
              ? <>&#10003; Auto-decided &amp; written back to LSQ · {result.opportunity_id ?? result.id}</>
              : <>&#9711; Held as Unassessed — auto-retry queued · not written to LSQ</>}
          </div>

          <div className="flex items-center gap-4 py-2">
            <ScoreRing score={result.score} band={result.band} size={84} />
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-text-muted">Verdict</div>
              <VerdictBadge band={result.band} size="lg" />
              <p className="mt-2 max-w-[42ch] text-sm text-text-secondary">{result.reason}</p>
            </div>
          </div>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Case summary · <span className="text-accent">auto-written</span>
            </div>
            <p className="text-sm leading-relaxed">{result.copilot_summary ?? result.reason}</p>
          </section>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Provenance
            </div>
            <div className="text-sm">
              <span
                className={
                  prov.state === "signed"
                    ? "text-verdict-clear-fg"
                    : prov.state === "unsigned"
                    ? "text-verdict-suspect-fg"
                    : "text-verdict-unassessed-fg"
                }
              >
                {prov.state === "signed" ? "✓" : prov.state === "unsigned" ? "✕" : "—"}{" "}
                {prov.label}
              </span>
            </div>
          </section>

          <section className="mt-4 rounded-xl border border-border bg-surface p-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Why it decided
            </div>
            <ChecksList checks={result.checks} rubricVersion={result.rubric_version} />
          </section>

          <div className="mt-4 flex gap-2">
            <Link href={`/verdict/${result.id}`} className="flex-1">
              <Button className="w-full">Open full record</Button>
            </Link>
          </div>
          <p className="mt-2 text-center text-[11px] text-text-muted">
            Decided {formatRelative(result.created_at)} · the verdict is automated — no human override.
          </p>
        </div>
      </aside>
    </div>
  );
}
