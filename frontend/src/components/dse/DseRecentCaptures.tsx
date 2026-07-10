"use client";

import { useRouter } from "next/navigation";

import { Card, CardHeader } from "@/components/ui/Card";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import type { ResultItem } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

/** The DSE's latest flagged captures — band, score, reason, opportunity, date — each
 *  row opening the same drill-down history already built (/history?rep_id=). */
export function DseRecentCaptures({ agentId, recent }: { agentId: string; recent: ResultItem[] }) {
  const router = useRouter();
  const historyHref = `/history?rep_id=${encodeURIComponent(agentId)}`;

  return (
    <Card>
      <CardHeader
        title="Recent flagged captures"
        subtitle="This DSE's latest Doubtful and Suspect verdicts."
        action={
          <a href={historyHref} className="text-body-sm font-medium text-accent hover:underline">
            View all in history
          </a>
        }
      />
      {recent.length === 0 ? (
        <p className="px-5 py-8 text-center text-body-sm text-text-muted">
          No flagged captures for this DSE yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-body-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="whitespace-nowrap px-4 py-2.5 text-left text-caption font-medium uppercase tracking-wide text-text-muted">
                  Verdict
                </th>
                <th className="whitespace-nowrap px-4 py-2.5 text-right text-caption font-medium uppercase tracking-wide text-text-muted">
                  Score
                </th>
                <th className="whitespace-nowrap px-4 py-2.5 text-left text-caption font-medium uppercase tracking-wide text-text-muted">
                  Reason
                </th>
                <th className="whitespace-nowrap px-4 py-2.5 text-left text-caption font-medium uppercase tracking-wide text-text-muted">
                  Opportunity
                </th>
                <th className="whitespace-nowrap px-4 py-2.5 text-right text-caption font-medium uppercase tracking-wide text-text-muted">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => router.push(historyHref)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") router.push(historyHref);
                  }}
                  tabIndex={0}
                  role="link"
                  aria-label={`Open this DSE's history — ${r.band}, score ${Math.round(r.score)}`}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-2/60 focus-visible:bg-surface-2"
                >
                  <td className="px-4 py-3">
                    <VerdictBadge band={r.band} size="sm" />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-text">{Math.round(r.score)}</td>
                  <td className="px-4 py-3 text-text-secondary">{r.reason}</td>
                  <td className="px-4 py-3 tabular-nums text-text-secondary">{r.opportunity_id ?? "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-text-muted">
                    {formatDateTime(r.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
