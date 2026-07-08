# Analytics + Team Hierarchy — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Additively extend the analytics + results API and add an effective-dated org-hierarchy dimension (rep → sm/rsm/srsm/zonal/branch/city), so the redesigned `/analytics` page can answer: is capture risk rising, what drives flags, which teams need attention — without changing any scoring/engine/webhook logic and without breaking any existing response key or the golden set.

**Architecture:** `rep_id`/`opportunity_id` are promoted from `Job.payload` to indexed `Result` columns (populated in `record_result`, backfilled by migration `0004`). A new tenant-scoped, effective-dated `hierarchy` table (also in `0004`) is loaded via CSV through NEW `Repo` methods (both `InMemoryRepo` + `PostgresRepo`) so analytics stays offline-testable. A pure Python resolver (`resolve_node`) does the effective-dated join; pure aggregation utils bucket the range results (daily/weekly/monthly), compute the previous-equal-length period, and group by node. The `analytics_summary` and `list_results` endpoints and `Repo.list_results` are extended additively (every existing key preserved). Admin gets `POST /v1/admin/hierarchy` + `GET /v1/admin/hierarchy/status`.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, Postgres (prod) / InMemoryRepo (tests), pytest, ruff, mypy. Zero new third-party dependencies (stdlib `csv` only).

## Global Constraints

