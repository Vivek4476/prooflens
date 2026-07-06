"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Info } from "lucide-react";
import { useState } from "react";

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

export default function ReviewPage() {
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useResults({ limit: 200 });
  const [attempted, setAttempted] = useState<Record<string, boolean>>({});
  const [pendingId, setPendingId] = useState<string | null>(null);

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: ReviewDecision }) =>
      api.reviewDecision(id, decision),
    onMutate: ({ id }) => setPendingId(id),
    onSettled: () => setPendingId(null),
    onSuccess: () => {
      toast({ kind: "success", title: "Decision recorded" });
      refetch();
    },
    onError: (_e, { id }) => {
      setAttempted((m) => ({ ...m, [id]: true }));
      toast({
        kind: "info",
        title: "Review endpoint pending",
        description: "POST /v1/results/{id}/review isn't implemented yet (see BACKEND_REQUIREMENTS.md).",
      });
    },
  });

  const queue: ResultItem[] = (data?.items ?? [])
    .filter((r) => r.band !== "Clear")
    .sort((a, b) => BAND_ORDER[a.band] - BAND_ORDER[b.band]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Review queue"
        description="Doubtful and Suspect verdicts queued for a human decision."
      />

      {/* Honest disclosure — the decision endpoint is not yet implemented. */}
      <Card className="flex items-start gap-3 border-l-2 border-l-brand-gold p-4">
        <Info size={17} className="mt-0.5 shrink-0 text-text-secondary" />
        <p className="text-caption text-text-secondary">
          The moderation console is complete and wired to the typed client. The decision endpoint{" "}
          <code className="rounded bg-surface-2 px-1 py-0.5 text-text">POST /v1/results/&#123;id&#125;/review</code>{" "}
          is not implemented on the backend yet, so actions show a pending state — no responses are
          mocked. The exact contract is documented in{" "}
          <span className="font-medium text-text">frontend/BACKEND_REQUIREMENTS.md</span>.
        </p>
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
          {queue.map((item) => (
            <ReviewCard
              key={item.id}
              item={item}
              status={pendingId === item.id ? "pending" : attempted[item.id] ? "attempted" : "idle"}
              onDecide={(decision) => decide.mutate({ id: item.id, decision })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
