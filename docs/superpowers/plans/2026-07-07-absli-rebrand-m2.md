# ABSLI-first Rebrand + M2 Adjudication Spine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ProofLens read as a product built for Aditya Birla Sun Life Insurance (ABSLI) and make the Review Queue work end-to-end (real moderator decisions persisted + audited).

**Architecture:** Backend adds four nullable review columns to `results`, a `record_review` repo method that both updates the result and writes an `audit_log` row, and a `POST /v1/results/{id}/review` endpoint; read endpoints surface a `review` block. Frontend consumes that block (live Review Queue with keyboard triage, review status on Verdict Detail) and flips the chrome to ABSLI-first (properly-fitted tenant logo + "Powered by ProofLens" engine credit).

**Tech Stack:** FastAPI (src-layout, run with `PYTHONPATH=src`), SQLAlchemy + Alembic, Pydantic v2, pytest + FastAPI `TestClient` (fully offline via `InMemoryRepo`); Next.js 15 App Router, TypeScript, Tailwind, react-query.

## Global Constraints

- Backend runs with `PYTHONPATH=src`; test command is `PYTHONPATH=src .venv/bin/python -m pytest`.
- Frontend lives in `frontend/`; verify with `npm run lint` and `npm run build` from that dir.
- Tenant `slug` stays `"dev"` (internal id). Never rename the slug or change `DEFAULT_TENANT`.
- Review decision vocabulary is exactly: `approve | reject | false_positive | escalate`. Copy verbatim; the client posts the field name `decision` (not `status`).
- Reviewer identity is the literal `"Demo Operator"` until SSO (M4). Do not invent auth.
- Reason/verdict text from the backend is verbatim — never rewrite it in the UI.
- Never commit API keys. No env changes are needed by this plan.
- Logo asset stays `/brand/abc-life-insurance.png` (the Aditya Birla Capital lockup); text labels read "Aditya Birla Sun Life Insurance".

---

### Task 1: Review block on `ResultView`

**Files:**
- Modify: `src/prooflens/service/views.py`
- Test: `tests/unit/test_result_view_review.py` (create)

**Interfaces:**
- Produces: `ResultView` gains optional fields `review_status: str | None`, `review_note: str | None`, `reviewed_at: str | None` (ISO 8601), `reviewer: str | None`; `to_dict()` emits key `"review"` = `{"status","note","reviewed_at","reviewer"}` when a decision exists, else `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_result_view_review.py`:

```python
"""ResultView.to_dict() surfaces a review block only once a decision exists."""

from __future__ import annotations

from prooflens.service.views import ResultView


def _view(**kw) -> ResultView:
    base = dict(
        id="r1", created_at="2026-07-07T00:00:00+00:00", tenant_id="t1",
        band="Suspect", score=20.0, reason="Suspect — designed graphic",
        reason_code="designed_graphic", rubric_version="v1",
    )
    base.update(kw)
    return ResultView(**base)


def test_review_is_none_when_undecided():
    assert _view().to_dict()["review"] is None


def test_review_block_present_after_decision():
    d = _view(
        review_status="approve", review_note="looks fine",
        reviewed_at="2026-07-07T01:00:00+00:00", reviewer="Demo Operator",
    ).to_dict()
    assert d["review"] == {
        "status": "approve",
        "note": "looks fine",
        "reviewed_at": "2026-07-07T01:00:00+00:00",
        "reviewer": "Demo Operator",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_result_view_review.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'review_status'`.

- [ ] **Step 3: Add the fields + review block**

In `src/prooflens/service/views.py`, inside `@dataclass ResultView`, add these fields after `rep_id: str | None = None`:

```python
    review_status: str | None = None   # approve|reject|false_positive|escalate; None = pending
    review_note: str | None = None
    reviewed_at: str | None = None     # ISO 8601
    reviewer: str | None = None
```

Then add `"review": self._review_dict(),` as the last entry of the dict returned by `to_dict()`, and add this method to the class:

```python
    def _review_dict(self) -> dict | None:
        if self.review_status is None:
            return None
        return {
            "status": self.review_status,
            "note": self.review_note,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_result_view_review.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/service/views.py tests/unit/test_result_view_review.py
git commit -m "feat(review): add review block to ResultView"
```

---

### Task 2: Repo seam — `record_review` + review filter (in-memory)

