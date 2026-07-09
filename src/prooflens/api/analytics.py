"""Pure analytics aggregation over ResultView items — buckets, previous-period
deltas, and per-hierarchy-node groups. No DB, no request objects: fed the range
items, the previous-period items, and the tenant's hierarchy rows so it stays
InMemory/Postgres-parity and unit-testable offline (spec §0a)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from ..service.hierarchy import resolve_node
from ..service.views import ResultView

# API group_by value -> hierarchy node field. "zone" is the friendly alias.
GROUP_BY_FIELD: dict[str, str] = {
    "zone": "zonal_head",
    "srsm": "srsm",
    "rsm": "rsm",
    "sm": "sm",
    "branch": "branch",
    "city": "city",
}


def _scored_date(r: ResultView) -> date:
    return datetime.fromisoformat(r.created_at).date()


def _tally(items: list[ResultView]) -> dict:
    clear = sum(1 for r in items if r.band == "Clear")
    doubtful = sum(1 for r in items if r.band == "Doubtful")
    suspect = sum(1 for r in items if r.band == "Suspect")
    scores = [r.score for r in items]
    return {
        "clear": clear,
        "doubtful": doubtful,
        "suspect": suspect,
        "total": len(items),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
    }


def _bucket_edges(start: datetime, end: datetime, bucket: str) -> list[tuple[date, date, str]]:
    """List of (bucket_start_date, bucket_end_date_exclusive, label). end is exclusive."""
    s = start.date()
    e = end.date()               # exclusive
    edges: list[tuple[date, date, str]] = []
    if bucket == "daily":
        d = s
        while d < e:
            edges.append((d, d + timedelta(days=1), d.isoformat()))
            d += timedelta(days=1)
    elif bucket == "weekly":
        d = s
        n = 1
        while d < e:
            edges.append((d, d + timedelta(days=7), f"Week {n}"))
            d += timedelta(days=7)
            n += 1
    elif bucket == "monthly":
        y, mo = s.year, s.month
        while date(y, mo, 1) < e:
            if mo == 12:
                nxt = date(y + 1, 1, 1)
            else:
                nxt = date(y, mo + 1, 1)
            edges.append((date(y, mo, 1), nxt, f"{y:04d}-{mo:02d}"))
            y, mo = nxt.year, nxt.month
    else:  # pragma: no cover - guarded by the endpoint
        raise ValueError(f"unknown bucket {bucket!r}")
    return edges


def build_buckets(
    items: list[ResultView],
    start: datetime,
    end: datetime,
    bucket: str,
    today: date | None = None,
) -> list[dict]:
    """Bucketed band/score series across [start, end). Weekly = 'Week 1..N'
    anchored to the range start; monthly = calendar months. The bucket that
    contains `today` is flagged incomplete. `today` defaults to wall-clock
    (UTC-relative to `start`'s tzinfo) but can be injected for deterministic
    testing."""
    if today is None:
        today = datetime.now(tz=start.tzinfo).date()
    edges = _bucket_edges(start, end, bucket)
    by_bucket: list[list[ResultView]] = [[] for _ in edges]
    range_end_date = end.date()  # exclusive range boundary
    for r in items:
        if not r.created_at:
            continue
        d = _scored_date(r)
        for i, (bs, be, _label) in enumerate(edges):
            if bs <= d < be:
                by_bucket[i].append(r)
                break
    out: list[dict] = []
    for (bs, be, label), rows in zip(edges, by_bucket, strict=True):
        tally = _tally(rows)
        # Inclusive last day of the window for display.
        # Clamp to not exceed the range's exclusive end.
        last_day = min(be - timedelta(days=1), range_end_date - timedelta(days=1))
        out.append({
            "bucket_label": label,
            "start": bs.isoformat(),
            "end": last_day.isoformat(),
            "clear": tally["clear"],
            "doubtful": tally["doubtful"],
            "suspect": tally["suspect"],
            "total": tally["total"],
            "avg_score": tally["avg_score"],
            "incomplete": bs <= today < be,
        })
    return out


# review_status values that count as a completed decision on a flagged result.
# "escalate" and pending (None) are deliberately excluded from `reviewed`.
_CONFIRMED_STATUSES = {"reject"}
_OVERTURNED_STATUSES = {"approve", "false_positive"}


def flag_precision(items: list[ResultView]) -> dict:
    """Flag-precision KPI over `items`: a "flag" is any non-"Clear" band
    (Doubtful or Suspect) — reuses the same band check `_tally` uses. Among
    flagged results, only "reject"/"approve"/"false_positive" reviews count
    toward `reviewed`; "escalate" and pending (None) are excluded entirely."""
    confirmed = 0
    overturned = 0
    for r in items:
        if r.band == "Clear":
            continue
        if r.review_status in _CONFIRMED_STATUSES:
            confirmed += 1
        elif r.review_status in _OVERTURNED_STATUSES:
            overturned += 1
    reviewed = confirmed + overturned
    precision_pct = round(confirmed / reviewed * 100, 1) if reviewed > 0 else None
    return {
        "reviewed": reviewed,
        "confirmed": confirmed,
        "overturned": overturned,
        "precision_pct": precision_pct,
    }


def _node_label(rows: list[dict], r: ResultView, field: str) -> str:
    node = resolve_node(rows, r.rep_id, _scored_date(r))
    if node is None:
        return "Unmapped"
    value = node.get(field)
    return value if value else "Unmapped"


def _groups(items: list[ResultView], rows: list[dict], field: str) -> list[dict]:
    buckets: dict[str, list[ResultView]] = {}
    for r in items:
        label = _node_label(rows, r, field)
        buckets.setdefault(label, []).append(r)
    total_all = len(items)
    out: list[dict] = []
    for label, group in sorted(buckets.items()):
        t = _tally(group)
        out.append({
            "node": label,
            "total": t["total"],
            "clear": t["clear"],
            "doubtful": t["doubtful"],
            "suspect": t["suspect"],
            "avg_score": t["avg_score"],
            "suspect_rate": round(t["suspect"] / t["total"], 3) if t["total"] else 0.0,
            "share": round(t["total"] / total_all, 3) if total_all else 0.0,
        })
    return out


def aggregate_range(
    items: list[ResultView],
    prev_items: list[ResultView],
    rows: list[dict],
    *,
    start: datetime,
    end: datetime,
    bucket: str,
    group_by: str,
    today: date,
) -> dict:
    """The additive analytics payload: bucketed series, previous-period tally,
    explicit period bounds, per-node groups (incl. Unmapped), reason counts."""
    series = build_buckets(items, start, end, bucket, today=today)
    last_day = end.date() - timedelta(days=1)
    prev_len_days = (end.date() - start.date()).days
    prev_end = start.date()                      # exclusive
    prev_start = prev_end - timedelta(days=prev_len_days)
    groups = (
        _groups(items, rows, GROUP_BY_FIELD[group_by])
        if group_by != "none"
        else []
    )
    reason_counts = dict(Counter(r.reason_code for r in items))
    return {
        "series": series,
        "incomplete": any(b["incomplete"] for b in series),
        "previous": _tally(prev_items),
        "period": {"from": start.date().isoformat(), "to": last_day.isoformat()},
        "previous_period": {
            "from": prev_start.isoformat(),
            "to": (prev_end - timedelta(days=1)).isoformat(),
        },
        "groups": groups,
        "reason_counts": reason_counts,
        "flag_precision": flag_precision(items),
    }
