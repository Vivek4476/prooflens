"""DSE (agent) search + scorecard endpoints (additive; spec:
docs/superpowers/specs/2026-07-10-dse-scorecard-design.md).

There are ~266 DSEs and most individual agents have too few captures to rank
fairly, so a "worst DSEs" leaderboard would mostly read "not enough volume"
under the existing small-sample guard. These two endpoints instead let an
operator look up ONE DSE (by name or id) and see their honest scorecard —
real (possibly tiny) numbers, never fabricated.

- GET /v1/dse?q=            — name/id search over the hierarchy, tenant-scoped.
- GET /v1/dse/{agent_id}    — the scorecard: chain, band mix, trend, recent.

Reuses the same building blocks as /v1/analytics/summary and /v1/results
(get_repo, DEFAULT_TENANT resolution, build_buckets, list_results) — no new
business logic, no scoring/engine/webhook changes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..engine.verdicts import REASON_SHORT_LABEL, Reason
from ..service.hierarchy import agent_display_name
from ..service.ids import normalize_id
from ..service.repo import Repo
from ..service.views import TenantView
from .analytics import _tally, build_buckets
from .auth import require_tenant
from .date_range import resolve_range
from .deps import get_repo

router = APIRouter(prefix="/v1/dse", tags=["dse"])

_SEARCH_LIMIT = 25
_RECENT_LIMIT = 20
_SCORECARD_LIMIT = 5000


def _latest_rows_by_agent(rows: list[dict]) -> dict[str, dict]:
    """One row per agent_id: the latest-`valid_from` version (search/listing
    surfaces the agent's CURRENT chain, unlike the effective-dated resolver
    used for scoring historical results)."""
    latest: dict[str, dict] = {}
    for row in rows:
        key = row.get("agent_id")
        if key is None:
            continue
        cur = latest.get(key)
        if cur is None or row["valid_from"] > cur["valid_from"]:
            latest[key] = row
    return latest


@router.get("")
def search_dse(
    q: str = Query(default=""),
    repo: Repo = Depends(get_repo),
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    """Search the hierarchy by name (case-insensitive substring) or agent_id
    (case-insensitive substring). Empty q -> the most-active DSEs (by total
    result count, all time), else the first N by agent_id. Capped at 25,
    tenant-scoped."""
    tenant_id = tenant.id
    needle = q.strip()
    if needle:
        matches = repo.search_hierarchy(tenant_id, needle, _SEARCH_LIMIT) if tenant_id else []
    else:
        rows = repo.get_hierarchy_rows(tenant_id) if tenant_id else []
        latest = _latest_rows_by_agent(rows)
        # most-active, all time (as before)
        counts = repo.result_counts_by_rep(tenant_id, None, None)
        matches = sorted(
            latest.values(),
            key=lambda r: (-counts.get(r["agent_id"], 0), r["agent_id"]),
        )[:_SEARCH_LIMIT]

    results = [
        {
            "agent_id": row["agent_id"],
            # search_hierarchy / _latest_rows_by_agent return the LATEST row per
            # agent, so its agent_name IS the display name (falls back to id).
            "name": row.get("agent_name") or row["agent_id"],
            "branch": row.get("branch"),
            "sm": row.get("sm"),
        }
        for row in matches
    ]
    return {"results": results}


@router.get("/{agent_id}")
def dse_scorecard(
    agent_id: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None, alias="to"),
    bucket: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
    repo: Repo = Depends(get_repo),
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    """The DSE scorecard: manager chain, KPIs, suspect-rate trend, top flag
    reasons, and the DSE's recent flagged captures — all computed over THIS
    rep_id's results in [from, to). Honest small-sample: a sparse DSE shows
    real (possibly tiny) numbers, never fabricated; 404 when the agent_id has
    neither a hierarchy row nor any results (unknown agent)."""
    tenant_id = tenant.id
    rows = repo.get_hierarchy_rows(tenant_id) if tenant_id else []

    try:
        start, end = resolve_range(from_, to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    items, total = repo.list_results(
        tenant_id=tenant_id, limit=_SCORECARD_LIMIT, offset=0, rep_id=agent_id, start=start, end=end
    )

    latest = _latest_rows_by_agent(rows)
    # Same canonical id rule used everywhere (upload, list_results filter), so
    # the hierarchy lookup can't drift from how ids are stored/compared.
    norm_id = normalize_id(agent_id)
    hierarchy_row = latest.get(norm_id) if norm_id else None

    if hierarchy_row is None and total == 0:
        # Also check for ANY result ever (outside the range) before declaring
        # the agent unknown — a real DSE with no activity in this window is
        # not "unknown", just quiet.
        _any_items, any_total = repo.list_results(
            tenant_id=tenant_id, limit=1, offset=0, rep_id=agent_id
        )
        if any_total == 0:
            raise HTTPException(status_code=404, detail=f"no such DSE {agent_id!r}")

    name = agent_display_name(rows, agent_id)
    chain = {
        "sm": hierarchy_row.get("sm") if hierarchy_row else None,
        "rsm": hierarchy_row.get("rsm") if hierarchy_row else None,
        "srsm": hierarchy_row.get("srsm") if hierarchy_row else None,
        "zone": hierarchy_row.get("zonal_head") if hierarchy_row else None,
        "branch": hierarchy_row.get("branch") if hierarchy_row else None,
        "city": hierarchy_row.get("city") if hierarchy_row else None,
    }

    tally = _tally(items)
    band_distribution = {
        "Clear": tally["clear"], "Doubtful": tally["doubtful"], "Suspect": tally["suspect"],
    }
    suspect_rate = round(tally["suspect"] / tally["total"], 3) if tally["total"] else 0.0

    reason_counts: dict[str, int] = {}
    for r in items:
        reason_counts[r.reason_code] = reason_counts.get(r.reason_code, 0) + 1
    # reason_code is always a Reason value — the fusion layer emits no other
    # strings (see engine/verdicts.py's module docstring) — same assumption
    # /v1/analytics/summary's top_reasons already makes.
    top_reasons = [
        {
            "reason_code": code,
            "short_label": REASON_SHORT_LABEL[Reason(code)],
            "count": n,
        }
        for code, n in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    today = datetime.now(UTC).date()
    series = build_buckets(items, start, end, bucket, today=today)
    trend = [
        {
            "bucket_label": b["bucket_label"],
            "start": b["start"],
            "end": b["end"],
            "suspect": b["suspect"],
            "total": b["total"],
            "suspect_rate": round(b["suspect"] / b["total"], 3) if b["total"] else 0.0,
            "incomplete": b["incomplete"],
        }
        for b in series
    ]

    flagged = [r for r in items if r.band != "Clear"]
    flagged.sort(key=lambda r: r.created_at, reverse=True)
    recent = [r.to_dict() for r in flagged[:_RECENT_LIMIT]]

    return {
        "agent_id": norm_id if norm_id else agent_id,
        "name": name,
        "chain": chain,
        "total": tally["total"],
        "band_distribution": band_distribution,
        "suspect_rate": suspect_rate,
        "avg_score": tally["avg_score"],
        "top_reasons": top_reasons,
        "trend": trend,
        "recent": recent,
        "truncated": total > _SCORECARD_LIMIT,
    }