**Files:**
- Modify: `src/prooflens/service/repo.py`
- Test: `tests/unit/test_inmemory_review.py` (create)

**Interfaces:**
- Consumes: `ResultView` review fields (Task 1).
- Produces:
  - `Repo.record_review(self, result_id: str, decision: str, note: str | None, reviewer: str) -> ResultView | None` — sets the review fields on the stored result, appends an audit event, returns the updated view, or `None` if the id is unknown.
  - `Repo.list_results(..., review: str | None = None)` — `review="pending"` keeps only undecided rows; any other non-empty value matches `review_status` exactly.
  - `InMemoryRepo.audit_log: list[dict]` — each entry `{"event","tenant_id","job_id","detail"}`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_inmemory_review.py`:

```python
"""record_review updates the result, writes an audit entry, and filters."""

from __future__ import annotations

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.engine.types import CheckOutcome, Verdict
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo() -> InMemoryRepo:
    t = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    return InMemoryRepo([t])


def _verdict() -> Verdict:
    return Verdict(
        band="Suspect", score=20.0, reason="Suspect — designed graphic",
        reason_code="designed_graphic", rubric_version="v1",
        checks=[CheckOutcome(name="content", available=True, score=0.0, summary="x", metric=None, data={}, latency_ms=1.0)],
    )


def test_record_review_updates_and_audits():
    repo = _repo()
    rid = repo.record_result("t1", None, _verdict())
    view = repo.record_review(rid, "approve", "ok", "Demo Operator")
    assert view is not None
    assert view.review_status == "approve" and view.reviewer == "Demo Operator"
    assert view.reviewed_at is not None
    assert repo.audit_log[-1]["event"] == "review.decision"
    assert repo.audit_log[-1]["detail"]["decision"] == "approve"


def test_record_review_unknown_id_returns_none():
    assert _repo().record_review("nope", "approve", None, "Demo Operator") is None


def test_list_results_review_filter():
    repo = _repo()
    a = repo.record_result("t1", None, _verdict())
    repo.record_result("t1", None, _verdict())  # left pending
    repo.record_review(a, "reject", None, "Demo Operator")
    pending, _ = repo.list_results(review="pending")
    rejected, _ = repo.list_results(review="reject")
    assert len(pending) == 1 and pending[0].review_status is None
    assert len(rejected) == 1 and rejected[0].id == a
```

Note: confirm the `Verdict`/`CheckOutcome` constructor keyword names against `src/prooflens/engine/types.py` before running; adjust the test's `_verdict()` if the real signatures differ (do not change production code to fit a guessed signature).

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_inmemory_review.py -v`
Expected: FAIL — `AttributeError: 'InMemoryRepo' object has no attribute 'record_review'`.

- [ ] **Step 3: Extend the Protocol**

In `src/prooflens/service/repo.py`, in the `Repo` Protocol: change the `list_results` signature to include `review`, and add `record_review`. Replace the existing `list_results` protocol stub with:

```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
    ) -> tuple[list[ResultView], int]:
        """Newest-first page of results + total matching count.
        review="pending" => undecided only; other value => exact review_status match."""
        ...

    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        """Record a moderator decision on a result; write an audit event.
        Returns the updated view, or None if result_id is unknown."""
        ...
```

- [ ] **Step 4: Implement on `InMemoryRepo`**

In `InMemoryRepo.__init__`, after `self.results: list[ResultView] = []` add:

```python
        self.audit_log: list[dict] = []
```

Replace `InMemoryRepo.list_results` with:

```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
    ) -> tuple[list[ResultView], int]:
        rows = [r for r in self.results if band is None or r.band == band]
        if review == "pending":
            rows = [r for r in rows if r.review_status is None]
        elif review:
            rows = [r for r in rows if r.review_status == review]
        rows = list(reversed(rows))  # newest first
        return rows[offset : offset + limit], len(rows)
```

Add `record_review` (place it after `get_result`), importing nothing new — `datetime`/`UTC` are already imported at the top of the file:

