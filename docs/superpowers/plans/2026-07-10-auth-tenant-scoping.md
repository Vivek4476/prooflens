# Auth + Tenant Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require a valid per-tenant API key on every `/v1/*` data route, resolve the tenant from that key, filter every query to it, and keep the key server-side via a Next.js BFF proxy.

**Architecture:** A hashed `api_keys` table + a `require_tenant` FastAPI dependency that resolves an active tenant from an `Authorization: Bearer <key>` header (401 otherwise). `list_results` gains a required `tenant_id` filter (the real data-isolation fix). A Next.js catch-all route handler proxies the browser's same-origin `/api/*` calls to the backend, injecting the key from server-only env so the browser never holds it.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Alembic, pytest, ruff, mypy (backend); Next.js 15 App Router, React 18, TypeScript, axios, Vitest, Playwright (frontend).

## Global Constraints

- **Additive only:** the scoring engine, verdict vocabulary, webhook handler, and golden set change ZERO.
- **No plaintext keys stored:** only `sha256(raw_key)` (hex, 64 chars) is persisted; the raw key is shown once at mint.
- **Honest 401s:** unknown/missing/revoked/inactive → `401` (never `403`; never confirm a key exists).
- **Always enforced:** no `AUTH_ENABLED` bypass flag. Tests use a `require_tenant` dependency override; local dev uses a real minted key.
- **Untouched:** webhook `/v1/webhooks/lsq/{slug}` (HMAC), admin routes (`X-Admin-Token`), `/healthz`, `/readyz`, `/metrics`, `/openapi.json`, `/docs`.
- **Existing ~245 backend tests stay green** (via the dependency override).
- **Key format:** `pl_` + `secrets.token_urlsafe(30)`. **Header:** `Authorization: Bearer <key>`.
- **Repo interface:** `list_results(...)` is keyword-only; adding `tenant_id` keeps it keyword-only and **required** (no default) so no caller silently skips scoping.
- Run backend checks from repo root with the venv active: `source .venv/bin/activate`. Backend: `pytest -q -W ignore`, `ruff check src tests`, `mypy src`. Frontend (in `frontend/`): `npx tsc --noEmit`, `npx vitest run`.

---

### Task 1: `ApiKey` model + migration `0007_api_keys`

**Files:**
- Modify: `src/prooflens/db/models.py` (add `ApiKey` after `Tenant`)
- Create: `migrations/versions/0007_api_keys.py`

**Interfaces:**
- Produces: `ApiKey` ORM model (`api_keys` table: `id, tenant_id, key_hash, prefix, label, created_at, revoked_at`). `key_hash` is unique/indexed; `tenant_id` FK+indexed.

- [ ] **Step 1: Add the `ApiKey` model.** In `src/prooflens/db/models.py`, immediately after the `Tenant` class (ends ~line 66), add:

```python
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), index=True
    )
    # sha256(raw key), hex (64 chars). The raw key is shown once at mint, never stored.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # First chars of the raw key, for display/debugging only (never reconstructable).
    prefix: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Non-null => inactive. Revocation sets this instead of deleting the row.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

(`uuid`, `datetime`, `String`, `DateTime`, `ForeignKey`, `func`, `Mapped`, `mapped_column`, `UUID`, `_uuid` are all already imported/defined in this file.)

- [ ] **Step 2: Create the migration.** Write `migrations/versions/0007_api_keys.py`:

```python
"""api_keys: per-tenant API credentials (hashed) for /v1/* auth

Revision ID: 0007_api_keys
Revises: 0006_agent_name
Create Date: 2026-07-10

Additive: a standalone table of per-tenant API keys. Only the sha256 hash of a
key is stored; the raw key is shown once at mint. No backfill — existing tenants
get keys via scripts/mint_api_key.py.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_api_keys"
down_revision = "0006_agent_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("label", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_unique_constraint("uq_api_keys_key_hash", "api_keys", ["key_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_api_keys_key_hash", "api_keys", type_="unique")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")
```

- [ ] **Step 3: Verify the migration graph + import.** Run:

```bash
source .venv/bin/activate
python -c "from prooflens.db import models; print(models.ApiKey.__tablename__)"
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s=ScriptDirectory.from_config(Config('alembic.ini')); print([r.revision for r in s.walk_revisions()][:3])"
```
Expected: prints `api_keys`, then a list whose first element is `0007_api_keys` (head), followed by `0006_agent_name`.

- [ ] **Step 4: Lint + typecheck.**

Run: `ruff check src && mypy src`
Expected: `All checks passed!` and `Success: no issues found`.

- [ ] **Step 5: Commit.**

```bash
git add src/prooflens/db/models.py migrations/versions/0007_api_keys.py
git commit -m "feat(auth): api_keys table + model (migration 0007)"
```

---

### Task 2: API-key helpers + repo methods

**Files:**
- Create: `src/prooflens/service/api_keys.py`
- Modify: `src/prooflens/service/repo.py` (add 3 methods to `Repo` protocol + `InMemoryRepo`)
- Modify: `src/prooflens/db/repo.py` (add 3 methods to `PostgresRepo`; import `ApiKey`)
- Test: `tests/unit/test_api_keys.py`

**Interfaces:**
- Consumes: `ApiKey` model (Task 1); `TenantView` (`service/views.py`); `_tenant_view` helper (already in `db/repo.py`).
- Produces:
  - `service/api_keys.py`: `generate_key() -> str`, `hash_key(raw: str) -> str`, `key_prefix(raw: str) -> str`.
  - `Repo.record_api_key(tenant_id: str, key_hash: str, prefix: str, label: str) -> str` (returns key id).
  - `Repo.tenant_for_api_key(key_hash: str) -> TenantView | None` (active tenant + non-revoked key).
  - `Repo.revoke_api_key(key_id: str) -> None`.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/test_api_keys.py`:

```python
"""API-key hashing helpers + InMemoryRepo key storage/lookup."""

from __future__ import annotations

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _tenant() -> TenantView:
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def test_generate_key_is_prefixed_and_unique():
    a, b = generate_key(), generate_key()
    assert a.startswith("pl_") and b.startswith("pl_")
    assert a != b
    assert len(a) > 20


def test_hash_is_stable_hex_64_and_prefix_is_short():
    raw = "pl_example"
    assert hash_key(raw) == hash_key(raw)
    assert len(hash_key(raw)) == 64
    assert all(c in "0123456789abcdef" for c in hash_key(raw))
    assert key_prefix(raw) == "pl_example"[:12]


def test_record_and_resolve_api_key():
    repo = InMemoryRepo([_tenant()])
    raw = generate_key()
    repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    resolved = repo.tenant_for_api_key(hash_key(raw))
    assert resolved is not None and resolved.id == "t1"
    # An unknown key resolves to nothing.
    assert repo.tenant_for_api_key(hash_key("pl_nope")) is None


def test_revoked_key_resolves_to_none():
    repo = InMemoryRepo([_tenant()])
    raw = generate_key()
    key_id = repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    assert repo.tenant_for_api_key(hash_key(raw)) is not None
    repo.revoke_api_key(key_id)
    assert repo.tenant_for_api_key(hash_key(raw)) is None
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `source .venv/bin/activate && pytest tests/unit/test_api_keys.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.service.api_keys'`.

- [ ] **Step 3: Create the helpers.** Write `src/prooflens/service/api_keys.py`:

```python
"""API-key helpers: mint a raw key, hash it, and take a display prefix.

