"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ReviewCard } from "@/components/review/ReviewCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api/client";
import { useResults } from "@/lib/api/hooks";
import type { ResultItem, ReviewDecision } from "@/lib/api/types";

const BAND_ORDER = { Suspect: 0, Doubtful: 1, Clear: 2 };
const DECISION_KEYS: Record<string, ReviewDecision> = {
  a: "approve",
  r: "reject",
  f: "false_positive",
  e: "escalate",
};

export default function ReviewPage() {
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useResults({ limit: 200, review: "pending" });
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [focusIdx, setFocusIdx] = useState(0);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  const queue: ResultItem[] = useMemo(
    () =>
      (data?.items ?? [])
        .filter((r) => r.band !== "Clear" && !r.review)
        .sort((a, b) => BAND_ORDER[a.band] - BAND_ORDER[b.band]),
    [data],
  );

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: ReviewDecision }) =>
      api.reviewDecision(id, decision),
    onMutate: ({ id }) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: (_res, { decision }) => {
      toast({ kind: "success", title: `Marked ${decision.replace("_", " ")}` });
      refetch();
    },
    onError: () =>
      toast({
        kind: "error",
        title: "Couldn't record the decision",
        description: "The review service didn't accept the decision. Please retry.",
      }),
  });

  // Keep the focused index within bounds as the queue shrinks.
  useEffect(() => {
    if (focusIdx > queue.length - 1) setFocusIdx(Math.max(0, queue.length - 1));
  }, [queue.length, focusIdx]);

  // Keyboard triage: j/k (or arrows) to move, a/r/f/e to decide on the focused card.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (!queue.length) return;
      const k = e.key.toLowerCase();
      if (k === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIdx((i) => Math.min(queue.length - 1, i + 1));
      } else if (k === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      } else if (DECISION_KEYS[k]) {
        e.preventDefault();
        const item = queue[focusIdx];
        if (item && pendingId == null) decide.mutate({ id: item.id, decision: DECISION_KEYS[k] });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [queue, focusIdx, pendingId, decide]);

  useEffect(() => {
    cardRefs.current[focusIdx]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focusIdx, queue.length]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Review queue"
        description="Doubtful and Suspect verdicts queued for a human decision."
      />

      <Card className="flex items-center gap-3 px-4 py-2.5 text-caption text-text-muted">
        <span className="font-medium text-text-secondary">Keyboard:</span>
        <kbd className="rounded bg-surface-2 px-1.5 py-0.5">J</kbd>/<kbd className="rounded bg-surface-2 px-1.5 py-0.5">K</kbd> move
        <span className="mx-1">·</span>
        <kbd className="rounded bg-surface-2 px-1.5 py-0.5">A</kbd> approve
        <kbd className="rounded bg-surface-2 px-1.5 py-0.5">R</kbd> reject
        <kbd className="rounded bg-surface-2 px-1.5 py-0.5">F</kbd> false-positive
        <kbd className="rounded bg-surface-2 px-1.5 py-0.5">E</kbd> escalate
      </Card>

      {isError ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
          <p className="text-body-sm text-text-secondary">Couldn&apos;t load the review queue.</p>
          <button onClick={() => refetch()} className="text-caption font-medium underline">Retry</button>
        </Card>
      ) : isLoading || !data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      ) : queue.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="Nothing to review"
          what="No Doubtful or Suspect verdicts are waiting. Clear verdicts don't need a human decision."
          cta={{ label: "Analyze a Photo", href: "/analyze" }}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {queue.map((item, i) => (
            <div key={item.id} ref={(el) => { cardRefs.current[i] = el; }}>
              <ReviewCard
                item={item}
                focused={i === focusIdx}
                status={pendingId === item.id ? "pending" : "idle"}
                onDecide={(decision) => decide.mutate({ id: item.id, decision })}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