```python
    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        view = next((r for r in self.results if r.id == result_id), None)
        if view is None:
            return None
        view.review_status = decision
        view.review_note = note
        view.reviewed_at = datetime.now(UTC).isoformat()
        view.reviewer = reviewer
        self.audit_log.append({
            "event": "review.decision",
            "tenant_id": view.tenant_id,
            "job_id": None,
            "detail": {"result_id": result_id, "decision": decision, "note": note, "reviewer": reviewer},
        })
        return view
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_inmemory_review.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/service/repo.py tests/unit/test_inmemory_review.py
git commit -m "feat(review): record_review + review filter on the repo seam"
```

---

### Task 3: `POST /v1/results/{id}/review` endpoint + read integration

**Files:**
- Modify: `src/prooflens/api/scoring.py`
- Test: `tests/integration/test_review_api.py` (create)

**Interfaces:**
- Consumes: `Repo.record_review` and `list_results(review=…)` (Task 2).
- Produces:
  - `POST /v1/results/{result_id}/review` — body `{"decision": "approve|reject|false_positive|escalate", "note"?: str}`; 200 returns the updated result dict (with `review` block); 404 unknown id; 422 invalid decision.
  - `GET /v1/results?review=…` filter (added to the existing list endpoint).

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_review_api.py`:

```python
"""POST /v1/results/{id}/review — records a decision, audits it, filters the queue.
Fully offline: InMemoryRepo + stub backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView
from tests.helpers import IMAGES_DIR


@pytest.fixture
def repo() -> InMemoryRepo:
    t = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={}, scoring=ScoringConfig())
    return InMemoryRepo([t])


@pytest.fixture
def client(repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app, raise_server_exceptions=False)


def _score(client) -> str:
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post("/v1/score", files={"image": ("m.jpg", fh.read(), "image/jpeg")})
    return r.json()["result_id"]


def test_review_records_and_returns_block(client):
    rid = _score(client)
    r = client.post(f"/v1/results/{rid}/review", json={"decision": "approve", "note": "ok"})
    assert r.status_code == 200
    review = r.json()["review"]
    assert review["status"] == "approve"
    assert review["reviewer"] == "Demo Operator"
    assert review["reviewed_at"] and review["note"] == "ok"


def test_review_unknown_result_404(client):
    r = client.post("/v1/results/does-not-exist/review", json={"decision": "approve"})
    assert r.status_code == 404


def test_review_invalid_decision_422(client):
    rid = _score(client)
    r = client.post(f"/v1/results/{rid}/review", json={"decision": "banana"})
    assert r.status_code == 422


def test_review_writes_audit_log(client, repo):
    rid = _score(client)
    client.post(f"/v1/results/{rid}/review", json={"decision": "reject"})
    assert repo.audit_log[-1]["event"] == "review.decision"
    assert repo.audit_log[-1]["detail"]["decision"] == "reject"


def test_results_review_filter_hides_actioned(client):
    rid = _score(client)
    client.post(f"/v1/results/{rid}/review", json={"decision": "approve"})
    pending = client.get("/v1/results", params={"review": "pending"}).json()
    assert all(i["review"] is None for i in pending["items"])
    assert rid not in [i["id"] for i in pending["items"]]


def test_get_result_includes_review_block(client):
    rid = _score(client)
    assert client.get(f"/v1/results/{rid}").json()["review"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_review_api.py -v`
Expected: FAIL — the review POST returns 404/405 (route missing) / `review` key absent.

- [ ] **Step 3: Add the endpoint + list filter**

In `src/prooflens/api/scoring.py`:

Add to the imports at the top (with the other `pydantic`/typing imports — add the line):

```python
from typing import Literal

from pydantic import BaseModel
```

Under `DEFAULT_TENANT = "dev"` add:

```python
REVIEWER = "Demo Operator"  # placeholder identity until SSO/RBAC (M4)


class ReviewBody(BaseModel):
    decision: Literal["approve", "reject", "false_positive", "escalate"]
    note: str | None = None
```

Change the `list_results` endpoint signature and call to thread `review`:

```python
@router.get("/v1/results")
def list_results(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    band: str | None = Query(None),
    review: str | None = Query(None),
    repo: Repo = Depends(get_repo),
) -> dict:
    items, total = repo.list_results(limit=limit, offset=offset, band=band, review=review)
    return {
        "items": [r.to_dict() for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
```

Add the review endpoint immediately after `get_result`:

```python
@router.post("/v1/results/{result_id}/review")
def review_result(
    result_id: str, body: ReviewBody, repo: Repo = Depends(get_repo)
) -> dict:
    """Record a moderator decision on a stored verdict (writes an audit event)."""
    view = repo.record_review(result_id, body.decision, body.note, REVIEWER)
    if view is None:
        raise HTTPException(status_code=404, detail=f"no result {result_id!r}")
    return view.to_dict()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_review_api.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_review_api.py
git commit -m "feat(review): POST /v1/results/{id}/review + ?review= filter"
```

---

### Task 4: Postgres persistence — columns, migration, seed rename

**Files:**
- Modify: `src/prooflens/db/models.py:122-136` (the `Result` model)
- Modify: `src/prooflens/db/repo.py`
- Modify: `src/prooflens/scripts/seed_dev_tenant.py` → actually `scripts/seed_dev_tenant.py`
- Create: `migrations/versions/0002_review_and_absli_rename.py`

**Interfaces:**
- Consumes: `AuditLog`, `Result` ORM models; `ResultView` review fields (Task 1).
- Produces: `PostgresRepo.record_review(...)` and `list_results(..., review=…)` matching the Protocol from Task 2; four nullable `results` columns; the seeded tenant renamed to ABSLI.

Note: this task has no offline pytest (the suite uses `InMemoryRepo`; there is no local Postgres). Verify by import/compile and Alembic offline SQL render. The behavior is already covered functionally through the in-memory path in Tasks 2–3.

- [ ] **Step 1: Add ORM columns**

In `src/prooflens/db/models.py`, inside `class Result`, after the `created_at` column add:

```python
    review_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
```

- [ ] **Step 2: Implement `record_review` + filter + view on `PostgresRepo`**

In `src/prooflens/db/repo.py`:

Change the imports:
- `from datetime import UTC, datetime` (add this line near the top, after `import uuid`).
- `from .models import Job, Result, Tenant` → `from .models import AuditLog, Job, Result, Tenant`.

Replace `list_results` signature/body to add the `review` filter (keep the existing job-trail logic below unchanged):

```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None,
    ) -> tuple[list[ResultView], int]:
        query = self._session.query(Result)
        if band:
            query = query.filter(Result.band == band)
        if review == "pending":
            query = query.filter(Result.review_status.is_(None))
        elif review:
            query = query.filter(Result.review_status == review)
        total = query.count()
        rows = (
            query.order_by(Result.created_at.desc()).offset(offset).limit(limit).all()
        )
        job_ids = [r.job_id for r in rows if r.job_id is not None]
        jobs = (
            {j.id: j for j in self._session.query(Job).filter(Job.id.in_(job_ids)).all()}
            if job_ids
            else {}
        )
        views = [self._to_view(r, jobs.get(r.job_id) if r.job_id else None) for r in rows]
        return views, total
```

Add `record_review` after `get_result`:

```python
    def record_review(
        self, result_id: str, decision: str, note: str | None, reviewer: str
    ) -> ResultView | None:
        try:
            rid = uuid.UUID(result_id)
        except (ValueError, AttributeError):
            return None
        row = self._session.get(Result, rid)
        if row is None:
            return None
        row.review_status = decision
        row.review_note = note
        row.reviewed_at = datetime.now(UTC)
        row.reviewer = reviewer
        self._session.add(AuditLog(
            tenant_id=row.tenant_id,
            job_id=row.job_id,
            event="review.decision",
            detail={"result_id": str(row.id), "decision": decision, "note": note, "reviewer": reviewer},
        ))
        self._session.flush()
        job = self._session.get(Job, row.job_id) if row.job_id else None
        return self._to_view(row, job)
```

In `_to_view`, add the review kwargs to the `ResultView(...)` construction (after `rep_id=payload.get("rep_id")`):

```python
            review_status=r.review_status,
            review_note=r.review_note,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            reviewer=r.reviewer,
```

- [ ] **Step 3: Write the Alembic migration**

Create `migrations/versions/0002_review_and_absli_rename.py`:

```python
"""results review columns + rename seeded demo tenant to ABSLI