Raw keys are shown once at mint and never stored — only sha256(raw) is kept and
compared. Hash-equality on the digest is inherently constant-time."""

from __future__ import annotations

import hashlib
import secrets

KEY_PREFIX = "pl_"
PREFIX_DISPLAY_LEN = 12  # chars of the raw key kept for display — never enough to reconstruct


def generate_key() -> str:
    """A fresh raw API key: 'pl_' + url-safe random. Shown once, never stored."""
    return KEY_PREFIX + secrets.token_urlsafe(30)


def hash_key(raw: str) -> str:
    """sha256 hex of the raw key — what we store and compare."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def key_prefix(raw: str) -> str:
    """First PREFIX_DISPLAY_LEN chars, for display/debugging only."""
    return raw[:PREFIX_DISPLAY_LEN]
```

- [ ] **Step 4: Add the 3 methods to the `Repo` protocol.** In `src/prooflens/service/repo.py`, inside the `Repo` protocol (after `get_tenant`, ~line 30), add:

```python
    def record_api_key(self, tenant_id: str, key_hash: str, prefix: str, label: str) -> str:
        """Store a hashed API key for a tenant; return the new key's id."""
        ...

    def tenant_for_api_key(self, key_hash: str) -> TenantView | None:
        """The active tenant owning a non-revoked key with this hash, else None."""
        ...

    def revoke_api_key(self, key_id: str) -> None:
        """Mark a key inactive (idempotent; unknown id is a no-op)."""
        ...
```

- [ ] **Step 5: Implement them on `InMemoryRepo`.** In the same file: in `InMemoryRepo.__init__` (after `self._hierarchy = {}`, ~line 108) add:

```python
        # key_hash -> {"id": str, "tenant_id": str, "revoked": bool}
        self._api_keys: dict[str, dict] = {}
```

Then add these methods to `InMemoryRepo` (anywhere among its methods):

```python
    def record_api_key(self, tenant_id: str, key_hash: str, prefix: str, label: str) -> str:
        key_id = str(next(self._ids))
        self._api_keys[key_hash] = {"id": key_id, "tenant_id": tenant_id, "revoked": False}
        return key_id

    def tenant_for_api_key(self, key_hash: str) -> TenantView | None:
        rec = self._api_keys.get(key_hash)
        if rec is None or rec["revoked"]:
            return None
        return self._tenants.get(rec["tenant_id"])

    def revoke_api_key(self, key_id: str) -> None:
        for rec in self._api_keys.values():
            if rec["id"] == key_id:
                rec["revoked"] = True
```

- [ ] **Step 6: Run the InMemory tests — verify pass.**

Run: `pytest tests/unit/test_api_keys.py -q`
Expected: PASS (4 passed).

- [ ] **Step 7: Implement them on `PostgresRepo`.** In `src/prooflens/db/repo.py`: add `ApiKey` to the models import (find the existing `from ..db.models import ...` or `from .models import ...` line and add `ApiKey`), then add:

```python
    def record_api_key(self, tenant_id: str, key_hash: str, prefix: str, label: str) -> str:
        import uuid as _uuid
        row = ApiKey(
            tenant_id=_uuid.UUID(tenant_id), key_hash=key_hash, prefix=prefix, label=label
        )
        self._session.add(row)
        self._session.flush()
        return str(row.id)

    def tenant_for_api_key(self, key_hash: str) -> TenantView | None:
        row = (
            self._session.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
            .one_or_none()
        )
        if row is None:
            return None
        t = (
            self._session.query(Tenant)
            .filter(Tenant.id == row.tenant_id, Tenant.active.is_(True))
            .one_or_none()
        )
        return _tenant_view(t) if t else None

    def revoke_api_key(self, key_id: str) -> None:
        import uuid as _uuid
        from sqlalchemy import func as _func
        row = (
            self._session.query(ApiKey)
            .filter(ApiKey.id == _uuid.UUID(key_id))
            .one_or_none()
        )
        if row is not None:
            row.revoked_at = _func.now()
