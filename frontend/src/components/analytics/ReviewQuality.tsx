import type { FlagPrecision } from "@/lib/api/types";
import { formatCount, formatPct } from "@/lib/format";

/** Below this many reviewed flags, a precision % is too noisy to report — say so honestly
 *  rather than show a wobbly percentage off a handful of decisions. */
const MIN_REVIEWS_FOR_PRECISION = 10;

/**
 * A slim "review quality" strip: how often a Doubtful/Suspect flag was confirmed by a
 * reviewer. Confirmed = Reject; overturned = Approve + False positive; escalations and
 * pending items are excluded. Shows an honest small-sample state until enough flags are
 * reviewed.
 */
export function ReviewQuality({ flagPrecision }: { flagPrecision: FlagPrecision }) {
  const { reviewed, confirmed, overturned, precision_pct } = flagPrecision;
  const ready = reviewed >= MIN_REVIEWS_FOR_PRECISION && precision_pct != null;

  return (
    <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="text-caption font-medium text-text-muted">Flag precision</div>
        <p className="mt-0.5 text-caption text-text-muted">
          How often a Doubtful or Suspect flag was confirmed on review.
        </p>
      </div>

      {ready ? (
        <div className="flex items-center gap-5 sm:shrink-0">
          <span className="text-display leading-none tabular-nums text-text">{formatPct(precision_pct)}</span>
          <span className="text-body-sm text-text-secondary">
            <span className="tabular-nums text-text">{formatCount(confirmed)}</span> of{" "}
            <span className="tabular-nums">{formatCount(reviewed)}</span> reviewed flags confirmed
            <span className="mt-0.5 block text-caption text-text-muted">
              {formatCount(overturned)} overturned · escalations excluded
            </span>
          </span>
        </div>
      ) : (
        <div className="text-body-sm text-text-muted sm:shrink-0 sm:text-right">
          {`Only ${formatCount(reviewed)} reviewed flag${reviewed === 1 ? "" : "s"} — not enough to report precision yet.`}
        </div>
      )}
    </div>
  );
}