Revision ID: 0002_review_and_absli_rename
Revises: 0001_initial
Create Date: 2026-07-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_review_and_absli_rename"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("review_status", sa.String(24), nullable=True))
    op.add_column("results", sa.Column("review_note", sa.String(500), nullable=True))
    op.add_column("results", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("results", sa.Column("reviewer", sa.String(120), nullable=True))
    # Rename the seeded demo tenant to the real ABSLI identity (idempotent).
    op.execute(
        "UPDATE tenants SET name = 'Aditya Birla Sun Life Insurance' "
        "WHERE slug = 'dev' AND name = 'Dev Tenant'"
    )


def downgrade() -> None:
    op.drop_column("results", "reviewer")
    op.drop_column("results", "reviewed_at")
    op.drop_column("results", "review_note")
    op.drop_column("results", "review_status")
    op.execute(
        "UPDATE tenants SET name = 'Dev Tenant' "
        "WHERE slug = 'dev' AND name = 'Aditya Birla Sun Life Insurance'"
    )
```

- [ ] **Step 4: Update the seed script for fresh databases**

In `scripts/seed_dev_tenant.py`, change `name="Dev Tenant",` → `name="Aditya Birla Sun Life Insurance",`.

- [ ] **Step 5: Verify compile + migration graph**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "import prooflens.db.repo, prooflens.db.models; import importlib.util, pathlib; \
spec=importlib.util.spec_from_file_location('m0002','migrations/versions/0002_review_and_absli_rename.py'); \
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('rev', m.revision, 'down', m.down_revision)"
PYTHONPATH=src .venv/bin/python -m alembic history 2>/dev/null | head || echo "alembic history needs DATABASE_URL — skip if unset"
```
Expected: prints `rev 0002_review_and_absli_rename down 0001_initial`; no import errors.

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: all pass (Postgres path unexercised offline, but imports must stay clean).

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/db/models.py src/prooflens/db/repo.py scripts/seed_dev_tenant.py migrations/versions/0002_review_and_absli_rename.py
git commit -m "feat(review): postgres review columns, migration, ABSLI tenant rename"
```

---

### Task 5: Frontend review types + client

**Files:**
- Modify: `frontend/src/lib/api/types.ts:112` (the `ReviewDecision` type) and `ResultItem`
- Modify: `frontend/src/lib/api/client.ts:69-75`

**Interfaces:**
- Produces: `ReviewDecision` includes `"escalate"`; new `ReviewBlock` interface; `ResultItem.review?: ReviewBlock | null`; `api.reviewDecision` returns `Promise<ResultItem>`.

- [ ] **Step 1: Extend the types**

In `frontend/src/lib/api/types.ts`:

Replace `export type ReviewDecision = "approve" | "reject" | "false_positive";` with:

```typescript
export type ReviewDecision = "approve" | "reject" | "false_positive" | "escalate";

export interface ReviewBlock {
  status: ReviewDecision;
  note: string | null;
  reviewed_at: string | null;
  reviewer: string | null;
}
```

Add a field to `ResultItem` (after `checks: CheckOutcome[];`):

```typescript
  // Present once a moderator has actioned this result; null/absent while pending.
  review?: ReviewBlock | null;
```

- [ ] **Step 2: Update the client method**

In `frontend/src/lib/api/client.ts`, replace the `reviewDecision` method (and its stale comment) with:

```typescript
  // Record a moderator decision. Returns the updated result (with a `review` block).
  async reviewDecision(id: string, decision: ReviewDecision, note?: string): Promise<ResultItem> {
    const { data } = await http.post(`/v1/results/${encodeURIComponent(id)}/review`, {
      decision,
      note,
    });
    return data;
  },
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run lint`
Expected: no errors from these files (`ResultItem` import already present in `client.ts`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/client.ts
git commit -m "feat(review): frontend review types + live client method"
```

---

### Task 6: Review Queue goes live (real decisions + keyboard triage)

**Files:**
- Modify: `frontend/src/app/(app)/review/page.tsx`
- Modify: `frontend/src/components/review/ReviewCard.tsx`

**Interfaces:**
- Consumes: `api.reviewDecision` (Task 5), `useResults` filtering on `review`.
- Produces: a working queue — decisions persist, actioned items leave, `A/R/F/E` keyboard shortcuts act on the focused card, focus ring on the active card.

- [ ] **Step 1: Rewrite `ReviewCard`**

Replace `frontend/src/components/review/ReviewCard.tsx` with:

```tsx
"use client";

import { ArrowUpCircle, Check, CircleSlash, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StateIcon } from "@/components/verdict/StateIcon";
import { VerdictBadge } from "@/components/verdict/VerdictBadge";
import type { ResultItem, ReviewDecision } from "@/lib/api/types";
import { CHECK_LABEL, checkConfidence, checkState } from "@/lib/verdict";
import { cn, formatRelative } from "@/lib/utils";

export function ReviewCard({
  item,
  onDecide,
  status,
  focused = false,
}: {
  item: ResultItem;
  onDecide: (d: ReviewDecision) => void;
  status: "idle" | "pending";
  focused?: boolean;
}) {
  const flags = item.checks
    .map((c) => ({ c, s: checkState(c) }))
    .filter((x) => x.s === "fail" || x.s === "warn")
    .sort((a, b) => (a.s === "fail" ? -1 : 1) - (b.s === "fail" ? -1 : 1));

  const busy = status === "pending";

  return (
    <Card
      className={cn(
        "flex flex-col gap-4 p-5 transition-shadow",
        focused && "ring-2 ring-brand-crimson",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <VerdictBadge band={item.band} />
          <span className="text-body-sm tabular-nums text-text-muted">{Math.round(item.score)}/100</span>
        </div>
        <span className="text-caption text-text-muted">{formatRelative(item.created_at)}</span>
      </div>

      <p className="text-body font-medium leading-snug text-text">{item.reason}</p>

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
        <Button variant="secondary" onClick={() => onDecide("approve")} disabled={busy}>
          <Check size={15} />
          Approve
        </Button>
        <Button variant="danger" onClick={() => onDecide("reject")} disabled={busy}>
          <X size={15} />
          Reject
        </Button>
        <Button variant="ghost" onClick={() => onDecide("false_positive")} disabled={busy}>
          <CircleSlash size={15} />
          False positive
        </Button>
        <Button variant="ghost" onClick={() => onDecide("escalate")} disabled={busy}>
          <ArrowUpCircle size={15} />
          Escalate
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Rewrite the Review page**

Replace `frontend/src/app/(app)/review/page.tsx` with:

```tsx
"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

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

  const queue: ResultItem[] = (data?.items ?? [])
    .filter((r) => r.band !== "Clear" && !r.review)
    .sort((a, b) => BAND_ORDER[a.band] - BAND_ORDER[b.band]);

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
  }, [focusIdx]);

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
```

- [ ] **Step 3: Confirm `useResults` accepts `review` and `Toast` supports `error`**

`useResults(params)` forwards `params` verbatim to `api.results` and the `/v1/results` query string, so `review: "pending"` works without a hook change — but confirm by reading `frontend/src/lib/api/hooks.ts` and `client.ts`'s `results()` (the `params` object is spread into the axios `params`). Also confirm the `useToast` `kind` union includes `"error"` in `frontend/src/components/ui/Toast.tsx`; if it only supports `"success" | "info"`, use `kind: "info"` for the error toast instead.

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: compiles with no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/\(app\)/review/page.tsx frontend/src/components/review/ReviewCard.tsx
git commit -m "feat(review): live Review Queue with keyboard triage"
```