- **Additive only.** Every existing response key on `/v1/analytics/summary`, `/v1/results`, and every result dict stays present and unchanged; the golden set (`tests/golden`) and `tests/unit/test_verdict_copy.py` invariants are preserved. New data is added alongside, never in place of, existing keys.
- **InMemory/Postgres parity.** Every new `Repo` method exists on BOTH `InMemoryRepo` (`src/prooflens/service/repo.py`) and `PostgresRepo` (`src/prooflens/db/repo.py`) with identical signatures and semantics. New behavior is unit-tested offline via `InMemoryRepo`.
- **Day-granular, UTC.** All date logic uses `datetime.now(UTC).date()`; ranges are the existing half-open `[start, end)` from `resolve_range`. Effective-dating compares `valid_from` (a `date`) against the result's scored `date`.
- **Read paths stay non-tenant-scoped** (pre-existing single-demo-tenant assumption; logged as a known gap in the spec §0-decision-5). The `hierarchy` TABLE is tenant-keyed and its Repo queries ARE tenant-scoped.
- **CSV upload only** (stdlib `csv`) — no new dependency in a memory-sensitive service. XLSX deferred (logged).
- **ID normalization is one shared util** (`normalize_id`: `.strip().upper()`, `None`/blank → `None`), applied identically at webhook ingestion (`WebhookPayload.rep_id` validator) and at hierarchy upload (every `agent_id`) and at the `rep_id` results filter.
- **CI lints all four paths:** the final gate runs `ruff check src tests scripts migrations` AND `mypy src` — a narrower local lint has passed while CI failed. Both must be clean.
- **ResultView is a non-frozen `@dataclass`** — tests may direct-append backdated rows to `repo.results` (setting `created_at`, `rep_id`, `band`, `score`, `reason_code`) to exercise date/hierarchy logic without scoring images.
- **Migration head is `0003_default_vision_groq`.** The single new migration is `0004_*` with `down_revision = "0003_default_vision_groq"`.
- **Analytics aggregation stays Python-over-`list_results`-items** (buckets, group_by, deltas). No raw-SQL aggregation.
- **Every code step below contains complete code.** Use `.venv/bin/python -m pytest ...` for tests (matching the repo's existing plan convention).

---

### Task 1: `normalize_id` shared util + `WebhookPayload.rep_id` validator

**Files:**
- Create: `src/prooflens/service/ids.py`
- Modify: `src/prooflens/api/schemas.py` (add a `field_validator` on `rep_id`)
- Test: `tests/unit/test_ids.py` (create), `tests/integration/test_webhook_e2e.py` (add one case) — the webhook path already exists.

**Interfaces:**
- Produces: `normalize_id(s: str | None) -> str | None` — `s.strip().upper()`, returning `None` for `None`/blank/whitespace-only.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ids.py
from __future__ import annotations

from prooflens.service.ids import normalize_id


def test_normalize_strips_and_uppercases():
    assert normalize_id("  rep-42 ") == "REP-42"
    assert normalize_id("abc") == "ABC"


def test_normalize_blank_and_none_become_none():
    assert normalize_id(None) is None
    assert normalize_id("") is None
    assert normalize_id("   ") is None
    assert normalize_id("\t\n") is None


def test_normalize_is_idempotent():
    once = normalize_id("  Rep-7 ")
    assert normalize_id(once) == once == "REP-7"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_ids.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.service.ids'`

- [ ] **Step 3: Implement the util**

```python
# src/prooflens/service/ids.py
"""One shared ID-normalization rule, used at BOTH webhook ingestion and
hierarchy upload so a rep_id always compares equal regardless of source
casing/whitespace. Single source of truth (spec §0c)."""

from __future__ import annotations


def normalize_id(s: str | None) -> str | None:
    """Canonical form of a rep/agent id: trimmed + upper-cased. Blank/None -> None."""
    if s is None:
        return None
    stripped = s.strip()
    return stripped.upper() if stripped else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_ids.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Apply the validator to `WebhookPayload.rep_id`**

In `src/prooflens/api/schemas.py`, extend the imports and add the validator. Replace the import line and the `WebhookPayload` class body:

```python
from pydantic import BaseModel, Field, field_validator

from ..service.ids import normalize_id


class WebhookPayload(BaseModel):
    event_id: str = Field(..., description="Idempotency key — one job per (tenant, event).")
    opportunity_id: str = Field(..., description="LSQ opportunity/lead id to write back to.")
    rep_id: str | None = Field(default=None, description="Field rep id (uniqueness trail).")
    captured_at: str | None = Field(default=None, description="Capture timestamp, if provided.")

    # Image: inline bytes now; by-reference fetch is a Phase 3 TODO.
    image_base64: str | None = Field(default=None)
    image_url: str | None = Field(default=None)

    @field_validator("rep_id")
    @classmethod
    def _normalize_rep_id(cls, v: str | None) -> str | None:
        # Normalize at ingestion so every stored rep_id is already canonical
        # (matches the hierarchy upload's normalization — one shared rule).
        return normalize_id(v)
```

Leave `WebhookAck` unchanged.

- [ ] **Step 6: Write the webhook integration assertion**

Add to `tests/integration/test_webhook_e2e.py` (append; it already builds a signed webhook — reuse its existing helpers/fixtures for signing + posting). If the file's helper is named differently, adapt the call but keep the assertion:

```python
def test_webhook_normalizes_rep_id_into_job_payload(client_and_repo_or_similar):
    # A mixed-case, padded rep_id is canonicalized ("  rep-9 " -> "REP-9")
    # before it is enqueued, so downstream results/hierarchy compare equal.
    # (Use this file's existing signed-post helper; assert on the enqueued job payload.)
    ...
```

If adding a full signed-post case is heavier than the deliverable warrants, instead assert directly on the model (this is sufficient and offline):

```python
# tests/unit/test_ids.py (append) — model-level proof the validator is wired
from prooflens.api.schemas import WebhookPayload


def test_webhook_payload_normalizes_rep_id():
    p = WebhookPayload(event_id="e1", opportunity_id="o1", rep_id="  rep-9 ")
    assert p.rep_id == "REP-9"
    p2 = WebhookPayload(event_id="e2", opportunity_id="o2", rep_id="   ")
    assert p2.rep_id is None
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_ids.py -v`
Expected: PASS (all)

- [ ] **Step 8: Commit**

```bash
git add src/prooflens/service/ids.py src/prooflens/api/schemas.py tests/unit/test_ids.py
git commit -m "feat(ids): shared normalize_id + WebhookPayload.rep_id validator"
```

---

### Task 2: Promote `rep_id`/`opportunity_id` to `Result` columns (+ populate in record_result)

Adds the ORM columns and the composite index, populates them in BOTH repos' `record_result`, and makes `PostgresRepo._to_view` prefer the columns (Job-join fallback kept for legacy nulls). The alembic migration is written in Task 3 (both column-adds, the hierarchy table, and the backfill land in one `0004` migration — they touch the same file, so keep them in one deliverable's migration but split the test cycles).

**Files:**
- Modify: `src/prooflens/db/models.py` (`Result`: add two columns + index)
- Modify: `src/prooflens/db/repo.py` (`record_result` sets columns; `_to_view` prefers columns)
- Test: `tests/unit/test_db_models.py` (append — ORM mapping/index, offline, no DB)

**Interfaces:**
- Consumes: `Result` ORM model.
- Produces: `Result.rep_id: str | None`, `Result.opportunity_id: str | None` columns; index `ix_results_tenant_rep` on `(tenant_id, rep_id)`. `PostgresRepo.record_result(...)` now persists both; `_to_view` reads `r.rep_id`/`r.opportunity_id`, falling back to the job payload only when the column is `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_db_models.py (append)
def test_result_has_rep_and_opportunity_columns():
    from prooflens.db.models import Result
    cols = Result.__table__.c
    assert "rep_id" in cols and "opportunity_id" in cols
    assert cols.rep_id.nullable is True
    assert cols.opportunity_id.nullable is True


def test_results_have_tenant_rep_index():
    from prooflens.db.models import Result
    idx = {i.name: [c.name for c in i.columns] for i in Result.__table__.indexes}
    assert "ix_results_tenant_rep" in idx
    assert idx["ix_results_tenant_rep"] == ["tenant_id", "rep_id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_db_models.py -k "rep_and_opportunity or tenant_rep_index" -v`
Expected: FAIL — `AssertionError` (columns/index absent).

- [ ] **Step 3: Add the columns + index to the `Result` model**

In `src/prooflens/db/models.py`, in class `Result`, add a `__table_args__` and the two columns. Insert after the `__tablename__` line:

```python
class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        # Effective-dated hierarchy join + rep_id filtering are per (tenant, rep).
        Index("ix_results_tenant_rep", "tenant_id", "rep_id"),
    )
```

And add the two columns immediately after the `job_id` column (before `band`):

```python
    rep_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

(`Index` and `String` are already imported in this module.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_db_models.py -k "rep_and_opportunity or tenant_rep_index" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Populate columns in `PostgresRepo.record_result` + prefer them in `_to_view`**

In `src/prooflens/db/repo.py`, in `record_result`, add the two fields to the `Result(...)` construction (they arrive already-normalized from the webhook; normalize defensively for the direct path too):

```python
    def record_result(
        self,
        tenant_id: str,
        job_id: str | None,
        verdict: Verdict,
        *,
        opportunity_id: str | None = None,
        rep_id: str | None = None,
    ) -> str:
        from ..service.ids import normalize_id

        row = Result(
            tenant_id=uuid.UUID(tenant_id),
            job_id=uuid.UUID(job_id) if job_id else None,
            rep_id=normalize_id(rep_id),
            opportunity_id=opportunity_id,
            band=verdict.band,
            score=int(round(verdict.score)),
            reason=verdict.reason,
            reason_code=verdict.reason_code,
            rubric_version=verdict.rubric_version,
            checks=[c.to_dict() for c in verdict.checks],
        )
        self._session.add(row)
        self._session.flush()
        return str(row.id)
```

In `_to_view`, prefer the columns, falling back to the job payload only when the column is `None` (legacy rows before backfill):

```python
    @staticmethod
    def _to_view(r: Result, job: Job | None) -> ResultView:
        # Prefer the promoted columns; fall back to the originating job payload
        # only for legacy rows the backfill did not reach (defence in depth).
        payload = (job.payload or {}) if job else {}
        rep_id = r.rep_id if r.rep_id is not None else payload.get("rep_id")
        opportunity_id = (
            r.opportunity_id if r.opportunity_id is not None else payload.get("opportunity_id")
        )
        return ResultView(
            id=str(r.id),
            created_at=r.created_at.isoformat() if r.created_at else "",
            tenant_id=str(r.tenant_id),
            band=r.band,
            score=float(r.score),
            reason=r.reason,
            reason_code=r.reason_code,
            rubric_version=r.rubric_version,
            checks=list(r.checks or []),
            processing_ms=round(
                sum(float(c.get("latency_ms") or 0.0) for c in (r.checks or [])), 1
            ),
            source="webhook" if r.job_id else "direct",
            opportunity_id=opportunity_id,
            rep_id=rep_id,
            review_status=r.review_status,
            review_note=r.review_note,
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
            reviewer=r.reviewer,
        )
```

(`InMemoryRepo.record_result` already stores `rep_id`/`opportunity_id` on the `ResultView` directly — no change needed there for this task, but Task 4/6 rely on it. Normalize the InMemory side too for parity: in `src/prooflens/service/repo.py` `record_result`, wrap with `normalize_id` — add `from .ids import normalize_id` at module top and change `rep_id=rep_id,` to `rep_id=normalize_id(rep_id),`.)

- [ ] **Step 6: Run the DB-model tests + the existing scoring/webhook suite (no behavior regressions)**

Run: `.venv/bin/python -m pytest tests/unit/test_db_models.py tests/integration/test_scoring_api.py tests/integration/test_review_api.py -q`
Expected: PASS (existing tests unaffected; InMemory result dicts unchanged).

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/db/models.py src/prooflens/db/repo.py src/prooflens/service/repo.py tests/unit/test_db_models.py
git commit -m "feat(results): promote rep_id/opportunity_id to indexed Result columns"
```

---

### Task 3: Hierarchy ORM model + the single `0004` migration (columns + table + backfill)

**Files:**
- Modify: `src/prooflens/db/models.py` (add `Hierarchy` model)
- Create: `migrations/versions/0004_hierarchy_and_result_ids.py`
- Test: `tests/unit/test_db_models.py` (append — Hierarchy mapping + index)

**Interfaces:**
- Produces: ORM `Hierarchy` with columns `id, tenant_id, agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from (date), uploaded_at, upload_id`; index `ix_hierarchy_lookup` on `(tenant_id, agent_id, valid_from)`. Migration `0004_hierarchy_and_result_ids` (down_revision `0003_default_vision_groq`) adds `results.rep_id`/`results.opportunity_id` + `ix_results_tenant_rep`, creates `hierarchy` + its index, and backfills `results.rep_id`/`opportunity_id` from `jobs.payload`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_db_models.py (append)
def test_hierarchy_model_columns_and_index():
    from prooflens.db.models import Hierarchy
    cols = Hierarchy.__table__.c
    for name in (
        "id", "tenant_id", "agent_id", "sm", "rsm", "srsm",
        "zonal_head", "branch", "city", "valid_from", "uploaded_at", "upload_id",
    ):
        assert name in cols, f"missing column {name}"
    assert str(cols.valid_from.type) == "DATE"
    idx = {i.name: [c.name for c in i.columns] for i in Hierarchy.__table__.indexes}
    assert idx["ix_hierarchy_lookup"] == ["tenant_id", "agent_id", "valid_from"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_db_models.py -k hierarchy_model -v`
Expected: FAIL — `ImportError: cannot import name 'Hierarchy'`

- [ ] **Step 3: Add the `Hierarchy` model**

In `src/prooflens/db/models.py`, add `Date` to the sqlalchemy import block (the line importing `BigInteger, Boolean, DateTime, ...`), then append a new model at the end of the file:

```python
class Hierarchy(Base):
    """Effective-dated org map: one row per (agent, version). A result maps to
    the row with agent_id == result.rep_id and the LATEST valid_from <= scored
    date. Tenant-scoped; org changes never rewrite historical reports."""

    __tablename__ = "hierarchy"
    __table_args__ = (
        Index("ix_hierarchy_lookup", "tenant_id", "agent_id", "valid_from"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    agent_id: Mapped[str] = mapped_column(String(200))
    sm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rsm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    srsm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    zonal_head: Mapped[str | None] = mapped_column(String(200), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    upload_id: Mapped[str] = mapped_column(String(64))
```

Add `date` to the `from datetime import ...` line at the top of the module (it currently imports only `datetime`):

```python
from datetime import date, datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_db_models.py -k hierarchy_model -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Write the `0004` migration**

```python
# migrations/versions/0004_hierarchy_and_result_ids.py
"""hierarchy table + promote rep_id/opportunity_id to Result columns (+ backfill)

Revision ID: 0004_hierarchy_and_result_ids
Revises: 0003_default_vision_groq
Create Date: 2026-07-08

Additive: adds two nullable columns to results (backfilled from jobs.payload),
a (tenant_id, rep_id) index, and the effective-dated hierarchy table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_hierarchy_and_result_ids"
down_revision = "0003_default_vision_groq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Promote rep_id / opportunity_id to real Result columns.
    op.add_column("results", sa.Column("rep_id", sa.String(200), nullable=True))
    op.add_column("results", sa.Column("opportunity_id", sa.String(200), nullable=True))
    op.create_index("ix_results_tenant_rep", "results", ["tenant_id", "rep_id"])

    # 2) Backfill from the originating job payload (normalized: trim + upper for rep_id).
    op.execute(
        """
        UPDATE results r
        SET rep_id = UPPER(TRIM(j.payload->>'rep_id')),
            opportunity_id = j.payload->>'opportunity_id'
        FROM jobs j
        WHERE r.job_id = j.id
          AND r.rep_id IS NULL
          AND NULLIF(TRIM(j.payload->>'rep_id'), '') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE results r
        SET opportunity_id = j.payload->>'opportunity_id'
        FROM jobs j
        WHERE r.job_id = j.id
          AND r.opportunity_id IS NULL
          AND NULLIF(TRIM(j.payload->>'opportunity_id'), '') IS NOT NULL
        """
    )

    # 3) Effective-dated hierarchy reference table.
    op.create_table(
        "hierarchy",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"), nullable=False,
        ),
        sa.Column("agent_id", sa.String(200), nullable=False),
        sa.Column("sm", sa.String(200), nullable=True),
        sa.Column("rsm", sa.String(200), nullable=True),
        sa.Column("srsm", sa.String(200), nullable=True),
        sa.Column("zonal_head", sa.String(200), nullable=True),
        sa.Column("branch", sa.String(200), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("upload_id", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_hierarchy_lookup", "hierarchy", ["tenant_id", "agent_id", "valid_from"]
    )


def downgrade() -> None:
    op.drop_index("ix_hierarchy_lookup", table_name="hierarchy")
    op.drop_table("hierarchy")
    op.drop_index("ix_results_tenant_rep", table_name="results")
    op.drop_column("results", "opportunity_id")
    op.drop_column("results", "rep_id")
```

- [ ] **Step 6: Verify the migration is importable + linear (head advances to 0004)**

Run:
```bash
.venv/bin/python -c "import migrations.versions.0004_hierarchy_and_result_ids as m; print(m.revision, m.down_revision)" 2>/dev/null \
  || PYTHONPATH=. .venv/bin/python -c "import importlib.util, pathlib; \
p=pathlib.Path('migrations/versions/0004_hierarchy_and_result_ids.py'); \
s=importlib.util.spec_from_file_location('m', p); mod=importlib.util.module_from_spec(s); s.loader.exec_module(mod); \
print(mod.revision, mod.down_revision)"
```
Expected: `0004_hierarchy_and_result_ids 0003_default_vision_groq`

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/db/models.py migrations/versions/0004_hierarchy_and_result_ids.py tests/unit/test_db_models.py
git commit -m "feat(db): Hierarchy model + 0004 migration (result id columns, backfill, hierarchy table)"
```

---

### Task 4: Pure effective-dated resolver `resolve_node`

**Files:**
- Create: `src/prooflens/service/hierarchy.py`
- Test: `tests/unit/test_hierarchy_resolver.py` (create)

**Interfaces:**
- Consumes: `normalize_id` (Task 1).
- Produces:
  - `HierarchyRow = dict` shape: `{agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from}` where `valid_from` is a `datetime.date`.
  - `NODE_FIELDS: tuple[str, ...] = ("sm", "rsm", "srsm", "zonal_head", "branch", "city")`.
  - `resolve_node(rows: list[dict], agent_id: str | None, scored_date: date) -> dict | None` — returns the row (a dict from `rows`) whose normalized `agent_id` matches the normalized argument AND has the latest `valid_from <= scored_date`; `None` when unmatched (→ the "Unmapped" node).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hierarchy_resolver.py
from __future__ import annotations

from datetime import date

from prooflens.service.hierarchy import NODE_FIELDS, resolve_node


def _row(agent, valid_from, **kw):
    base = {"agent_id": agent, "valid_from": valid_from}
    base.update(kw)
    return base


def test_resolve_none_agent_is_unmapped():
    assert resolve_node([_row("A1", date(2026, 1, 1), branch="North")], None, date(2026, 6, 1)) is None


def test_resolve_no_matching_agent_is_unmapped():
    rows = [_row("A1", date(2026, 1, 1), branch="North")]
    assert resolve_node(rows, "A2", date(2026, 6, 1)) is None


def test_resolve_picks_latest_valid_from_on_or_before_scored_date():
    rows = [
        _row("A1", date(2026, 1, 1), branch="North"),
        _row("A1", date(2026, 5, 1), branch="South"),   # rep moved on May 1
    ]
    # Before the move -> North
    assert resolve_node(rows, "A1", date(2026, 3, 15))["branch"] == "North"
    # On/after the move -> South
    assert resolve_node(rows, "A1", date(2026, 5, 1))["branch"] == "South"
    assert resolve_node(rows, "A1", date(2026, 7, 1))["branch"] == "South"


def test_resolve_before_earliest_valid_from_is_unmapped():
    rows = [_row("A1", date(2026, 5, 1), branch="South")]
    assert resolve_node(rows, "A1", date(2026, 1, 1)) is None


def test_resolve_normalizes_ids_on_both_sides():
    rows = [_row("REP-9", date(2026, 1, 1), branch="North")]
    assert resolve_node(rows, "  rep-9 ", date(2026, 6, 1))["branch"] == "North"


def test_node_fields_are_the_six_levels():
    assert NODE_FIELDS == ("sm", "rsm", "srsm", "zonal_head", "branch", "city")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_hierarchy_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.service.hierarchy'`

- [ ] **Step 3: Implement the resolver**

```python
# src/prooflens/service/hierarchy.py
"""Pure effective-dated hierarchy resolver + node vocabulary.

A result maps to the hierarchy row whose agent_id equals the result's rep_id
(normalized on both sides) and whose valid_from is the LATEST date on or before
the result's scored date. No match -> None (the "Unmapped" node). Effective-
dated so org changes never rewrite historical reports."""

from __future__ import annotations

from datetime import date

from .ids import normalize_id

# The six org levels a result can be grouped by, coarse -> fine is not implied.
NODE_FIELDS: tuple[str, ...] = ("sm", "rsm", "srsm", "zonal_head", "branch", "city")


def resolve_node(rows: list[dict], agent_id: str | None, scored_date: date) -> dict | None:
    """Return the effective hierarchy row for this agent at scored_date, or None.

    rows: hierarchy rows as dicts, each with at least "agent_id" (str) and
    "valid_from" (datetime.date). Picks the row with the latest valid_from that
    is <= scored_date among rows matching the normalized agent_id."""
    key = normalize_id(agent_id)
    if key is None:
        return None
    best: dict | None = None
    for row in rows:
        if normalize_id(row.get("agent_id")) != key:
            continue
        vf = row["valid_from"]
        if vf > scored_date:
            continue
        if best is None or vf > best["valid_from"]:
            best = row
    return best
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_hierarchy_resolver.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/service/hierarchy.py tests/unit/test_hierarchy_resolver.py
git commit -m "feat(hierarchy): pure effective-dated resolve_node + NODE_FIELDS"
```

---

### Task 5: Repo hierarchy methods on BOTH `InMemoryRepo` + `PostgresRepo`

**Files:**
- Modify: `src/prooflens/service/repo.py` (add 3 methods to the `Repo` protocol + `InMemoryRepo`)
- Modify: `src/prooflens/db/repo.py` (implement the 3 methods on `PostgresRepo`)
- Test: `tests/unit/test_repo_hierarchy.py` (create — offline, InMemory only)

**Interfaces:**
- Consumes: `resolve_node` is NOT needed here; `hierarchy_status`'s match-rate compares rep_ids seen in the last-90-day results against the current version's `agent_id` set (normalized).
- Produces (identical signatures on both repos):
  - `replace_hierarchy(self, tenant_id: str, rows: list[dict], upload_id: str) -> None` — atomically replaces this tenant's hierarchy with `rows`. Each row is a dict `{agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from}` (`valid_from` a `datetime.date`); `agent_id` is stored normalized.
  - `get_hierarchy_rows(self, tenant_id: str) -> list[dict]` — all current rows for the tenant as dicts with the same keys plus `upload_id`.
  - `hierarchy_status(self, tenant_id: str) -> dict` — `{upload_id, valid_from, row_count, match_rate, matched, unmapped}`. `valid_from` is the max `valid_from` in the current version (ISO string or None); `match_rate` is `matched / (matched + unmapped)` rounded to 3, over DISTINCT non-null rep_ids in the tenant's last-90-day results; `0.0` when there are no rep_ids. Empty hierarchy → `{upload_id: None, valid_from: None, row_count: 0, match_rate: 0.0, matched: 0, unmapped: <distinct rep count>}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_repo_hierarchy.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta, date

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant():
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _repo():
    return InMemoryRepo([_tenant()])


def _row(agent, vf, **kw):
    base = {"agent_id": agent, "sm": None, "rsm": None, "srsm": None,
            "zonal_head": None, "branch": None, "city": None, "valid_from": vf}
    base.update(kw)
    return base


def _result(rep_id, days_ago):
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return ResultView(id="x", created_at=ts, tenant_id="t1", band="Clear",
                      score=90.0, reason="r", reason_code="clear", rubric_version="v3",
                      rep_id=rep_id)


def test_replace_and_get_hierarchy_rows():
    repo = _repo()
    repo.replace_hierarchy("t1", [_row("A1", date(2026, 1, 1), branch="North")], "u1")
    rows = repo.get_hierarchy_rows("t1")
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "A1" and rows[0]["branch"] == "North"
    assert rows[0]["upload_id"] == "u1"


def test_replace_hierarchy_is_atomic_replace_and_normalizes_agent():
    repo = _repo()
    repo.replace_hierarchy("t1", [_row("  a1 ", date(2026, 1, 1))], "u1")
    repo.replace_hierarchy("t1", [_row("B2", date(2026, 2, 1))], "u2")
    rows = repo.get_hierarchy_rows("t1")
    assert [r["agent_id"] for r in rows] == ["B2"]        # u1 fully replaced
    repo.replace_hierarchy("t1", [_row(" a1 ", date(2026, 1, 1))], "u3")
    assert repo.get_hierarchy_rows("t1")[0]["agent_id"] == "A1"   # normalized on store


def test_hierarchy_status_match_rate_over_last_90_days():
    repo = _repo()
    # Results: A1 (matched), A2 (matched), A3 (unmapped), one old (ignored).
    repo.results.extend([
        _result("A1", 1), _result("A2", 10), _result("A3", 20),
        _result("A1", 5),                # duplicate rep -> distinct counts once
        _result("A9", 200),              # older than 90d -> excluded
    ])
    repo.replace_hierarchy("t1", [
        _row("A1", date(2026, 1, 1), valid_from=date(2026, 1, 1)),
        _row("A2", date(2026, 1, 2), valid_from=date(2026, 1, 2)),
    ], "u1")
    st = repo.hierarchy_status("t1")
    assert st["upload_id"] == "u1"
    assert st["row_count"] == 2
    assert st["matched"] == 2 and st["unmapped"] == 1      # A1,A2 matched; A3 unmapped
    assert st["match_rate"] == round(2 / 3, 3)


def test_hierarchy_status_empty_hierarchy():
    repo = _repo()
    repo.results.append(_result("A1", 1))
    st = repo.hierarchy_status("t1")
    assert st == {"upload_id": None, "valid_from": None, "row_count": 0,
                  "match_rate": 0.0, "matched": 0, "unmapped": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_repo_hierarchy.py -v`
Expected: FAIL — `AttributeError: 'InMemoryRepo' object has no attribute 'replace_hierarchy'`

- [ ] **Step 3: Add the three methods to the `Repo` protocol + `InMemoryRepo`**

In `src/prooflens/service/repo.py`, add to the `Repo` protocol (after `record_review`):

```python
    def replace_hierarchy(self, tenant_id: str, rows: list[dict], upload_id: str) -> None:
        """Atomically replace this tenant's hierarchy with rows.
        Each row: {agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from(date)}."""
        ...

    def get_hierarchy_rows(self, tenant_id: str) -> list[dict]:
        """Current hierarchy rows for the tenant (dicts incl. upload_id)."""
        ...

    def hierarchy_status(self, tenant_id: str) -> dict:
        """Current version + match rate vs distinct rep_ids in the last 90 days."""
        ...
```

Add an `_hierarchy` store to `InMemoryRepo.__init__` (after `self.audit_log = []`):

```python
        self._hierarchy: dict[str, list[dict]] = {}
```

And implement the methods on `InMemoryRepo` (after `record_review`, before `commit`). Add `from datetime import date, timedelta` usage — the module already imports `UTC, datetime`; extend to `from datetime import UTC, datetime, timedelta`:

```python
    def replace_hierarchy(self, tenant_id: str, rows: list[dict], upload_id: str) -> None:
        from .ids import normalize_id

        stored: list[dict] = []
        for r in rows:
            stored.append({
                "agent_id": normalize_id(r.get("agent_id")),
                "sm": r.get("sm"),
                "rsm": r.get("rsm"),
                "srsm": r.get("srsm"),
                "zonal_head": r.get("zonal_head"),
                "branch": r.get("branch"),
                "city": r.get("city"),
                "valid_from": r["valid_from"],
                "upload_id": upload_id,
            })
        self._hierarchy[tenant_id] = stored

    def get_hierarchy_rows(self, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self._hierarchy.get(tenant_id, [])]

    def hierarchy_status(self, tenant_id: str) -> dict:
        from .ids import normalize_id

        rows = self._hierarchy.get(tenant_id, [])
        cutoff = datetime.now(UTC) - timedelta(days=90)
        rep_ids: set[str] = set()
        for r in self.results:
            if r.tenant_id != tenant_id or not r.rep_id or not r.created_at:
                continue
            if datetime.fromisoformat(r.created_at) < cutoff:
                continue
            norm = normalize_id(r.rep_id)
            if norm is not None:
                rep_ids.add(norm)
        agents = {normalize_id(r["agent_id"]) for r in rows}
        matched = sum(1 for rid in rep_ids if rid in agents)
        unmapped = len(rep_ids) - matched
        total = matched + unmapped
        upload_id = rows[0]["upload_id"] if rows else None
        valid_from = max((r["valid_from"] for r in rows), default=None)
        return {
            "upload_id": upload_id,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "row_count": len(rows),
            "match_rate": round(matched / total, 3) if total else 0.0,
            "matched": matched,
            "unmapped": unmapped,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_repo_hierarchy.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Implement the same three methods on `PostgresRepo`**

In `src/prooflens/db/repo.py`, add `date, timedelta` to the datetime import (`from datetime import UTC, date, datetime, timedelta`), import the model (`from .models import AuditLog, Hierarchy, Job, Result, Tenant`), and add these methods (after `record_review`, before `commit`):

```python
    def replace_hierarchy(self, tenant_id: str, rows: list[dict], upload_id: str) -> None:
        from ..service.ids import normalize_id

        tid = uuid.UUID(tenant_id)
        self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).delete()
        for r in rows:
            self._session.add(Hierarchy(
                tenant_id=tid,
                agent_id=normalize_id(r.get("agent_id")),
                sm=r.get("sm"), rsm=r.get("rsm"), srsm=r.get("srsm"),
                zonal_head=r.get("zonal_head"), branch=r.get("branch"), city=r.get("city"),
                valid_from=r["valid_from"], upload_id=upload_id,
            ))
        self._session.flush()

    def get_hierarchy_rows(self, tenant_id: str) -> list[dict]:
        tid = uuid.UUID(tenant_id)
        rows = self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).all()
        return [{
            "agent_id": h.agent_id, "sm": h.sm, "rsm": h.rsm, "srsm": h.srsm,
            "zonal_head": h.zonal_head, "branch": h.branch, "city": h.city,
            "valid_from": h.valid_from, "upload_id": h.upload_id,
        } for h in rows]

    def hierarchy_status(self, tenant_id: str) -> dict:
        from ..service.ids import normalize_id

        tid = uuid.UUID(tenant_id)
        rows = self._session.query(Hierarchy).filter(Hierarchy.tenant_id == tid).all()
        cutoff = datetime.now(UTC) - timedelta(days=90)
        result_reps = (
            self._session.query(Result.rep_id)
            .filter(
                Result.tenant_id == tid,
                Result.rep_id.isnot(None),
                Result.created_at >= cutoff,
            )
            .distinct()
            .all()
        )
        rep_ids = {normalize_id(r[0]) for r in result_reps if normalize_id(r[0]) is not None}
        agents = {normalize_id(h.agent_id) for h in rows}
        matched = sum(1 for rid in rep_ids if rid in agents)
        unmapped = len(rep_ids) - matched
        total = matched + unmapped
        upload_id = rows[0].upload_id if rows else None
        valid_from = max((h.valid_from for h in rows), default=None)
        return {
            "upload_id": upload_id,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "row_count": len(rows),
            "match_rate": round(matched / total, 3) if total else 0.0,
            "matched": matched,
            "unmapped": unmapped,
        }
```

- [ ] **Step 6: Confirm both repos satisfy the protocol (runtime_checkable) + suite green**

Run:
```bash
.venv/bin/python -c "
from prooflens.service.repo import Repo, InMemoryRepo
assert hasattr(InMemoryRepo, 'replace_hierarchy')
assert hasattr(InMemoryRepo, 'get_hierarchy_rows')
assert hasattr(InMemoryRepo, 'hierarchy_status')
print('ok')
"
.venv/bin/python -m pytest tests/unit/test_repo_hierarchy.py -q
```
Expected: `ok` then PASS.

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/service/repo.py src/prooflens/db/repo.py tests/unit/test_repo_hierarchy.py
git commit -m "feat(repo): hierarchy replace/get/status on InMemory + Postgres (parity)"
```

---

### Task 6: Pure analytics-aggregation util

**Files:**
- Create: `src/prooflens/api/analytics.py`
- Test: `tests/unit/test_analytics_agg.py` (create)

**Interfaces:**
- Consumes: `resolve_node`, `NODE_FIELDS` (Task 4); `ResultView` (`band`, `score`, `reason_code`, `rep_id`, `created_at`).
- Produces:
  - `build_buckets(items, start, end, bucket) -> list[dict]` — `items: list[ResultView]`, `start`/`end` tz-aware UTC (half-open), `bucket in {"daily","weekly","monthly"}`. Each bucket: `{bucket_label, start, end, clear, doubtful, suspect, total, avg_score, incomplete}`. `start`/`end` are ISO date strings; weekly labels `"Week 1".."Week N"` anchored to the range start; monthly = calendar month labelled `"YYYY-MM"`; daily labelled by ISO date. `incomplete=True` for the bucket that contains "today" (UTC) — i.e. the current unfinished bucket.
  - `aggregate_range(items, prev_items, rows, *, start, end, bucket, group_by, today) -> dict` — the full analytics payload additions: `{"series": [...buckets...], "incomplete": bool, "previous": {clear,doubtful,suspect,total,avg_score}, "period": {from,to}, "previous_period": {from,to}, "groups": [...], "reason_counts": {...}}`. `group_by in {"none", *NODE_FIELDS-with-'zone'-alias}`; `groups` is `[]` when `group_by == "none"`, else one entry per distinct node value (incl. an `"Unmapped"` entry) `{node, total, clear, doubtful, suspect, suspect_rate, avg_score, share}`. `today` is a `datetime.date` (injected for testability).
  - `GROUP_BY_FIELD: dict[str, str]` mapping the API `group_by` value to a `NODE_FIELDS` key (`"zone" -> "zonal_head"`, others identity).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_analytics_agg.py
from __future__ import annotations

from datetime import UTC, date, datetime

from prooflens.api.analytics import aggregate_range, build_buckets
from prooflens.service.views import ResultView


def _r(day: date, band="Clear", score=90.0, reason="clear", rep_id=None):
    return ResultView(
        id="x", created_at=datetime(day.year, day.month, day.day, 12, tzinfo=UTC).isoformat(),
        tenant_id="t1", band=band, score=score, reason="r", reason_code=reason,
        rubric_version="v3", rep_id=rep_id,
    )


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def test_daily_buckets_count_and_labels():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 4))   # Jun 1,2,3
    items = [_r(date(2026, 6, 1), "Clear", 80), _r(date(2026, 6, 1), "Suspect", 10),
             _r(date(2026, 6, 3), "Doubtful", 50)]
    b = build_buckets(items, start, end, "daily")
    assert [x["bucket_label"] for x in b] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert b[0]["total"] == 2 and b[0]["clear"] == 1 and b[0]["suspect"] == 1
    assert b[0]["avg_score"] == 45.0
    assert b[1]["total"] == 0
    assert b[2]["doubtful"] == 1


def test_weekly_buckets_anchored_to_range_start():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 15))  # 14 days -> 2 full weeks
    items = [_r(date(2026, 6, 2)), _r(date(2026, 6, 9))]        # week1, week2
    b = build_buckets(items, start, end, "weekly")
    assert [x["bucket_label"] for x in b] == ["Week 1", "Week 2"]
    assert b[0]["total"] == 1 and b[1]["total"] == 1
    assert b[0]["start"] == "2026-06-01" and b[0]["end"] == "2026-06-07"


def test_monthly_buckets_are_calendar_months():
    start, end = _dt(date(2026, 5, 15)), _dt(date(2026, 7, 2))
    items = [_r(date(2026, 5, 20)), _r(date(2026, 6, 10)), _r(date(2026, 7, 1))]
    b = build_buckets(items, start, end, "monthly")
    assert [x["bucket_label"] for x in b] == ["2026-05", "2026-06", "2026-07"]
    assert all(x["total"] == 1 for x in b)


def test_incomplete_flag_on_todays_bucket():
    today = datetime.now(UTC).date()
    start, end = _dt(today), _dt(date(today.year, today.month, today.day)) 
    # a 1-day range ending after today is not valid via resolve_range; test build_buckets directly
    from datetime import timedelta
    start = _dt(today - timedelta(days=1))
    end = _dt(today + timedelta(days=1))            # covers yesterday + today
    b = build_buckets([_r(today)], start, end, "daily")
    assert b[-1]["bucket_label"] == today.isoformat()
    assert b[-1]["incomplete"] is True
    assert b[0]["incomplete"] is False              # yesterday is complete


def test_aggregate_previous_period_window_and_delta():
    # Range Jun 8..Jun 14 (7 days). Previous equal-length period = Jun 1..Jun 7.
    start, end = _dt(date(2026, 6, 8)), _dt(date(2026, 6, 15))
    items = [_r(date(2026, 6, 10), "Suspect", 10), _r(date(2026, 6, 11), "Clear", 90)]
    prev = [_r(date(2026, 6, 2), "Suspect", 20)]
    out = aggregate_range(items, prev, [], start=start, end=end, bucket="daily",
                          group_by="none", today=date(2026, 6, 20))
    assert out["period"] == {"from": "2026-06-08", "to": "2026-06-14"}
    assert out["previous_period"] == {"from": "2026-06-01", "to": "2026-06-07"}
    assert out["previous"]["total"] == 1 and out["previous"]["suspect"] == 1
    assert out["groups"] == []
    assert out["reason_counts"]["suspect"] == 1 and out["reason_counts"]["clear"] == 1


def test_aggregate_group_by_includes_unmapped():
    start, end = _dt(date(2026, 6, 1)), _dt(date(2026, 6, 8))
    rows = [{"agent_id": "A1", "sm": None, "rsm": None, "srsm": None,
             "zonal_head": None, "branch": "North", "city": None,
             "valid_from": date(2026, 1, 1)}]
    items = [
        _r(date(2026, 6, 2), "Suspect", 10, "recycled", rep_id="A1"),  # North
        _r(date(2026, 6, 3), "Clear", 90, "clear", rep_id="A1"),       # North
        _r(date(2026, 6, 4), "Suspect", 10, "recycled", rep_id="A2"),  # Unmapped
    ]
    out = aggregate_range(items, [], rows, start=start, end=end, bucket="daily",
                          group_by="branch", today=date(2026, 6, 20))
    groups = {g["node"]: g for g in out["groups"]}
    assert set(groups) == {"North", "Unmapped"}
    assert groups["North"]["total"] == 2 and groups["North"]["suspect"] == 1
    assert groups["North"]["suspect_rate"] == 0.5
    assert groups["Unmapped"]["total"] == 1 and groups["Unmapped"]["suspect"] == 1
    assert round(groups["North"]["share"] + groups["Unmapped"]["share"], 3) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_analytics_agg.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.api.analytics'`

- [ ] **Step 3: Implement the aggregation util**

```python
# src/prooflens/api/analytics.py
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
            nxt = min(d + timedelta(days=7), e)
            # end shown is inclusive last day = nxt-1 for a full week; keep 7-day window label
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
    items: list[ResultView], start: datetime, end: datetime, bucket: str
) -> list[dict]:
    """Bucketed band/score series across [start, end). Weekly = 'Week 1..N'
    anchored to the range start; monthly = calendar months. The bucket that
    contains today (UTC) is flagged incomplete."""
    today = datetime.now(tz=start.tzinfo).date()
    edges = _bucket_edges(start, end, bucket)
    by_bucket: list[list[ResultView]] = [[] for _ in edges]
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
        last_day = be - timedelta(days=1)
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
    series = build_buckets(items, start, end, bucket)
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
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_analytics_agg.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/analytics.py tests/unit/test_analytics_agg.py
git commit -m "feat(analytics): pure aggregation — buckets, previous-period, node groups"
```

---

### Task 7: Extend `analytics_summary` endpoint (additive)

**Files:**
- Modify: `src/prooflens/api/scoring.py` (`analytics_summary`)
- Test: `tests/integration/test_scoring_api.py` (append; existing tests must still pass)

**Interfaces:**
- Consumes: `aggregate_range`, `GROUP_BY_FIELD` (Task 6); `resolve_range` (existing); `Repo.get_hierarchy_rows` (Task 5); `REASON_SHORT_LABEL` (Task 9) for `top_reasons` — Task 9 lands the map; wire the import here but guard order by sequencing Task 9 BEFORE Task 7 in execution if `short_label` assertions run. To keep Task 7 self-contained, this task adds `short_label` using a local import that Task 9 provides; run Task 9 first.
- Produces: same endpoint with new query params `from`, `to` (aliases of `start_date`/`end_date`), `bucket` (default `"daily"`), `group_by` (default `"none"`); response keeps EVERY existing key and adds `series` bucket enrichment (existing `series` daily key retained, plus new bucketed keys), `incomplete`, `previous`, `period`, `previous_period`, `groups`, and `short_label` inside each `top_reasons` entry.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_scoring_api.py (append)
def _backdate(repo, rep_id, band, score, reason_code, days_ago):
    from datetime import UTC, datetime, timedelta
    from prooflens.service.views import ResultView
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    repo.results.append(ResultView(
        id=f"b{len(repo.results)}", created_at=ts, tenant_id="t1", band=band,
        score=score, reason="r", reason_code=reason_code, rubric_version="v3",
        rep_id=rep_id,
    ))


def test_analytics_additive_keys_present(client):
    _upload(client, "meeting.jpg")
    body = client.get("/v1/analytics/summary").json()
    # every legacy key still present
    for k in ("total", "images_today", "band_distribution", "suspect_pct",
              "avg_score", "avg_processing_ms", "duplicates_caught",
              "top_reasons", "series"):
        assert k in body
    # new additive keys
    for k in ("incomplete", "previous", "period", "previous_period", "groups"):
        assert k in body
    assert body["groups"] == []                       # group_by defaults to none
    assert "short_label" in body["top_reasons"][0]


def test_analytics_from_to_aliases(client):
    from datetime import date
    today = date.today().isoformat()
    _upload(client, "meeting.jpg")
    a = client.get(f"/v1/analytics/summary?from={today}").json()
    b = client.get(f"/v1/analytics/summary?start_date={today}").json()
    assert a["total"] == b["total"] == 1


def test_analytics_weekly_bucket_labels(client, repo):
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=13)).isoformat()
    end = date.today().isoformat()
    _backdate(repo, "A1", "Suspect", 10, "recycled", 10)
    body = client.get(
        f"/v1/analytics/summary?from={start}&to={end}&bucket=weekly"
    ).json()
    labels = [b["bucket_label"] for b in body["series"]]
    assert labels[0] == "Week 1" and labels[-1].startswith("Week ")


def test_analytics_group_by_branch_with_unmapped(client, repo):
    from datetime import date, timedelta
    repo.replace_hierarchy("t1", [{
        "agent_id": "A1", "sm": None, "rsm": None, "srsm": None,
        "zonal_head": None, "branch": "North", "city": None,
        "valid_from": date.today() - timedelta(days=40),
    }], "u1")
    _backdate(repo, "A1", "Suspect", 10, "recycled", 2)
    _backdate(repo, "A2", "Clear", 90, "clear", 2)     # unmapped
    body = client.get("/v1/analytics/summary?group_by=branch").json()
    nodes = {g["node"] for g in body["groups"]}
    assert nodes == {"North", "Unmapped"}


def test_analytics_previous_period_present(client):
    _upload(client, "meeting.jpg")
    body = client.get("/v1/analytics/summary").json()
    assert set(body["period"]) == {"from", "to"}
    assert set(body["previous_period"]) == {"from", "to"}
    assert set(body["previous"]) >= {"clear", "doubtful", "suspect", "total", "avg_score"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "additive_keys or from_to or weekly_bucket or group_by_branch or previous_period" -v`
Expected: FAIL — new keys absent / `from` param unknown.

- [ ] **Step 3: Extend the endpoint**

In `src/prooflens/api/scoring.py`, update imports:

```python
from ..engine.verdicts import REASON_SHORT_LABEL, REASON_TEXT, Reason
from .analytics import GROUP_BY_FIELD, aggregate_range
from .date_range import fill_series, resolve_range
```

Replace the `analytics_summary` function body with (keeps every existing key; adds the new ones):

```python
@router.get("/v1/analytics/summary")
def analytics_summary(
    repo: Repo = Depends(get_repo),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None, alias="to"),
    bucket: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
    group_by: Literal["none", "zone", "srsm", "rsm", "sm", "branch", "city"] = Query(
        default="none"
    ),
) -> dict:
    # `from`/`to` are aliases of start_date/end_date; the explicit ones win if both given.
    start_arg = start_date if start_date is not None else from_
    end_arg = end_date if end_date is not None else to
    try:
        start, end = resolve_range(start_arg, end_arg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, total = repo.list_results(limit=5000, offset=0, start=start, end=end)

    bands = Counter(r.band for r in items)
    reason_counts = Counter(r.reason_code for r in items)
    scores = [r.score for r in items]
    proc = [r.processing_ms for r in items if r.processing_ms]

    today = datetime.now(UTC).date()
    today_iso = today.isoformat()
    images_today = sum(1 for r in items if (r.created_at or "").startswith(today_iso))

    # Legacy daily series (kept verbatim for existing consumers/tests).
    by_day: dict[str, list] = {}
    for r in items:
        by_day.setdefault((r.created_at or "")[:10], []).append(r)
    daily_series = fill_series(by_day, start, end)

    # Previous equal-length period (for deltas), fetched over its own window.
    span_days = (end.date() - start.date()).days
    prev_end = start
    prev_start_date = start.date() - timedelta(days=span_days)
    prev_start = datetime(
        prev_start_date.year, prev_start_date.month, prev_start_date.day, tzinfo=UTC
    )
    prev_items, _ = repo.list_results(limit=5000, offset=0, start=prev_start, end=prev_end)

    rows = repo.get_hierarchy_rows(DEFAULT_TENANT_ID_FOR_ANALYTICS(repo))
    agg = aggregate_range(
        items, prev_items, rows,
        start=start, end=end, bucket=bucket, group_by=group_by, today=today,
    )

    top_reasons = [
        {
            "reason_code": code,
            "reason": REASON_TEXT[Reason(code)],
            "short_label": REASON_SHORT_LABEL[Reason(code)],
            "count": n,
        }
        for code, n in reason_counts.most_common()
    ]

    return {
        "total": total,
        "images_today": images_today,
        "band_distribution": {b: bands.get(b, 0) for b in ("Clear", "Doubtful", "Suspect")},
        "suspect_pct": round(100 * bands.get("Suspect", 0) / total, 1) if total else 0.0,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "avg_processing_ms": round(sum(proc) / len(proc), 1) if proc else 0.0,
        "duplicates_caught": reason_counts.get(Reason.RECYCLED.value, 0),
        "top_reasons": top_reasons,
        "series": daily_series,          # legacy per-day series (unchanged shape)
        "buckets": agg["series"],        # NEW bucketed series (daily/weekly/monthly)
        "incomplete": agg["incomplete"],
        "previous": agg["previous"],
        "period": agg["period"],
        "previous_period": agg["previous_period"],
        "groups": agg["groups"],
    }
```

Add `timedelta` to the datetime import at the top of `scoring.py` (`from datetime import UTC, datetime, timedelta`).

The read endpoints are non-tenant-scoped (spec decision 5), but hierarchy is tenant-keyed. Resolve the demo tenant once. Add near the top of `scoring.py` (after `DEFAULT_TENANT = "dev"`):

```python
def DEFAULT_TENANT_ID_FOR_ANALYTICS(repo: Repo) -> str:
    # The read path is single-demo-tenant (spec decision 5). Hierarchy is
    # tenant-keyed, so resolve the demo tenant's id for the join. Empty string
    # (no hierarchy loaded) yields no rows -> every result is "Unmapped".
    t = repo.get_tenant_by_slug(DEFAULT_TENANT)
    return t.id if t else ""
```

> NOTE for the implementer: rename the helper to a normal lower_snake_case name `_analytics_tenant_id` to satisfy ruff (N802). Use `_analytics_tenant_id(repo)` at the call site. (Shown upper-case here only to make the intent unmissable — DO rename it.)

Correct call site:

```python
    rows = repo.get_hierarchy_rows(_analytics_tenant_id(repo))
```

- [ ] **Step 4: Run the new + the ENTIRE existing scoring suite**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -q`
Expected: PASS — every pre-existing analytics test (`test_results_and_analytics_populate`, `test_analytics_*`) still green (they assert on `series` and legacy keys, all preserved) plus the 5 new cases.

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(api): analytics_summary additive — from/to, bucket, group_by, previous, groups"
```

---

### Task 8: Extend `GET /v1/results` + `Repo.list_results` (reason/rep_id/from/to)

**Files:**
- Modify: `src/prooflens/service/repo.py` (`Repo.list_results` protocol + `InMemoryRepo.list_results`)
- Modify: `src/prooflens/db/repo.py` (`PostgresRepo.list_results`)
- Modify: `src/prooflens/api/scoring.py` (`list_results` endpoint)
- Test: `tests/integration/test_scoring_api.py` (append), `tests/unit/test_repo_hierarchy.py`-adjacent unit or `tests/unit/test_inmemory_review.py`-style unit for the repo filter.

**Interfaces:**
- Produces: `list_results(..., reason: str | None = None, rep_id: str | None = None)` on both repos — `reason` filters exact `reason_code`; `rep_id` filters normalized-exact `rep_id`. The endpoint adds `reason`, `rep_id`, `from`, `to` query params (`from`/`to` re-use `resolve_range` semantics but only when provided — when both absent, NO date filter is applied so the existing unfiltered behavior is preserved).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_scoring_api.py (append)
def test_results_filter_by_reason_and_rep_id(client, repo):
    from datetime import UTC, datetime
    from prooflens.service.views import ResultView
    now = datetime.now(UTC).isoformat()
    repo.results.extend([
        ResultView(id="r1", created_at=now, tenant_id="t1", band="Suspect", score=10,
                   reason="r", reason_code="recycled", rubric_version="v3", rep_id="A1"),
        ResultView(id="r2", created_at=now, tenant_id="t1", band="Clear", score=90,
                   reason="r", reason_code="clear", rubric_version="v3", rep_id="A2"),
    ])
    by_reason = client.get("/v1/results?reason=recycled").json()
    assert {i["reason_code"] for i in by_reason["items"]} == {"recycled"}
    # rep_id is normalized: lower-case query matches the stored upper id
    by_rep = client.get("/v1/results?rep_id=a1").json()
    assert {i["rep_id"] for i in by_rep["items"]} == {"A1"}


def test_results_filter_by_from_to(client, repo):
    from datetime import UTC, datetime, timedelta
    from prooflens.service.views import ResultView
    old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    new = datetime.now(UTC).isoformat()
    repo.results.extend([
        ResultView(id="old", created_at=old, tenant_id="t1", band="Clear", score=90,
                   reason="r", reason_code="clear", rubric_version="v3"),
        ResultView(id="new", created_at=new, tenant_id="t1", band="Clear", score=90,
                   reason="r", reason_code="clear", rubric_version="v3"),
    ])
    from datetime import date
    today = date.today().isoformat()
    only_today = client.get(f"/v1/results?from={today}").json()
    assert {i["id"] for i in only_today["items"]} == {"new"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "filter_by_reason or filter_by_from_to" -v`
Expected: FAIL — `reason`/`rep_id`/`from` params ignored (all rows returned).

- [ ] **Step 3: Extend both repos' `list_results`**

In `src/prooflens/service/repo.py`, update the protocol signature AND the `InMemoryRepo` implementation to add `reason` + `rep_id`:

Protocol:
```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        ...
```

`InMemoryRepo.list_results` (add the two filters after the band filter, normalize rep_id):
```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        from .ids import normalize_id

        rows = [r for r in self.results if band is None or r.band == band]
        if reason is not None:
            rows = [r for r in rows if r.reason_code == reason]
        if rep_id is not None:
            want = normalize_id(rep_id)
            rows = [r for r in rows if normalize_id(r.rep_id) == want]
        if review == "pending":
            rows = [r for r in rows if r.review_status is None]
        elif review:
            rows = [r for r in rows if r.review_status == review]
        if start is not None:
            rows = [
                r for r in rows
                if r.created_at and datetime.fromisoformat(r.created_at) >= start
            ]
        if end is not None:
            rows = [
                r for r in rows
                if r.created_at and datetime.fromisoformat(r.created_at) < end
            ]
        rows = list(reversed(rows))
        return rows[offset : offset + limit], len(rows)
```

In `src/prooflens/db/repo.py`, `PostgresRepo.list_results` — add the two filters:
```python
    def list_results(
        self, *, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        from ..service.ids import normalize_id

        query = self._session.query(Result)
        if band:
            query = query.filter(Result.band == band)
        if reason is not None:
            query = query.filter(Result.reason_code == reason)
        if rep_id is not None:
            query = query.filter(Result.rep_id == normalize_id(rep_id))
        if review == "pending":
            query = query.filter(Result.review_status.is_(None))
        elif review:
            query = query.filter(Result.review_status == review)
        if start is not None:
            query = query.filter(Result.created_at >= start)
        if end is not None:
            query = query.filter(Result.created_at < end)
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

- [ ] **Step 4: Extend the `list_results` endpoint**

In `src/prooflens/api/scoring.py`, replace the `list_results` endpoint:
```python
@router.get("/v1/results")
def list_results(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    band: str | None = Query(None),
    review: str | None = Query(None),
    reason: str | None = Query(None),
    rep_id: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    repo: Repo = Depends(get_repo),
) -> dict:
    # from/to only constrain the range when provided; absent => no date filter
    # (preserves the existing unfiltered default).
    start = end = None
    if from_ is not None or to is not None:
        try:
            start, end = resolve_range(from_, to)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, total = repo.list_results(
        limit=limit, offset=offset, band=band, review=review,
        reason=reason, rep_id=rep_id, start=start, end=end,
    )
    return {
        "items": [r.to_dict() for r in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/integration/test_scoring_api.py -k "filter_by_reason or filter_by_from_to or results_and_analytics" -v`
Expected: PASS (new filters work; the existing `test_results_and_analytics_populate` still green — new params default to None).

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/service/repo.py src/prooflens/db/repo.py src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(results): reason/rep_id/from/to filters on /v1/results (both repos)"
```

---

### Task 9: `REASON_SHORT_LABEL` in `engine/verdicts.py` + docs

Sequenced BEFORE Task 7 at execution time (Task 7 imports `REASON_SHORT_LABEL`). If executing strictly top-to-bottom, do Task 9 before Task 7, or run this task's Step 3 as the first change in Task 7.

**Files:**
- Modify: `src/prooflens/engine/verdicts.py` (add `REASON_SHORT_LABEL`)
- Modify: `docs/VERDICT_COPY.md` (document the short labels)
- Test: `tests/unit/test_verdict_copy.py` (append)

**Interfaces:**
- Produces: `REASON_SHORT_LABEL: dict[Reason, str]` covering EVERY `Reason` member.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_verdict_copy.py (append)
def test_every_reason_has_short_label():
    from prooflens.engine.verdicts import REASON_SHORT_LABEL, Reason
    assert set(REASON_SHORT_LABEL) == set(Reason)
    for reason, label in REASON_SHORT_LABEL.items():
        assert 0 < len(label) <= 32, f"{reason}: {label!r}"
        assert label[0].isupper(), f"{reason} short label should be title-ish: {label!r}"


def test_known_short_labels_match_spec():
    from prooflens.engine.verdicts import REASON_SHORT_LABEL, Reason
    assert REASON_SHORT_LABEL[Reason.RECYCLED] == "Recycled image"
    assert REASON_SHORT_LABEL[Reason.SCREEN_RECAPTURE] == "Photo of a screen"
    assert REASON_SHORT_LABEL[Reason.DESIGNED_GRAPHIC] == "Designed graphic"
    assert REASON_SHORT_LABEL[Reason.NO_PEOPLE_OR_IRRELEVANT] == "No people in scene"
    assert REASON_SHORT_LABEL[Reason.TOO_BLURRED] == "Too blurred"
    assert REASON_SHORT_LABEL[Reason.NO_CONTENT_ANALYSIS] == "Scored without content check"
    assert REASON_SHORT_LABEL[Reason.CLEAR] == "Clear"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_verdict_copy.py -k short_label -v`
Expected: FAIL — `ImportError: cannot import name 'REASON_SHORT_LABEL'`

- [ ] **Step 3: Add the map**

In `src/prooflens/engine/verdicts.py`, after `REASON_TEXT`:

```python
# Concise labels for aggregate surfaces (charts, group rows). Full sentences in
# REASON_TEXT remain the verdict surface; these are for counts/legends (spec §0e).
REASON_SHORT_LABEL: dict[Reason, str] = {
    Reason.CLEAR: "Clear",
    Reason.RECYCLED: "Recycled image",
    Reason.SCREEN_RECAPTURE: "Photo of a screen",
    Reason.DESIGNED_GRAPHIC: "Designed graphic",
    Reason.NO_PEOPLE_OR_IRRELEVANT: "No people in scene",
    Reason.NOT_A_VISIT: "Not a visit",
    Reason.SINGLE_PERSON: "Only one person",
    Reason.NO_VISIT_CONTEXT: "No visit in progress",
    Reason.TOO_BLURRED: "Too blurred",
    Reason.NO_CONTENT_ANALYSIS: "Scored without content check",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_verdict_copy.py -k short_label -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Document in `docs/VERDICT_COPY.md`**

Append a section to `docs/VERDICT_COPY.md`:

```markdown
## Short labels (aggregate surfaces)

Charts, group rows and reason legends use a concise label, never the full
sentence. The single source of truth is `REASON_SHORT_LABEL` in
[`src/prooflens/engine/verdicts.py`](../src/prooflens/engine/verdicts.py);
`tests/unit/test_verdict_copy.py` asserts every `Reason` has one (≤ 32 chars).
The full `reason` sentence remains the verdict surface — short labels are for
counts and legends only.

| Reason code | Short label |
|---|---|
| `clear` | Clear |
| `recycled` | Recycled image |
| `screen_recapture` | Photo of a screen |
| `designed_graphic` | Designed graphic |
| `no_people_or_irrelevant` | No people in scene |
| `not_a_visit` | Not a visit |
| `single_person` | Only one person |
| `no_visit_context` | No visit in progress |
| `too_blurred` | Too blurred |
| `no_content_analysis` | Scored without content check |
```

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/engine/verdicts.py docs/VERDICT_COPY.md tests/unit/test_verdict_copy.py
git commit -m "feat(verdicts): REASON_SHORT_LABEL for aggregate surfaces + docs"
```

---

### Task 10: Admin hierarchy endpoints (`POST` upload + `GET` status)

**Files:**
- Create: `src/prooflens/api/hierarchy_admin.py` (a new router; keeps `admin.py`'s tenant CRUD untouched)
- Modify: `src/prooflens/api/app.py` (register the router)
- Test: `tests/integration/test_hierarchy_admin_api.py` (create — offline InMemory)

**Interfaces:**
- Consumes: `require_admin` (from `admin.py`); `get_repo` (from `deps.py`); `Repo.replace_hierarchy`/`hierarchy_status` (Task 5); `resolve_node`/`NODE_FIELDS` (Task 4); `normalize_id` (Task 1).
- Produces: routes `POST /v1/admin/hierarchy` (multipart `file` CSV → validate → version → `{upload_id, row_count, match_rate_preview, matched, unmapped}`) and `GET /v1/admin/hierarchy/status` → `Repo.hierarchy_status`. Optional `GET /v1/admin/hierarchy/template` returns a CSV template.
- CSV columns (header row, case-insensitive): `agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from` (`valid_from` ISO `YYYY-MM-DD`). Validation errors → HTTP 400: unknown columns, missing `agent_id`/`valid_from` header, blank `agent_id`, duplicate `agent_id` **within the same `valid_from`**, unparseable `valid_from`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_hierarchy_admin_api.py
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.config import get_settings
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant():
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


@pytest.fixture
def repo():
    return InMemoryRepo([_tenant()])


@pytest.fixture
def client(repo):
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_headers():
    return {"X-Admin-Token": get_settings().admin_token}


def _csv(rows: str) -> dict:
    return {"file": ("hierarchy.csv", io.BytesIO(rows.encode()), "text/csv")}


GOOD = (
    "agent_id,sm,rsm,srsm,zonal_head,branch,city,valid_from\n"
    "A1,Sam,Ravi,Sr1,ZoneN,North,Delhi,2026-01-01\n"
    "A2,Sam,Ravi,Sr1,ZoneN,North,Delhi,2026-01-01\n"
)


def test_upload_requires_admin(client):
    r = client.post("/v1/admin/hierarchy", files=_csv(GOOD))
    assert r.status_code == 401


def test_upload_good_csv_versions_and_previews_match_rate(client, repo, admin_headers):
    from datetime import UTC, datetime
    now = datetime.now(UTC).isoformat()
    repo.results.append(ResultView(id="r1", created_at=now, tenant_id="t1", band="Clear",
                                   score=90, reason="r", reason_code="clear",
                                   rubric_version="v3", rep_id="A1"))
    r = client.post("/v1/admin/hierarchy", files=_csv(GOOD), headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2
    assert "upload_id" in body
    assert body["matched"] == 1 and body["unmapped"] == 0
    assert body["match_rate_preview"] == 1.0
    assert len(repo.get_hierarchy_rows("t1")) == 2


def test_upload_unknown_column_400(client, admin_headers):
    bad = "agent_id,valid_from,region\nA1,2026-01-01,X\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "region" in r.json()["detail"]


def test_upload_blank_agent_id_400(client, admin_headers):
    bad = "agent_id,valid_from\n ,2026-01-01\n"
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "agent_id" in r.json()["detail"].lower()


def test_upload_duplicate_agent_same_date_400(client, admin_headers):
    bad = ("agent_id,valid_from\nA1,2026-01-01\nA1,2026-01-01\n")
    r = client.post("/v1/admin/hierarchy", files=_csv(bad), headers=admin_headers)
    assert r.status_code == 400
    assert "duplicate" in r.json()["detail"].lower()


def test_upload_same_agent_two_dates_ok(client, admin_headers):
    ok = ("agent_id,valid_from,branch\nA1,2026-01-01,North\nA1,2026-05-01,South\n")
    r = client.post("/v1/admin/hierarchy", files=_csv(ok), headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["row_count"] == 2


def test_status_reports_current_version(client, repo, admin_headers):
    client.post("/v1/admin/hierarchy", files=_csv(GOOD), headers=admin_headers)
    st = client.get("/v1/admin/hierarchy/status", headers=admin_headers).json()
    assert st["row_count"] == 2
    assert st["valid_from"] == "2026-01-01"
    assert "match_rate" in st
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/integration/test_hierarchy_admin_api.py -v`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Implement the router**

```python
# src/prooflens/api/hierarchy_admin.py
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

from ..service.hierarchy import NODE_FIELDS, resolve_node
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

    # Match-rate preview vs distinct rep_ids in the tenant's last-90-day results,
    # computed against the NEW rows before persisting.
    status_before = repo.hierarchy_status(tenant_id)  # noqa: F841 (kept for clarity)
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
```

Note the unused `resolve_node`/`NODE_FIELDS` import: `NODE_FIELDS` IS used (in `_HEADER`); drop `resolve_node` from the import to keep ruff happy — change the import to `from ..service.hierarchy import NODE_FIELDS`.

- [ ] **Step 4: Register the router**

In `src/prooflens/api/app.py`, add the import and include:
```python
from .hierarchy_admin import router as hierarchy_admin_router
```
and after `app.include_router(scoring_router)`:
```python
    app.include_router(hierarchy_admin_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/integration/test_hierarchy_admin_api.py -v`
Expected: PASS (8 passed)

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/api/hierarchy_admin.py src/prooflens/api/app.py tests/integration/test_hierarchy_admin_api.py
git commit -m "feat(admin): /v1/admin/hierarchy upload + status + template (via Repo)"
```

---

### Task 11: `BACKEND_REQUIREMENTS.md` — document additively

**Files:**
- Modify: `frontend/BACKEND_REQUIREMENTS.md`

- [ ] **Step 1: Append the new-surface documentation**

Add a new subsection after the existing "Added for the frontend" block:

```markdown
### Analytics + Team Hierarchy (implemented additively)

All of the following are **additive** — no existing response key changed; the
golden set and verdict-copy invariants are preserved.

**`GET /v1/analytics/summary`** — now also accepts `from`/`to` (date aliases of
`start_date`/`end_date`, both kept), `bucket=daily|weekly|monthly` (default
`daily`), `group_by=none|zone|srsm|rsm|sm|branch|city` (default `none`). The
response keeps every existing key and adds:
- `buckets[]` — `{bucket_label, start, end, clear, doubtful, suspect, total, avg_score, incomplete}`. Weekly labels are `"Week 1..N"` anchored to the range start; monthly = calendar month (`YYYY-MM`).
- `incomplete` — true if the current (today's) bucket is unfinished.
- `previous` — `{clear, doubtful, suspect, total, avg_score}` for the immediately-preceding equal-length period (for deltas).
- `period` / `previous_period` — `{from, to}` explicit window bounds.
- `groups[]` — when `group_by != none`, one per node (incl. `"Unmapped"`): `{node, total, clear, doubtful, suspect, suspect_rate, avg_score, share}`.
- `top_reasons[]` entries now also carry `short_label`.
- The legacy per-day `series[]` is unchanged.

**`GET /v1/results`** — now also accepts `reason` (exact `reason_code`),
`rep_id` (normalized exact), and `from`/`to` (date range). Existing filters
(`band`, `review`, `limit`, `offset`) unchanged.

**`POST /v1/admin/hierarchy`** (multipart, `X-Admin-Token`) — CSV columns
`agent_id, sm, rsm, srsm, zonal_head, branch, city, valid_from` (`valid_from`
`YYYY-MM-DD`). Validates unknown columns / blank agent_id / duplicate agent_id
within a `valid_from` / bad dates → 400. Returns
`{upload_id, row_count, match_rate_preview, matched, unmapped}`. Versions via
`upload_id`; the hierarchy is effective-dated (a result maps to the row with the
latest `valid_from <= scored_date`).

**`GET /v1/admin/hierarchy/status`** — `{upload_id, valid_from, row_count,
match_rate, matched, unmapped}` (match rate vs distinct `rep_id`s in the last
90 days of results).

**`GET /v1/admin/hierarchy/template`** — the canonical column set + an example row.

**Known gaps (logged, not fixed here):** the analytics/results read paths are
NOT tenant-scoped (single-demo-tenant assumption; real fix is the SSO/RBAC
milestone). CSV-only upload; XLSX deferred.
```

- [ ] **Step 2: Commit**

```bash
git add frontend/BACKEND_REQUIREMENTS.md
git commit -m "docs: document analytics + hierarchy additions in BACKEND_REQUIREMENTS"
```

---

### Task 12: Final gate — full suite, lint (4 paths), mypy, OpenAPI sanity

**Files:** none (verification only; commit any fixups).

- [ ] **Step 1: Full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all — including the golden set and pre-existing scoring/webhook/review suites).

- [ ] **Step 2: Lint the SAME four paths CI lints**

Run: `.venv/bin/ruff check src tests scripts migrations`
Expected: clean. (Common catches: unused imports — e.g. `resolve_node` in `hierarchy_admin.py`, the `N802` upper-case helper name in `scoring.py`; the `status_before` `noqa`. Fix and re-run.)

- [ ] **Step 3: Type-check**

Run: `.venv/bin/mypy src`
Expected: clean. (Watch: `resolve_node` returns `dict | None`; `hierarchy_status` returns `dict`; `Query(alias="from")` params typed `str | None`.)

- [ ] **Step 4: OpenAPI sanity — new params appear**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
from prooflens.api.app import create_app
spec = create_app().openapi()['paths']
a = sorted(x['name'] for x in spec['/v1/analytics/summary']['get'].get('parameters', []))
r = sorted(x['name'] for x in spec['/v1/results']['get'].get('parameters', []))
print('analytics:', a)
print('results:', r)
assert {'from','to','bucket','group_by','start_date','end_date'} <= set(a), a
assert {'reason','rep_id','from','to','band'} <= set(r), r
assert '/v1/admin/hierarchy' in spec and '/v1/admin/hierarchy/status' in spec
print('OPENAPI OK')
"
```
Expected: prints the param lists then `OPENAPI OK`.

- [ ] **Step 5: Commit any fixups**

```bash
git add -A
git commit -m "chore: lint/type fixups + final gate for analytics-hierarchy backend"
```

---

## Self-Review

**1. Spec coverage:**
- §0a analytics extension (`from`/`to`, `bucket`, `group_by`, `previous`, `period`/`previous_period`, `groups` incl. Unmapped, `short_label`, weekly anchoring, incomplete bucket) → Tasks 6 (pure agg) + 7 (endpoint) + 9 (short_label).
- §0b `/v1/results` filters (`reason`, `rep_id`, `from`/`to`) → Task 8.
- §0c hierarchy table (columns, effective-dated join, shared normalization) → Tasks 1 (normalize), 3 (table), 4 (resolver).
- §0d admin endpoints (upload + status, match rate) → Tasks 5 (repo) + 10 (routes).
- §0e `REASON_SHORT_LABEL` + `VERDICT_COPY.md` → Task 9.
- §0f `BACKEND_REQUIREMENTS.md` → Task 11.
- Decision 1 (`rep_id`/`opportunity_id` columns + backfill) → Tasks 2 + 3. Decision 3 (Repo abstraction) → Task 5/10. Decision 4 (pure resolver) → Task 4. Decision 5 (non-tenant-scoped reads, tenant-keyed hierarchy) → Task 7/10 `_analytics_tenant_id`/`_tenant_id`. §13 tests (two-version move, unmapped/normalization, delta/group_by/prev-window/incomplete/weekly, results filters, upload validation/match-rate/versioning) → Tasks 4, 5, 6, 8, 10.
- Final gate (pytest, ruff 4 paths, mypy, OpenAPI) → Task 12.

**2. Placeholder scan:** No "TODO/TBD/similar-to". Two intentional flags for the implementer, both concrete: (a) Task 7's `DEFAULT_TENANT_ID_FOR_ANALYTICS` is shown upper-case with an explicit instruction to rename to `_analytics_tenant_id` (ruff N802) and a corrected call site; (b) Task 10 notes dropping the unused `resolve_node` import. Task 1 Step 6 offers two options (full signed-webhook case OR the model-level `WebhookPayload` assertion) — the model-level one is complete and self-contained. These are guidance, not gaps.

**3. Type consistency:** `normalize_id(str|None)->str|None` used identically everywhere. `resolve_node(rows: list[dict], agent_id: str|None, scored_date: date)->dict|None` matches its use in `analytics._node_label`. `NODE_FIELDS`/`GROUP_BY_FIELD` keys line up (`zone→zonal_head`). Repo methods `replace_hierarchy(str, list[dict], str)->None`, `get_hierarchy_rows(str)->list[dict]`, `hierarchy_status(str)->dict` are identical across InMemory + Postgres and consumed unchanged in Tasks 7 & 10. `list_results` gains `reason`/`rep_id` on protocol + both impls + endpoint in Task 8. `REASON_SHORT_LABEL` (Task 9) is imported by Task 7 — execution note requires Task 9 before Task 7. `build_buckets`/`aggregate_range` signatures in Task 6 match the endpoint call in Task 7 (`today=datetime.now(UTC).date()`).

**Risks / ambiguities noted for the executor:** (1) Task 9 must precede Task 7 (import dependency) — flagged in both tasks. (2) The spec says "add `series` bucket enrichment"; to stay strictly additive against existing tests that assert `len(series)==30`, the plan KEEPS the legacy daily `series` and adds a separate `buckets` key rather than mutating `series` — confirm the frontend spec expects `buckets` (or rename if it truly wants the bucketed data under `series`). (3) "Duplicate agent_ids" validation is scoped to duplicates within the same `valid_from` so legitimate effective-dated multi-version rows for one agent are allowed — verify against §13 intent.