```

(`Tenant` and `_tenant_view` are already imported/defined in `db/repo.py` — confirm by grep before editing.)

- [ ] **Step 8: Full lint/type/test.**

Run: `pytest -q -W ignore && ruff check src tests && mypy src`
Expected: all pass (no regressions; new tests included).

- [ ] **Step 9: Commit.**

```bash
git add src/prooflens/service/api_keys.py src/prooflens/service/repo.py src/prooflens/db/repo.py tests/unit/test_api_keys.py
git commit -m "feat(auth): api-key helpers + record/resolve/revoke on both repos"
```

---

### Task 3: `require_tenant` dependency

**Files:**
- Create: `src/prooflens/api/auth.py`
- Test: `tests/unit/test_auth.py`

**Interfaces:**
- Consumes: `hash_key` (Task 2), `Repo.tenant_for_api_key` (Task 2), `get_repo` (`api/deps.py`), `TenantView`.
- Produces: `require_tenant(authorization, repo) -> TenantView` (FastAPI dependency; raises `HTTPException(401)`).

- [ ] **Step 1: Write the failing test.** Create `tests/unit/test_auth.py`:

```python
"""require_tenant: bearer-key -> tenant, everything else -> 401."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from prooflens.api.auth import require_tenant
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo_with_key() -> tuple[InMemoryRepo, str, str]:
    tenant = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                        scoring=ScoringConfig(), vision_backend="stub")
    repo = InMemoryRepo([tenant])
    raw = generate_key()
    key_id = repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    return repo, raw, key_id


def test_valid_bearer_resolves_tenant():
    repo, raw, _ = _repo_with_key()
    tenant = require_tenant(authorization=f"Bearer {raw}", repo=repo)
    assert tenant.id == "t1"


@pytest.mark.parametrize("header", [None, "", "Bearer ", "Token abc", "Bearer "])
def test_missing_or_malformed_header_401(header):
    repo, _, _ = _repo_with_key()
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=header, repo=repo)
    assert exc.value.status_code == 401


def test_unknown_key_401():
    repo, _, _ = _repo_with_key()
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=f"Bearer {generate_key()}", repo=repo)
    assert exc.value.status_code == 401


def test_revoked_key_401():
    repo, raw, key_id = _repo_with_key()
    repo.revoke_api_key(key_id)
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=f"Bearer {raw}", repo=repo)
    assert exc.value.status_code == 401
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `pytest tests/unit/test_auth.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.api.auth'`.

- [ ] **Step 3: Implement `require_tenant`.** Write `src/prooflens/api/auth.py`:

```python
"""Per-tenant API-key auth for the /v1/* data surface.

Every data route depends on ``require_tenant``: it reads ``Authorization: Bearer
<key>``, hashes it, and resolves the owning ACTIVE tenant via a non-revoked
api_keys row. Missing/unknown/revoked/inactive -> 401 (never 403; we do not
confirm a key's existence). The webhook (HMAC) and admin routes (X-Admin-Token)
have their own schemes and do NOT use this."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from ..service.api_keys import hash_key
from ..service.repo import Repo
from ..service.views import TenantView
from .deps import get_repo

_BEARER = "bearer "


def require_tenant(
    authorization: str | None = Header(default=None),
    repo: Repo = Depends(get_repo),
) -> TenantView:
    if not authorization or not authorization.lower().startswith(_BEARER):
        raise HTTPException(status_code=401, detail="missing bearer token")
    raw = authorization[len(_BEARER):].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="missing bearer token")
    tenant = repo.tenant_for_api_key(hash_key(raw))
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    return tenant
```

- [ ] **Step 4: Run tests — verify pass.**

Run: `pytest tests/unit/test_auth.py -q`
Expected: PASS (all parametrized cases + others).

- [ ] **Step 5: Lint/type.**

Run: `ruff check src tests && mypy src`
Expected: pass.

- [ ] **Step 6: Commit.**

```bash
git add src/prooflens/api/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): require_tenant bearer-key dependency"
```

---

### Task 4: `list_results` tenant scoping

**Files:**
- Modify: `src/prooflens/service/repo.py` (`Repo` protocol + `InMemoryRepo.list_results`)
- Modify: `src/prooflens/db/repo.py` (`PostgresRepo.list_results`)
- Test: `tests/unit/test_list_results_scoping.py`

**Interfaces:**
- Consumes: `Result.tenant_id` (already on the model).
- Produces: `list_results(*, tenant_id: str, limit=50, offset=0, band=None, review=None, reason=None, rep_id=None, start=None, end=None) -> tuple[list[ResultView], int]` — `tenant_id` is **required, keyword-only**, first param.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/test_list_results_scoping.py`:

```python
"""list_results must return only the requested tenant's rows."""

from __future__ import annotations

from datetime import UTC, datetime

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant(tid: str) -> TenantView:
    return TenantView(id=tid, slug=tid, webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _seed(repo: InMemoryRepo, tid: str, n: int) -> None:
    for i in range(n):
        repo.results.append(ResultView(
            id=f"{tid}-{i}",
            created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
            tenant_id=tid, band="Clear", score=90.0, reason="r",
            reason_code="clear", rubric_version="v3", rep_id="A1",
        ))


def test_list_results_isolates_by_tenant():
    repo = InMemoryRepo([_tenant("t1"), _tenant("t2")])
    _seed(repo, "t1", 3)
    _seed(repo, "t2", 5)

    items, total = repo.list_results(tenant_id="t1", limit=50, offset=0)
    assert total == 3
    assert all(r.tenant_id == "t1" for r in items)

    items2, total2 = repo.list_results(tenant_id="t2", limit=50, offset=0)
    assert total2 == 5
    assert all(r.tenant_id == "t2" for r in items2)

    # An unknown tenant sees nothing.
    _, total3 = repo.list_results(tenant_id="nope", limit=50, offset=0)
    assert total3 == 0
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `pytest tests/unit/test_list_results_scoping.py -q`
Expected: FAIL — `TypeError: list_results() missing 1 required keyword-only argument: 'tenant_id'` (or a total mismatch).

- [ ] **Step 3: Add `tenant_id` to the `Repo` protocol signature.** In `src/prooflens/service/repo.py`, change the protocol's `list_results` signature to lead with `tenant_id`:

```python
    def list_results(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
```

- [ ] **Step 4: Filter by tenant in `InMemoryRepo.list_results`.** Change its first line from `rows = [r for r in self.results ...]` to filter tenant first:

```python
    def list_results(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0, band: str | None = None,
        review: str | None = None, reason: str | None = None, rep_id: str | None = None,
        start: datetime | None = None, end: datetime | None = None,
    ) -> tuple[list[ResultView], int]:
        rows = [r for r in self.results if r.tenant_id == tenant_id]
        rows = [r for r in rows if band is None or r.band == band]
        # ... (rest of the existing filters unchanged: reason, rep_id, review, start, end) ...
```

Keep every existing filter line below it exactly as-is.

- [ ] **Step 5: Filter by tenant in `PostgresRepo.list_results`.** In `src/prooflens/db/repo.py`, update the signature identically and add the tenant filter as the first `.filter(...)` after building the query:

```python
        import uuid as _uuid
        query = self._session.query(Result).filter(Result.tenant_id == _uuid.UUID(tenant_id))
        if band:
            query = query.filter(Result.band == band)
        # ... (rest unchanged) ...
```

- [ ] **Step 6: Run the scoping test — verify pass.**

Run: `pytest tests/unit/test_list_results_scoping.py -q`
Expected: PASS.

- [ ] **Step 7: Note — the full suite is expected to FAIL here** because existing callers/tests don't pass `tenant_id` yet. That is fixed in Tasks 5–8. Run only lint + type now:

Run: `ruff check src tests && mypy src`
Expected: `mypy` reports call-site errors in `api/scoring.py` and `api/dse.py` (missing `tenant_id`) — that is expected and fixed next. Lint passes.

- [ ] **Step 8: Commit.**

```bash
git add src/prooflens/service/repo.py src/prooflens/db/repo.py tests/unit/test_list_results_scoping.py
git commit -m "feat(auth): list_results requires tenant_id (data isolation)"
```

---

### Task 5: Enforce + scope `scoring.py` routes (`/v1/score`, `/v1/results`, `/v1/analytics/summary`)

**Files:**
- Modify: `src/prooflens/api/scoring.py`
- Modify: any test that calls these routes (add the `require_tenant` override + seed a key) — Step 6 enumerates.

**Interfaces:**
- Consumes: `require_tenant` (Task 3), `list_results(tenant_id=...)` (Task 4), `score_bytes` (existing).
- Produces: `/v1/results`, `/v1/analytics/summary`, `/v1/score` now require a key and scope to its tenant.

- [ ] **Step 1: Import `require_tenant` + `TenantView`.** At the top of `src/prooflens/api/scoring.py` add:

```python
from ..service.views import TenantView  # if not already imported
from .auth import require_tenant
```

- [ ] **Step 2: Scope `/v1/results`.** Add `tenant: TenantView = Depends(require_tenant)` to the `list_results` route signature (after `repo`) and pass `tenant_id=tenant.id` into the repo call:

```python
    repo: Repo = Depends(get_repo),
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    # ... existing start/end resolution unchanged ...
    items, total = repo.list_results(
        tenant_id=tenant.id, limit=limit, offset=offset, band=band, review=review,
        reason=reason, rep_id=rep_id, start=start, end=end,
    )
```

- [ ] **Step 3: Scope `/v1/analytics/summary`.** Add `tenant: TenantView = Depends(require_tenant)` to the route, replace the `list_results(...)` call to pass `tenant_id=tenant.id`, and replace the internal `_analytics_tenant_id(repo)` call (used for the hierarchy join) with `tenant.id`:

```python
    ] = Query(default="none"),
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    # ...
    items, total = repo.list_results(limit=5000, offset=0, start=start, end=end, tenant_id=tenant.id)
    # ... wherever `_analytics_tenant_id(repo)` was called for hierarchy rows, use `tenant.id`:
    rows = repo.get_hierarchy_rows(tenant.id)
```

(Grep the route body for `_analytics_tenant_id` and replace each use with `tenant.id`.)

- [ ] **Step 4: Require auth on `/v1/score` and use the authed tenant.** The route currently takes a `tenant: str = Form(DEFAULT_TENANT)` form field and resolves it via `_score_direct`. Replace the form-based tenant with the authenticated tenant:

```python
@router.post("/v1/score")
async def score_image(
    image: UploadFile = File(...),
    backend: str | None = Form(None),
    repo: Repo = Depends(get_repo),
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    return await anyio.to_thread.run_sync(
        _score_direct, data, tenant, backend, repo, limiter=_score_limiter
    )
```

And change `_score_direct` to take the `TenantView` directly instead of a slug:

```python
def _score_direct(data: bytes, tenant: TenantView, backend: str | None, repo: Repo) -> dict:
    return score_bytes(data, tenant_view=tenant, backend=backend, repo=repo)
```

(Removes the now-unused slug lookup + `HTTPException(404, "unknown tenant")` inside `_score_direct`.) Keep `DEFAULT_TENANT` — it's still the seed-script default.

- [ ] **Step 5: Delete `_analytics_tenant_id` if now unused.** Grep: `grep -rn "_analytics_tenant_id" src/`. If no references remain, delete the function.

- [ ] **Step 6: Update this router's tests.** Find every test that hits these routes and (a) add the `require_tenant` override to its app fixture, (b) for `/v1/score` tests, drop any `tenant=` form field. Locate them:

```bash
grep -rln "v1/results\|v1/analytics/summary\|/v1/score" tests/
```

For each such test's `client`/app fixture, add ONE line after the `get_repo` override (the fixture already has a `repo` InMemoryRepo seeded with a `"dev"` tenant):

```python
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
```

Also: `/v1/score` no longer takes a `tenant` form field and no longer 404s on an unknown tenant (the tenant comes from the key). Remove/rewrite any test that posts `tenant=...` to `/v1/score` or asserts a 404 "unknown tenant" from it — that path is gone. A `/v1/score` happy-path test just posts the image (+ the auth override) and asserts a 200 verdict.

- [ ] **Step 7: Run the affected tests + lint/type.**

Run: `pytest tests/ -q -W ignore -k "results or analytics or score" && ruff check src tests && mypy src`
Expected: PASS (the routes now resolve the overridden `dev` tenant; `mypy` clean for `scoring.py`).

- [ ] **Step 8: Commit.**

```bash
git add src/prooflens/api/scoring.py tests/
git commit -m "feat(auth): enforce require_tenant + tenant scoping on scoring routes"
```

---

### Task 6: Enforce + scope `dse.py` routes

**Files:**
- Modify: `src/prooflens/api/dse.py`
- Modify: `tests/integration/test_dse_api.py`

**Interfaces:**
- Consumes: `require_tenant` (Task 3), `list_results(tenant_id=...)` (Task 4).
- Produces: `/v1/dse` + `/v1/dse/{agent_id}` require a key, scope hierarchy + results to its tenant.

- [ ] **Step 1: Import + add the dependency.** In `src/prooflens/api/dse.py` add `from .auth import require_tenant` and `from ..service.views import TenantView` (if not present). Add `tenant: TenantView = Depends(require_tenant)` to BOTH route signatures (`search_dse`, `dse_scorecard`), after `repo`.

- [ ] **Step 2: Use the authed tenant instead of `_tenant_id`.** Replace `tenant_id = _tenant_id(repo)` with `tenant_id = tenant.id` in both routes. Delete `_tenant_id` (grep to confirm no other references first).

- [ ] **Step 3: Scope the scorecard's result reads.** In `dse_scorecard`, both `repo.list_results(...)` calls must pass `tenant_id=tenant.id`:

```python
    items, total = repo.list_results(
        tenant_id=tenant.id, limit=5000, offset=0, rep_id=agent_id, start=start, end=end
    )
    # ... and the "any results ever" check:
    _any_items, any_total = repo.list_results(
        tenant_id=tenant.id, limit=1, offset=0, rep_id=agent_id
    )
```

- [ ] **Step 4: Add the override to the DSE test fixture.** In `tests/integration/test_dse_api.py`, in the `client` fixture (after `app.dependency_overrides[get_repo] = lambda: repo`) add:

```python
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
```

The `_seed_results` helper stores `tenant_id="t1"` and the fixture's `_tenant()` has `id="t1"`, so scoped reads still find the seeded rows.

- [ ] **Step 5: Run + lint/type.**

Run: `pytest tests/integration/test_dse_api.py -q -W ignore && ruff check src tests && mypy src`
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add src/prooflens/api/dse.py tests/integration/test_dse_api.py
git commit -m "feat(auth): enforce require_tenant + tenant scoping on DSE routes"
```

---

### Task 7: Enforce auth on `bulk.py` routes

**Files:**
- Modify: `src/prooflens/api/bulk.py`
- Modify: `tests/integration/test_bulk_score_api.py`

**Interfaces:**
- Consumes: `require_tenant` (Task 3).
- Produces: `POST /v1/bulk-score` + `GET /v1/bulk-score/{job_id}` require a key; the batch scores under the authed tenant.

- [ ] **Step 1: Import + require on both routes.** In `src/prooflens/api/bulk.py` add `from .auth import require_tenant` and `from ..service.views import TenantView`. Add `tenant: TenantView = Depends(require_tenant)` to `start_bulk_score` and `get_bulk_score`.

- [ ] **Step 2: Score under the authed tenant.** In `start_bulk_score`, replace the `DEFAULT_TENANT` tenant resolution with the authed tenant — remove the `tenant_view = repo.get_tenant_by_slug(DEFAULT_TENANT)` / 404 block and pass `tenant_slug=tenant.slug` into `run_bulk_job`:

```python
    tenant: TenantView = Depends(require_tenant),
) -> dict:
    if registry.active_count() >= MAX_INFLIGHT_JOBS:
        raise HTTPException(status_code=429, detail=(...))  # unchanged
    rows = [BulkRow(...) for r in body.rows]  # unchanged
    job = registry.create(total=len(rows), label=body.label)
    background_tasks.add_task(
        run_bulk_job, job, rows,
        tenant_slug=tenant.slug, lsq=lsq, repo_factory=repo_factory,
    )
    return {"job_id": job.id, "total": job.total}
```

- [ ] **Step 3: Add the override to the bulk test fixture.** In `tests/integration/test_bulk_score_api.py`, in the `client` fixture add:

```python
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
```

(The fixture's `_tenant()` has `slug="dev"`, `id="t1"`; the background job resolves `"dev"` via the overridden `get_repo_factory` repo, which has that tenant.)

- [ ] **Step 4: Run + lint/type.**

Run: `pytest tests/integration/test_bulk_score_api.py -q -W ignore && ruff check src tests && mypy src`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/prooflens/api/bulk.py tests/integration/test_bulk_score_api.py
git commit -m "feat(auth): require_tenant on bulk-score routes"
```

---

### Task 8: Full-suite green + cross-tenant isolation test

**Files:**
- Modify: any remaining test file still failing for lack of the override (Step 1 finds them).
- Test: `tests/integration/test_tenant_scoping.py` (new)

**Interfaces:**
- Consumes: everything above.
- Produces: a real end-to-end proof that tenant A's key never returns tenant B's data.

- [ ] **Step 1: Run the whole suite; fix any stragglers.**

Run: `pytest -q -W ignore`
For each failing test that hits a now-protected route, add to its app fixture:
```python
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
```
Re-run until green. (Webhook/admin/hierarchy-admin tests should NOT need it — those routes are unprotected.)

- [ ] **Step 2: Write the cross-tenant isolation test.** Create `tests/integration/test_tenant_scoping.py`:

```python
"""End-to-end: tenant A's key sees only A's results, never B's."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _tenant(tid: str) -> TenantView:
    return TenantView(id=tid, slug=tid, webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def _seed(repo, tid: str, n: int) -> None:
    for i in range(n):
        repo.results.append(ResultView(
            id=f"{tid}-{i}", created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
            tenant_id=tid, band="Clear", score=90.0, reason="r",
            reason_code="clear", rubric_version="v3", rep_id="A1",
        ))


@pytest.fixture
def env():
    repo = InMemoryRepo([_tenant("t1"), _tenant("t2")])
    _seed(repo, "t1", 3)
    _seed(repo, "t2", 5)
    key_a = generate_key()
    repo.record_api_key("t1", hash_key(key_a), key_prefix(key_a), "A")
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    # NOTE: require_tenant is NOT overridden here — we exercise the real header path.
    return TestClient(app, raise_server_exceptions=False), key_a


def test_no_key_is_401(env):
    client, _ = env
    assert client.get("/v1/results").status_code == 401


def test_key_a_sees_only_tenant_a(env):
    client, key_a = env
    r = client.get("/v1/results", headers={"Authorization": f"Bearer {key_a}"})
    assert r.status_code == 200
    assert r.json()["total"] == 3  # A's rows only, never B's 5


def test_bad_key_is_401(env):
    client, _ = env
    r = client.get("/v1/results", headers={"Authorization": "Bearer pl_wrong"})
    assert r.status_code == 401
```

- [ ] **Step 3: Run it.**

Run: `pytest tests/integration/test_tenant_scoping.py -q -W ignore`
Expected: PASS (3 passed).

- [ ] **Step 4: Whole suite + lint + type.**

Run: `pytest -q -W ignore && ruff check src tests && mypy src`
Expected: all green.

- [ ] **Step 5: Commit.**

```bash
git add tests/
git commit -m "test(auth): cross-tenant isolation + fixture overrides; suite green"
```

---

### Task 9: `mint_key` service fn + `mint_api_key.py` CLI

**Files:**
- Modify: `src/prooflens/service/api_keys.py` (add `mint_key`)
- Create: `scripts/mint_api_key.py` (thin CLI wrapper)
- Test: `tests/unit/test_mint_api_key.py`

**Interfaces:**
- Consumes: `generate_key/hash_key/key_prefix` (Task 2), `Repo.record_api_key` + `get_tenant_by_slug`.
- Produces: `mint_key(repo: Repo, slug: str, label: str) -> str` in `service/api_keys.py` (returns the raw key). The CLI is a thin wrapper so tests import from `prooflens.service.api_keys` — no `scripts` package needed.

- [ ] **Step 1: Write the failing test.** Create `tests/unit/test_mint_api_key.py`:

```python
"""mint_key: creates a resolvable key for an existing tenant."""

from __future__ import annotations

import pytest

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import hash_key, mint_key
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo() -> InMemoryRepo:
    return InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s",
                                    field_map={}, scoring=ScoringConfig(), vision_backend="stub")])


def test_mint_key_returns_resolvable_key():
    repo = _repo()
    raw = mint_key(repo, "dev", "test-label")
    assert raw.startswith("pl_")
    assert repo.tenant_for_api_key(hash_key(raw)) is not None


def test_mint_key_unknown_tenant_raises():
    repo = _repo()
    with pytest.raises(ValueError, match="unknown tenant"):
        mint_key(repo, "ghost", "x")
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `pytest tests/unit/test_mint_api_key.py -q`
Expected: FAIL — `ImportError: cannot import name 'mint_key' from 'prooflens.service.api_keys'`.

- [ ] **Step 3: Add `mint_key` to the service module.** Append to `src/prooflens/service/api_keys.py`:

```python
def mint_key(repo: "Repo", slug: str, label: str = "") -> str:
    """Create a key for an existing tenant and return the RAW key (shown once).
    Raises ValueError for an unknown tenant. The caller commits the repo."""
    tenant = repo.get_tenant_by_slug(slug)
    if tenant is None:
        raise ValueError(f"unknown tenant {slug!r}")
    raw = generate_key()
    repo.record_api_key(tenant.id, hash_key(raw), key_prefix(raw), label)
    return raw
```

Add the import guard at the top of `api_keys.py` for the type-only reference:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repo import Repo
```

- [ ] **Step 4: Run test — verify pass.**

Run: `pytest tests/unit/test_mint_api_key.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Add the thin CLI wrapper.** Create `scripts/mint_api_key.py`:

```python
"""Mint a per-tenant API key. Prints the raw key ONCE — store it now.

Usage:
    python scripts/mint_api_key.py --tenant dev --label "dev dashboard"
"""

from __future__ import annotations

import argparse

from prooflens.service.api_keys import mint_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a per-tenant API key.")
    parser.add_argument("--tenant", required=True, help="tenant slug (e.g. dev)")
    parser.add_argument("--label", default="", help="human label for the key")
    args = parser.parse_args()

    from prooflens.db.base import session_scope
    from prooflens.db.repo import PostgresRepo

    session = session_scope()
    repo = PostgresRepo(session)
    try:
        raw = mint_key(repo, args.tenant, args.label)
        repo.commit()
    finally:
        session.close()
    print(raw)


if __name__ == "__main__":
    main()
```

(No `scripts/__init__.py` — the script is executed, not imported; the tested logic lives in `service/api_keys.py`.)

- [ ] **Step 6: Lint/type.**

Run: `ruff check src tests scripts && mypy src`
Expected: pass.

- [ ] **Step 7: Commit.**

```bash
git add src/prooflens/service/api_keys.py scripts/mint_api_key.py tests/unit/test_mint_api_key.py
git commit -m "feat(auth): mint_key service fn + mint_api_key CLI"
```

---

### Task 10: Next.js BFF proxy + client repoint

**Files:**
- Create: `frontend/src/app/api/[...path]/route.ts`
- Create: `frontend/src/app/api/[...path]/route.test.ts`
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/.env.local.example`, `frontend/.env.production`

**Interfaces:**
- Consumes: server-only env `PROOFLENS_API_URL`, `PROOFLENS_TENANT_KEY`, `PROOFLENS_ADMIN_TOKEN`.
- Produces: same-origin `/api/*` proxy; browser holds no secret.

- [ ] **Step 1: Write the failing proxy test.** Create `frontend/src/app/api/[...path]/route.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

function req(url: string, init?: RequestInit) {
  // NextRequest is a superset of Request for our purposes here.
  return new Request(url, init) as unknown as import("next/server").NextRequest;
}

afterEach(() => vi.restoreAllMocks());

describe("BFF proxy", () => {
  it("injects the bearer key on v1/* and forwards status + query", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const res = await GET(req("http://localhost:3000/api/v1/results?limit=5"), {
      params: Promise.resolve({ path: ["v1", "results"] }),
    });
    expect(res.status).toBe(200);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(String(calledUrl)).toContain("/v1/results?limit=5");
    expect((calledInit!.headers as Headers).get("authorization")).toMatch(/^Bearer /);
  });

  it("injects the admin token on admin/* and not the bearer key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } }),
    );
    await GET(req("http://localhost:3000/api/admin/tenants"), {
      params: Promise.resolve({ path: ["admin", "tenants"] }),
    });
    const init = fetchMock.mock.calls[0][1]!;
    const headers = init.headers as Headers;
    expect(headers.get("x-admin-token")).toBeTruthy();
    expect(headers.get("authorization")).toBeNull();
  });

  it("forwards a POST body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 202, headers: { "content-type": "application/json" } }),
    );
    const res = await POST(
      req("http://localhost:3000/api/v1/bulk-score", {
        method: "POST",
        body: JSON.stringify({ rows: [] }),
        headers: { "content-type": "application/json" },
      }),
      { params: Promise.resolve({ path: ["v1", "bulk-score"] }) },
    );
    expect(res.status).toBe(202);
    expect(fetchMock.mock.calls[0][1]!.method).toBe("POST");
  });
});
```

- [ ] **Step 2: Run it — verify it fails.**

Run (in `frontend/`): `npx vitest run src/app/api`
Expected: FAIL — cannot resolve `./route`.

- [ ] **Step 3: Implement the proxy.** Create `frontend/src/app/api/[...path]/route.ts`:

```typescript
import type { NextRequest } from "next/server";

// The BFF proxy: the browser calls same-origin /api/*, and this Node handler
// forwards to the backend, injecting credentials from SERVER-ONLY env so the
// key never reaches the browser. Never cached.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = (process.env.PROOFLENS_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TENANT_KEY = process.env.PROOFLENS_TENANT_KEY || "";
const ADMIN_TOKEN = process.env.PROOFLENS_ADMIN_TOKEN || "";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const suffix = path.join("/");
  const search = new URL(req.url).search;
  const url = `${BACKEND}/${suffix}${search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (suffix.startsWith("v1/") && TENANT_KEY) headers.set("authorization", `Bearer ${TENANT_KEY}`);
  if (suffix.startsWith("admin/") && ADMIN_TOKEN) headers.set("x-admin-token", ADMIN_TOKEN);

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  const upstream = await fetch(url, { method, headers, body, redirect: "manual" });
  const respHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) respHeaders.set("content-type", ct);
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}

type Ctx = { params: Promise<{ path: string[] }> };
const handler = async (req: NextRequest, ctx: Ctx) => proxy(req, (await ctx.params).path);

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
```

- [ ] **Step 4: Run the proxy test — verify pass.**

Run: `npx vitest run src/app/api`
Expected: PASS (3 passed).

- [ ] **Step 5: Repoint the API client at `/api`.** In `frontend/src/lib/api/client.ts`, change the base URL + drop the browser admin token:

```typescript
// All backend calls go through the same-origin BFF proxy (src/app/api/[...path]),
// which injects the tenant key + admin token server-side. The browser holds no secret.
export const API_BASE = "/api";
export const http = axios.create({ baseURL: API_BASE, timeout: 120_000 });
```

Delete the `API_URL`/`ADMIN_TOKEN` consts and the `NEXT_PUBLIC_*` reads. In `tenants()`, remove the manual `headers: { "X-Admin-Token": ADMIN_TOKEN }` (the proxy adds it):

```typescript
  async tenants(): Promise<Tenant[]> {
    const { data } = await http.get("/admin/tenants");
    return data;
  },
```

Grep for other `API_URL`/`ADMIN_TOKEN` importers and update: `grep -rn "API_URL\|ADMIN_TOKEN" frontend/src`. (If `API_URL` is imported elsewhere for display, export `API_BASE` and adjust.)

- [ ] **Step 6: Update env examples.** Replace `frontend/.env.local.example` contents:

```
# Copy to .env.local. These are SERVER-ONLY (no NEXT_PUBLIC_ prefix) — read by the
# BFF proxy at src/app/api/[...path]/route.ts, never shipped to the browser.
PROOFLENS_API_URL=http://localhost:8000
PROOFLENS_TENANT_KEY=pl_paste_a_key_from_scripts/mint_api_key.py
PROOFLENS_ADMIN_TOKEN=dev-admin-token
```

Replace `frontend/.env.production`:

```
# Production build config for Vercel. These are SERVER-ONLY env (set in the Vercel
# dashboard, NOT committed for the secret ones) — read by the BFF proxy, never
# inlined into the browser bundle. NEXT_PUBLIC_ADMIN_TOKEN is removed entirely.
PROOFLENS_API_URL=https://prooflens-api.onrender.com
# PROOFLENS_TENANT_KEY and PROOFLENS_ADMIN_TOKEN are set in the Vercel dashboard.
```

- [ ] **Step 7: Typecheck + full frontend suite.**

Run: `npx tsc --noEmit && npx vitest run`
Expected: `tsc` clean; all vitest pass (177 unit + 3 new proxy).

- [ ] **Step 8: Commit.**

```bash
cd .. && git add frontend/src/app/api frontend/src/lib/api/client.ts frontend/.env.local.example frontend/.env.production
git commit -m "feat(auth): Next.js BFF proxy; client calls same-origin /api; key server-side"
```

---

### Task 11: Docs + local-dev wiring + e2e sanity

**Files:**
- Modify: `frontend/BACKEND_REQUIREMENTS.md`
- Verify: mobile e2e still pass through the proxy.

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Document the auth surface.** Append to `frontend/BACKEND_REQUIREMENTS.md`:

```markdown
## Auth (per-tenant API key) — implemented (#18)

All `/v1/*` data routes require `Authorization: Bearer <key>`; missing/invalid/revoked → `401`.
The key resolves the tenant and every query is filtered to it. Webhook (HMAC), admin
(`X-Admin-Token`), and `/healthz`/`/readyz`/`/metrics` are unaffected.

**Keys:** minted via `python scripts/mint_api_key.py --tenant <slug> --label <note>` (prints the raw
key once; only its sha256 is stored; revocable). **Never** shipped to the browser.

**Frontend:** the dashboard calls same-origin `/api/*`; the Next.js BFF proxy
(`src/app/api/[...path]/route.ts`) injects the key from server-only env
(`PROOFLENS_API_URL`, `PROOFLENS_TENANT_KEY`, `PROOFLENS_ADMIN_TOKEN`).
```

- [ ] **Step 2: Wire local dev.** Mint a local key against the running dev DB and set `.env.local` so the local dashboard works end-to-end:

```bash
source .venv/bin/activate
KEY=$(python scripts/mint_api_key.py --tenant dev --label "local dev")
printf 'PROOFLENS_API_URL=http://localhost:8000\nPROOFLENS_TENANT_KEY=%s\nPROOFLENS_ADMIN_TOKEN=dev-admin-token\n' "$KEY" > frontend/.env.local
```
(The migration must be applied to the local DB first: `alembic upgrade head`.)

- [ ] **Step 3: Restart the frontend + smoke the proxy.**

```bash
pkill -f "next dev"; sleep 1; rm -rf frontend/.next
(cd frontend && npm run dev > /tmp/next-dev.log 2>&1 &)
sleep 6
curl -s -o /dev/null -w "proxy results: %{http_code}\n" http://localhost:3000/api/v1/results?limit=1
```
Expected: `proxy results: 200` (the proxy injected the key; the backend returned scoped results). A `401` means the key/env is wrong.

- [ ] **Step 4: Run the mobile e2e (data-independent — must still pass).**

Run (in `frontend/`): `npx playwright test`
Expected: 15 passed. (The smoke tests assert layout/nav, not API data, so they pass regardless; the proxy must not 500.)

- [ ] **Step 5: Final full verification.**

```bash
source .venv/bin/activate && pytest -q -W ignore && ruff check src tests scripts && mypy src
cd frontend && npx tsc --noEmit && npx vitest run
```
Expected: all green.

- [ ] **Step 6: Commit.**

```bash
cd .. && git add frontend/BACKEND_REQUIREMENTS.md
git commit -m "docs(auth): document per-tenant key + BFF proxy in BACKEND_REQUIREMENTS"
```

---

## Deployment (post-merge, production still HELD)

Not code — a runbook for whoever deploys:
1. Merge to `analytics-v4` (preview), like DSE/bulk. Render runs `alembic upgrade head` (creates `api_keys`).
2. `python scripts/mint_api_key.py --tenant dev --label "abslI dashboard"` against the prod DB → copy the printed key.
3. In **Vercel** (server env, NOT `NEXT_PUBLIC_*`): set `PROOFLENS_API_URL=https://prooflens-api.onrender.com`, `PROOFLENS_TENANT_KEY=<minted key>`, `PROOFLENS_ADMIN_TOKEN=<existing admin token>`. Remove `NEXT_PUBLIC_ADMIN_TOKEN`.
4. Redeploy the frontend. Verify the dashboard loads and a raw `curl https://prooflens-api.onrender.com/v1/results` returns `401`.