---

### Task 7: Verdict Detail shows the review outcome

**Files:**
- Modify: `frontend/src/app/(app)/verdict/[id]/page.tsx`

**Interfaces:**
- Consumes: `ResultItem.review` (Task 5).
- Produces: a "Moderator review" card on the detail page when `r.review` is present.

- [ ] **Step 1: Add the review card**

In `frontend/src/app/(app)/verdict/[id]/page.tsx`, add this block immediately after the "Capture context" `</Card>` (before the "Full evidence" card):

```tsx
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
```

(`Card`, `CardHeader`, `Field`, and `formatDateTime` are already imported/defined in this file.)

- [ ] **Step 2: Typecheck + build**

Run: `cd frontend && npm run build`
Expected: compiles clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\(app\)/verdict/\[id\]/page.tsx
git commit -m "feat(review): show moderator decision on Verdict Detail"
```

---

### Task 8: `TenantLogo` — fit the ABSLI logo properly

**Files:**
- Create: `frontend/src/components/brand/TenantLogo.tsx`

**Interfaces:**
- Produces: `TenantLogo({ size?: "md" | "sm", className?: string })` — renders `/brand/abc-life-insurance.png` inside a horizontal white card sized to the logo's real aspect ratio (height-constrained, width auto, padded, no clipping), with an "ABSLI" text fallback on image error.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/brand/TenantLogo.tsx`:

