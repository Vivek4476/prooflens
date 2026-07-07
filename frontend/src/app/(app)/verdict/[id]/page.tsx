"use client";

import { AlertCircle, ArrowLeft, Clock } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ChecksList } from "@/components/verdict/ChecksList";
import { ScoreRing } from "@/components/verdict/ScoreRing";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import { useResult } from "@/lib/api/hooks";
import { formatDateTime, formatMs } from "@/lib/utils";

/**
 * The Verdict Detail page — the permanent, linkable home for a single scored
 * result and its full evidence. Everything (Analyze, History rows) links here,
 * so a verdict is no longer ephemeral.
 */
export default function VerdictDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const { data: r, isLoading, isError } = useResult(id);

  const back = (
    <Link href="/history">
      <Button variant="ghost">
        <ArrowLeft size={15} />
        Back to history
      </Button>
    </Link>
  );

  if (isError) {
    return (
      <div>
        <PageHeader title="Verdict" actions={back} />
        <Card className="flex flex-col items-center gap-3 px-6 py-16 text-center">
          <AlertCircle size={22} className="text-text-muted" />
          <p className="text-body-sm font-medium text-text">Verdict not found</p>
          <p className="max-w-md text-caption text-text-muted">
            No stored result matches this id. It may have been purged, or the link is stale.
          </p>
          <Link href="/history" className="mt-1">
            <Button variant="secondary">Go to history</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Verdict"
        description={id ? `Result ${id}` : undefined}
        actions={back}
      />

      {isLoading || !r ? (
        <div className="space-y-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Verdict summary — band first, then the reason and the score. */}
          <Card className="p-6">
            <div className="mb-5 flex items-center justify-between">
              <VerdictBadge band={r.band} size="lg" />
              <div className="flex items-center gap-1.5 text-caption text-text-muted">
                <Clock size={13} />
                {formatMs(r.processing_ms)}
              </div>
            </div>

            <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
              <ScoreRing score={r.score} band={r.band} />
              <div className="flex-1">
                <p className="text-h2 leading-snug text-text">{r.reason}</p>
                <p className="mt-3 text-caption text-text-muted">
                  Rubric {r.rubric_version} · scored {formatDateTime(r.created_at)}
                </p>
              </div>
            </div>
          </Card>

          {/* Capture context */}
          <Card>
            <CardHeader title="Capture context" subtitle="Where this verdict came from." />
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 py-4 sm:grid-cols-4">
              <Field label="Rep" value={r.rep_id ?? "—"} mono />
              <Field label="Opportunity" value={r.opportunity_id ?? "—"} mono />
              <Field label="Source" value={r.source} />
              <Field label="Scored" value={formatDateTime(r.created_at)} />
            </dl>
          </Card>

          {/* Moderator review — only once a decision has been recorded. */}
          {r.review && (
            <Card>
              <CardHeader title="Moderator review" subtitle="The human decision recorded for this verdict." />
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 py-4 sm:grid-cols-4">
                <Field label="Decision" value={r.review.status.replace("_", " ")} />
                <Field label="Reviewer" value={r.review.reviewer ?? "—"} />
                <Field
                  label="Reviewed"
                  value={r.review.reviewed_at ? formatDateTime(r.review.reviewed_at) : "—"}
                />
                <Field label="Note" value={r.review.note ?? "—"} />
              </dl>
            </Card>
          )}

          {/* Full evidence */}
          <Card>
            <CardHeader
              title="Why this verdict"
              subtitle="Every check the pipeline ran — what was found and how confident."
            />
            <ChecksList checks={r.checks} rubricVersion={r.rubric_version} />
          </Card>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-caption font-medium uppercase tracking-wide text-text-muted">{label}</dt>
      <dd className={`mt-1 truncate text-body-sm text-text${mono ? " font-mono tabular-nums" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
