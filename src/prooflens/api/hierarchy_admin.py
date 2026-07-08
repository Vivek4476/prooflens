"""Admin hierarchy endpoints (spec §0d).

POST /v1/admin/hierarchy       — multipart CSV upload -> validate -> new version.
GET  /v1/admin/hierarchy/status — current version + match rate (last 90 days).
GET  /v1/admin/hierarchy/template — a downloadable CSV template (nice-to-have).

Flows through the Repo abstraction (NOT admin.py's raw session), so hierarchy is
offline-testable with InMemoryRepo. Reuses require_admin."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..service.hierarchy import NODE_FIELDS
from ..service.ids import normalize_id
from ..service.repo import Repo
from .admin import require_admin
from .deps import get_repo
from .scoring import DEFAULT_TENANT

router = APIRouter(prefix="/v1/admin/hierarchy", tags=["admin", "hierarchy"])

_HEADER = ("agent_id", *NODE_FIELDS, "valid_from")  # canonical column set


def _tenant_id(repo: Repo) -> str:
    t = repo.get_tenant_by_slug(DEFAULT_TENANT)
    if t is None:
        raise HTTPException(status_code=404, detail=f"unknown tenant {DEFAULT_TENANT!r}")
    return t.id


def _parse_csv(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")           # tolerate a BOM from Excel exports
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="empty CSV (no header row)")
    headers = [h.strip().lower() for h in reader.fieldnames]
    unknown = [h for h in headers if h not in _HEADER]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown columns: {', '.join(unknown)}")
    for required in ("agent_id", "valid_from"):
        if required not in headers:
            raise HTTPException(status_code=400, detail=f"missing required column: {required}")

    rows: list[dict] = []
    seen: set[tuple[str, date]] = set()
    for i, raw in enumerate(reader, start=2):   # row 1 is the header
        norm = {k.strip().lower(): (v.strip() if isinstance(v, str) else v)
                for k, v in raw.items() if k is not None}
        agent = normalize_id(norm.get("agent_id"))
        if agent is None:
            raise HTTPException(status_code=400, detail=f"row {i}: blank agent_id")
        vf_raw = norm.get("valid_from") or ""
        if not vf_raw:
            vf = date.today()
        else:
            try:
                vf = date.fromisoformat(vf_raw)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f"row {i}: bad valid_from {vf_raw!r}"
                ) from exc
        key = (agent, vf)
        if key in seen:
            raise HTTPException(
                status_code=400,
                detail=f"row {i}: duplicate agent_id {agent!r} for valid_from {vf.isoformat()}",
            )
        seen.add(key)
        rows.append({
            "agent_id": agent,
            "sm": norm.get("sm") or None,
            "rsm": norm.get("rsm") or None,
            "srsm": norm.get("srsm") or None,
            "zonal_head": norm.get("zonal_head") or None,
            "branch": norm.get("branch") or None,
            "city": norm.get("city") or None,
            "valid_from": vf,
        })
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has a header but no data rows")
    return rows


@router.post("", dependencies=[Depends(require_admin)])
def upload_hierarchy(
    file: UploadFile = File(...),
    repo: Repo = Depends(get_repo),
) -> dict:
    rows = _parse_csv(file.file.read())
    tenant_id = _tenant_id(repo)
    upload_id = uuid.uuid4().hex

    repo.replace_hierarchy(tenant_id, rows, upload_id)
    status = repo.hierarchy_status(tenant_id)
    return {
        "upload_id": upload_id,
        "row_count": len(rows),
        "match_rate_preview": status["match_rate"],
        "matched": status["matched"],
        "unmapped": status["unmapped"],
    }


@router.get("/status", dependencies=[Depends(require_admin)])
def hierarchy_status(repo: Repo = Depends(get_repo)) -> dict:
    return repo.hierarchy_status(_tenant_id(repo))


@router.get("/template", dependencies=[Depends(require_admin)])
def hierarchy_template() -> dict:
    return {"columns": list(_HEADER), "example": {
        "agent_id": "REP-1", "sm": "Sam", "rsm": "Ravi", "srsm": "Sr1",
        "zonal_head": "ZoneN", "branch": "North", "city": "Delhi",
        "valid_from": "2026-01-01",
    }}