```tsx
"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The ABSLI tenant logo, fitted to its real ~2:1 proportions. The source PNG is
 * a wide horizontal lockup, so it is rendered in a height-constrained, width-auto
 * white card (object-contain, padded, NOT clipped) — never forced into a square.
 */
export function TenantLogo({
  size = "md",
  className,
}: {
  size?: "md" | "sm";
  className?: string;
}) {
  const [ok, setOk] = useState(true);
  const box = size === "md" ? "h-11 px-3" : "h-8 px-2";
  const img = size === "md" ? "max-h-6" : "max-h-4";

  if (!ok) {
    return (
      <span
        className={cn(
          "inline-grid place-items-center rounded-md bg-white ring-1 ring-border",
          box,
          className,
        )}
      >
        <span className="text-body-sm font-bold text-brand-crimson">ABSLI</span>
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md bg-white ring-1 ring-border",
        box,
        className,
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/abc-life-insurance.png"
        alt="Aditya Birla Sun Life Insurance"
        className={cn("w-auto object-contain", img)}
        onError={() => setOk(false)}
      />
    </span>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run lint`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/brand/TenantLogo.tsx
git commit -m "feat(brand): fitted ABSLI TenantLogo (no square clipping)"
```

---

### Task 9: ABSLI-first chrome

**Files:**
- Create: `frontend/src/components/brand/AbsliMasthead.tsx`
- Create: `frontend/src/components/brand/PoweredByProofLens.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Delete: `frontend/src/components/brand/Brandmark.tsx`, `frontend/src/components/brand/TenantSwitcher.tsx`
- Modify: `frontend/src/app/layout.tsx:9` (metadata title)
- Modify: `frontend/src/app/(app)/settings/page.tsx:126-131` (org footer)

**Interfaces:**
- Consumes: `TenantLogo` (Task 8).
- Produces: ABSLI-primary sidebar masthead + a muted "Powered by ProofLens" footer credit; `TenantSwitcher`/`Brandmark` removed.

- [ ] **Step 1: Create `AbsliMasthead`**

Create `frontend/src/components/brand/AbsliMasthead.tsx`:

```tsx
import { TenantLogo } from "@/components/brand/TenantLogo";

/**
 * ABSLI-first identity for the app chrome. The tenant (Aditya Birla Sun Life
 * Insurance) is the primary brand; ProofLens is credited as the engine below
 * (see <PoweredByProofLens>).
 */
export function AbsliMasthead() {
  return (
    <div className="flex flex-col gap-2.5">
      <TenantLogo size="md" />
      <div className="leading-tight">
        <p className="text-body-sm font-semibold text-text">Aditya Birla Sun Life Insurance</p>
        <p className="text-caption text-text-muted">Capture Integrity workspace</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `PoweredByProofLens`**

Create `frontend/src/components/brand/PoweredByProofLens.tsx`:

```tsx
import { Aperture } from "lucide-react";

/** ProofLens as the engine credit under the ABSLI-first brand. */
export function PoweredByProofLens() {
  return (
    <div className="flex items-center gap-2">
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-brand-crimson text-white">
        <Aperture size={12} strokeWidth={2.5} />
      </span>
      <span className="text-caption text-text-muted">
        Powered by <span className="font-medium text-text-secondary">ProofLens</span> · Capture Integrity
      </span>
    </div>
  );
}
```

- [ ] **Step 3: Rewire the sidebar**

In `frontend/src/components/layout/Sidebar.tsx`:

Replace the two brand imports:

```tsx
import { Brandmark } from "@/components/brand/Brandmark";
import { TenantSwitcher } from "@/components/brand/TenantSwitcher";
```

with:

```tsx
import { AbsliMasthead } from "@/components/brand/AbsliMasthead";
import { PoweredByProofLens } from "@/components/brand/PoweredByProofLens";
```

Replace the masthead block:

```tsx
      {/* Co-brand masthead: ProofLens product mark + the active tenant. */}
      <div className="space-y-3 border-b border-border px-4 py-4">
        <Brandmark />
        <TenantSwitcher />
      </div>
```

with:

```tsx
      {/* ABSLI-first masthead: the tenant is the primary brand. */}
      <div className="border-b border-border px-4 py-4">
        <AbsliMasthead />
      </div>
```

Replace the footer block:

```tsx
      <div className="border-t border-border p-4">
        <p className="text-caption text-text-muted">Scores &amp; flags — never blocks.</p>
        <p className="text-caption text-text-muted">Images are never stored.</p>
      </div>
```

with:

```tsx
      <div className="space-y-2.5 border-t border-border p-4">
        <PoweredByProofLens />
        <p className="text-caption text-text-muted">Scores &amp; flags — never blocks. Images are never stored.</p>
      </div>
```

- [ ] **Step 4: Delete the obsolete brand components**

```bash
git rm frontend/src/components/brand/Brandmark.tsx frontend/src/components/brand/TenantSwitcher.tsx
```

- [ ] **Step 5: Update the browser title**

In `frontend/src/app/layout.tsx`, change:

```tsx
  title: "ProofLens — Capture Integrity",
```

to:

```tsx
  title: "ABSLI Capture Integrity · ProofLens",
```

- [ ] **Step 6: Fix the settings org footer**

In `frontend/src/app/(app)/settings/page.tsx`, replace the footer block (lines ~126–131):

```tsx
      <div className="flex items-center gap-3 text-caption text-text-muted">
        <Activity size={14} />
        <span>ProofLens · Capture Integrity — scores &amp; flags, never blocks. Images are never stored.</span>
        <Building2 size={14} className="ml-auto" />
        <span>ProofLens</span>
      </div>
```

with:

```tsx
      <div className="flex items-center gap-3 text-caption text-text-muted">
        <Activity size={14} />
        <span>Capture Integrity — scores &amp; flags, never blocks. Images are never stored.</span>
        <Building2 size={14} className="ml-auto" />
        <span>Aditya Birla Sun Life Insurance · powered by ProofLens</span>
      </div>
```

- [ ] **Step 7: Typecheck + build (catches any dangling import)**

Run: `cd frontend && npm run build`
Expected: compiles clean — no references to the deleted `Brandmark`/`TenantSwitcher` remain (grep as a guard: `grep -rn "Brandmark\|TenantSwitcher" frontend/src` returns nothing).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/brand/AbsliMasthead.tsx frontend/src/components/brand/PoweredByProofLens.tsx \
  frontend/src/components/layout/Sidebar.tsx frontend/src/app/layout.tsx frontend/src/app/\(app\)/settings/page.tsx
git commit -m "feat(brand): ABSLI-first chrome, ProofLens as engine credit"
```

---

## Final verification

- [ ] Backend: `PYTHONPATH=src .venv/bin/python -m pytest -q` — all pass.
- [ ] Frontend: `cd frontend && npm run lint && npm run build` — clean.
- [ ] Guard: `grep -rn "Brandmark\|TenantSwitcher\|Dev Tenant" frontend/src src scripts` — no stray references (the seed now says ABSLI).
- [ ] Manual smoke (optional, needs the API): score an image → open its Verdict Detail → it appears in Review Queue → press `A` → toast fires, card leaves the queue → reopen the verdict → "Moderator review" card shows "approve / Demo Operator".

## Deploy note

After merge, the live Render Postgres needs `alembic upgrade head` to apply `0002` (adds the review columns and renames the tenant). The `scripts/start-api.sh` migrate step runs this on deploy; confirm it completed before demoing the Review Queue.

## Self-review notes

- **Spec coverage:** §1 identity → Tasks 8, 9 (+ tenant rename in Task 4); §2 logo fit → Task 8; §3 tenant at source → Task 4 (migration + seed) and Task 9 (chrome, no API dependency for the name); §4 M2 → Tasks 1–7. Testing section → Tasks 1–3 tests. All covered.
- **Field-name pin:** endpoint body uses `decision` (Task 3), client posts `decision` (Task 5) — consistent, matches the spec risk callout.
- **Type consistency:** `record_review(result_id, decision, note, reviewer) -> ResultView | None` identical across Protocol (Task 2), InMemoryRepo (Task 2), PostgresRepo (Task 4). `review` block keys `status/note/reviewed_at/reviewer` identical across `ResultView._review_dict` (Task 1), `ReviewBlock` TS type (Task 5), and its consumers (Tasks 6–7). `ReviewDecision` includes `escalate` in both backend `Literal` and TS union.
