# Retire the Stub as Production Default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `groq` the default vision backend so no fake-Clear verdict can reach a user; when no key is configured, scoring caps to Doubtful (never Clear, never blocks). The stub survives as a test-only / offline-CLI fixture.

**Architecture:** Change the default backend name in config/deploy. On the scoring paths, a missing-key construction failure no longer 503s on the *default* path — it substitutes an `UnavailableVision` sentinel whose `assess()` raises, so `relevance.run` returns `available=False` and `fuse.py` caps the verdict to Doubtful. The `503` is kept only for an *explicit* operator override to a misconfigured live backend.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy + alembic, pydantic-settings, pytest.

## Global Constraints

- `groq` is the default vision backend everywhere production runs; the stub is NEVER the implicit default.
- The stub stays selectable **by name** (`get_backend("stub")`), unchanged, for CLI + tests.
- The golden set + CI stay fully offline on the stub — do not break them.
- Core principle: **fail-open — score & flag, never block; never award Clear without real vision.**
- `conftest.py` autouse `_hermetic_vision_env` pins `VISION_BACKEND=stub` and blanks all provider keys — existing tests are unaffected by the default flip; new no-key tests must monkeypatch the env explicitly.
- `GROQ_API_KEY` is already set on Render (confirmed), so the production cutover uses the real model immediately.

---

### Task 1: `UnavailableVision` sentinel backend

A `VisionBackend` whose `assess()` always raises, carrying the construction-failure reason. Feeding it to the engine makes `relevance.run` return `available=False` (it catches exceptions from `assess`), which `fuse.py` turns into a Doubtful-capped verdict.

**Files:**
- Create: `src/prooflens/vision/unavailable.py`
- Modify: `src/prooflens/vision/__init__.py` (export the class)
- Test: `tests/unit/test_unavailable_vision.py`

**Interfaces:**
- Produces: `class UnavailableVision` with `name: str = "unavailable"`, `is_real: bool = False`, `__init__(self, reason: str)`, and `assess(self, image_bytes: bytes) -> ContentAssessment` which raises `RuntimeError(self._reason)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_unavailable_vision.py
"""UnavailableVision raises on assess so the relevance check degrades gracefully."""
from __future__ import annotations

import pytest

from prooflens.engine.checks import relevance
from prooflens.engine.scoring_config import Thresholds
from prooflens.vision.unavailable import UnavailableVision


def test_assess_raises_with_reason():
    v = UnavailableVision("no GROQ_API_KEY set")
    assert v.is_real is False
    with pytest.raises(RuntimeError, match="no GROQ_API_KEY set"):
        v.assess(b"\xff\xd8\xff")


def test_relevance_reports_unavailable_when_backend_raises():
    outcome = relevance.run(b"\xff\xd8\xff", vision=UnavailableVision("boom"), thresholds=Thresholds())
    assert outcome.available is False
    assert outcome.score is None
    assert outcome.data.get("error") is True
    assert "boom" in outcome.data.get("detail", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_unavailable_vision.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.vision.unavailable'`

- [ ] **Step 3: Write the implementation**

```python
# src/prooflens/vision/unavailable.py
"""A VisionBackend that is deliberately unavailable.

Used when the configured default backend cannot be constructed (e.g. no API
key). Its assess() raises, so engine/checks/relevance.py records
available=False and fusion caps the verdict to Doubtful — the app degrades to
review instead of 503-ing or silently falling back to the stub.
"""

from __future__ import annotations

from .schema import ContentAssessment


class UnavailableVision:
    name = "unavailable"
    is_real = False

    def __init__(self, reason: str) -> None:
        self._reason = reason or "vision backend unavailable"

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        raise RuntimeError(self._reason)
```

- [ ] **Step 4: Export it**

In `src/prooflens/vision/__init__.py`, add to the imports and `__all__` alongside the existing `StubBackend` export:

```python
from .unavailable import UnavailableVision  # noqa: F401
```
and add `"UnavailableVision"` to the `__all__` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_unavailable_vision.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/vision/unavailable.py src/prooflens/vision/__init__.py tests/unit/test_unavailable_vision.py
git commit -m "feat(vision): add UnavailableVision sentinel that degrades to Doubtful"
```

---

### Task 2: Make `groq` the default backend (config + deploy config)

Flip every *implicit* default from `stub` to `groq`. The `conftest` pin keeps the suite on stub, so this should not break existing tests.

**Files:**
- Modify: `src/prooflens/config.py` (field default + `build_vision_backend` fallback)
- Modify: `render.yaml`
- Modify: `deploy/docker-compose.yml`
- Test: `tests/unit/test_config_default.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings().vision_backend == "groq"` by default; `settings.build_vision_backend("stub")` still returns the stub.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config_default.py
"""The default vision backend is groq; stub is only reachable by explicit name."""
from __future__ import annotations

import prooflens.config as config


def test_default_backend_is_groq(monkeypatch):
    # Clear the conftest stub-pin so we observe the real default.
    monkeypatch.delenv("VISION_BACKEND", raising=False)
    config.get_settings.cache_clear()
    assert config.Settings().vision_backend == "groq"


def test_stub_still_selectable_by_name():
    settings = config.Settings()
    backend = settings.build_vision_backend("stub")
    assert backend.name == "stub"
    assert backend.is_real is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_default.py -v`
Expected: FAIL — `test_default_backend_is_groq` asserts `"groq"` but gets `"stub"`.

- [ ] **Step 3: Change the config default**

In `src/prooflens/config.py`, line ~51, change:

```python
    vision_backend: str = Field(default="stub", alias="VISION_BACKEND")
```
to:
```python
    vision_backend: str = Field(default="groq", alias="VISION_BACKEND")
```

And in `build_vision_backend` (line ~139), change the fallback literal:

```python
        name = (name or self.vision_backend or "groq").strip().lower()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_default.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Update deploy config**

In `render.yaml`, change the `VISION_BACKEND` env var value from `stub` to `groq` and update the adjacent comment to note: "groq is the default; `GROQ_API_KEY` must be set or images cap to Doubtful (review)."

In `deploy/docker-compose.yml`, line ~10, change:
```yaml
  VISION_BACKEND: ${VISION_BACKEND:-stub}
```
to:
```yaml
  VISION_BACKEND: ${VISION_BACKEND:-groq}   # override to 'stub' for a fully offline local run
```

- [ ] **Step 6: Run the full suite to confirm nothing relied on the implicit stub default**

Run: `pytest -q`
Expected: PASS (all pre-existing tests + the new ones). If any test fails because it relied on the *implicit* default being stub, fix that test by setting the backend explicitly (`vision_backend="stub"` in its fixture or `monkeypatch.setenv("VISION_BACKEND", "stub")`), not by reverting the default.

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/config.py render.yaml deploy/docker-compose.yml tests/unit/test_config_default.py
git commit -m "feat(config): default vision backend to groq (stub no longer implicit)"
```

---

### Task 3: No-503 degrade to Doubtful on the default `/v1/score` path

Distinguish an *explicit* per-request backend override from the *configured default*. Default-path construction failure → `UnavailableVision` → Doubtful. Explicit override failure → keep `503`.

**Files:**
- Modify: `src/prooflens/api/scoring.py` (`_score_direct`, lines ~76-91)
- Test: `tests/integration/test_scoring_api.py`

**Interfaces:**
- Consumes: `UnavailableVision(reason)` from Task 1.
- Produces: unchanged endpoint response shape; only the failure behaviour changes.

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_scoring_api.py`:

```python
def test_default_path_without_key_caps_to_doubtful(client, monkeypatch):
    # Default backend groq, but no key configured -> vision unavailable.
    monkeypatch.setenv("VISION_BACKEND", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    r = _upload(client, "meeting.jpg")
    assert r.status_code == 200                     # never blocks
    body = r.json()
    assert body["band"] != "Clear"                  # never a fake Clear
    content = next(c for c in body["checks"] if c["name"] == "content")
    assert content["available"] is False
    config.get_settings.cache_clear()


def test_explicit_override_to_misconfigured_live_backend_503s(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    with open(IMAGES_DIR / "meeting.jpg", "rb") as fh:
        r = client.post(
            "/v1/score",
            files={"image": ("meeting.jpg", fh.read(), "image/jpeg")},
            data={"backend": "groq"},               # operator explicitly asked for groq
        )
    assert r.status_code == 503
    config.get_settings.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_scoring_api.py -k "doubtful or 503" -v`
Expected: FAIL — the default-path test currently 503s (build failure raises), so `status_code == 200` fails.

- [ ] **Step 3: Implement the discriminator + degrade**

In `src/prooflens/api/scoring.py`, replace the block at lines ~77-91:

```python
    requested = (backend or settings.vision_backend or "stub").strip().lower()
    live_ai = requested != "stub"

    # Build the backend. If Live AI is requested but can't be constructed (e.g. a
    # missing API key), surface the exact reason — never silently use the stub.
    try:
        vision = settings.build_vision_backend(requested)
    except Exception as exc:  # noqa: BLE001
        if not live_ai:
            raise
        raise HTTPException(
            status_code=503, detail=f"Live AI ({requested}) is unavailable: {exc}"
        ) from exc
```

with:

```python
    explicit = backend is not None            # operator named a backend on THIS request
    requested = (backend or settings.vision_backend or "groq").strip().lower()
    # "live_ai" now means the operator EXPLICITLY asked for a non-stub backend, so
    # a misconfiguration should surface loudly (503). The configured default degrades
    # quietly to Doubtful instead (fail-open: score & flag, never block).
    live_ai = explicit and requested != "stub"

    try:
        vision = settings.build_vision_backend(requested)
    except Exception as exc:  # noqa: BLE001
        if explicit:
            # They asked for this specific backend and it's misconfigured — say so.
            raise HTTPException(
                status_code=503, detail=f"Live AI ({requested}) is unavailable: {exc}"
            ) from exc
        # Default path: don't block, don't fake a Clear. Degrade to an unavailable
        # vision so fusion caps the verdict to Doubtful (review).
        vision = UnavailableVision(f"{requested} unavailable: {exc}")
```

Add the import near the other vision imports at the top of the file:

```python
from ..vision.unavailable import UnavailableVision
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_scoring_api.py -k "doubtful or 503" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the whole scoring-api test file (no regressions)**

Run: `pytest tests/integration/test_scoring_api.py -q`
Expected: PASS (the pinned-stub tests still return Clear; new behaviour tests pass)

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/api/scoring.py tests/integration/test_scoring_api.py
git commit -m "feat(api): default-path scoring degrades to Doubtful, not 503, when no key"
```

---

### Task 4: Worker path degrades the same way

The async worker (`process_job`) builds a backend from the tenant's configured name and is not an HTTP request, so it must not crash on a missing key — it degrades to `UnavailableVision` (→ Doubtful).

**Files:**
- Modify: `src/prooflens/service/processor.py` (line ~50)
- Test: `tests/integration/test_webhook_e2e.py` (reuse its existing InMemoryRepo + FakeLSQClient setup)

**Interfaces:**
- Consumes: `UnavailableVision(reason)` from Task 1.
- Produces: `process_job(...)` returns a Verdict (never raises) when the tenant's backend can't be built.

- [ ] **Step 1: Write the failing test**

In `tests/integration/test_webhook_e2e.py`, add a test that drives `process_job` for a tenant configured to `groq` with no key, reusing the same repo/lsq construction the other tests in this file already use. Assert the job completes with a non-Clear verdict instead of raising:

```python
def test_worker_degrades_when_tenant_backend_has_no_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    import prooflens.config as config
    config.get_settings.cache_clear()
    # Build the SAME repo/lsq/settings this file's other tests use, but with a
    # tenant whose vision_backend is "groq" (a live backend with no key set).
    # (Follow the existing setup helper in this file; set tenant.vision_backend="groq".)
    verdict = _run_one_job(vision_backend="groq")   # helper mirrors existing e2e wiring
    assert verdict.band != "Clear"
    config.get_settings.cache_clear()
```

If this file has no reusable single-job helper, add a small `_run_one_job(vision_backend)` at the top of the file that builds `InMemoryRepo([tenant])`, a `FakeLSQClient`, and `Settings()`, enqueues one `meeting.jpg` job, and calls `process_job(...)` — mirroring the existing end-to-end test body.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_webhook_e2e.py -k degrades -v`
Expected: FAIL — `build_vision_backend("groq")` raises (no key), so `process_job` raises instead of returning a Verdict.

- [ ] **Step 3: Implement the degrade**

In `src/prooflens/service/processor.py`, replace line ~49-50:

```python
    # Never call a paid backend implicitly: the tenant chooses (default stub).
    backend = settings.build_vision_backend(tenant.vision_backend)
```

with:

```python
    # Never call a paid backend implicitly; and never crash a job on a
    # misconfigured backend — degrade to an unavailable vision so the verdict
    # caps to Doubtful (fail-open) instead of dead-lettering.
    try:
        backend = settings.build_vision_backend(tenant.vision_backend)
    except Exception as exc:  # noqa: BLE001
        backend = UnavailableVision(f"{tenant.vision_backend} unavailable: {exc}")
```

Add the import near the top of the file:

```python
from ..vision.unavailable import UnavailableVision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_webhook_e2e.py -k degrades -v`
Expected: PASS

- [ ] **Step 5: Run the full webhook e2e file (no regressions)**

Run: `pytest tests/integration/test_webhook_e2e.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/prooflens/service/processor.py tests/integration/test_webhook_e2e.py
git commit -m "feat(worker): degrade to Doubtful instead of crashing on missing backend key"
```

---

### Task 5: Tenant DB default → groq (new migration)

New tenants default to `groq`; existing rows are untouched.

**Files:**
- Modify: `src/prooflens/db/models.py` (line ~60)
- Create: `migrations/versions/0003_default_vision_groq.py`
- Test: `tests/unit/test_db_models.py`

**Interfaces:**
- Produces: `Tenant.vision_backend` column server default `"groq"`.

- [ ] **Step 1: Confirm the current migration head**

Run: `alembic heads`
Expected: prints one head, `0002_review_and_absli_rename (head)`. Use that exact id as `down_revision` below; if it differs, substitute the printed value.

- [ ] **Step 2: Write the failing test**

Add to `tests/unit/test_db_models.py`:

```python
def test_tenant_vision_backend_defaults_to_groq():
    from prooflens.db.models import Tenant
    col = Tenant.__table__.c.vision_backend
    assert col.default.arg == "groq"           # ORM-side default
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_db_models.py -k vision_backend -v`
Expected: FAIL — default is currently `"stub"`.

- [ ] **Step 4: Change the model default**

In `src/prooflens/db/models.py`, line ~60, change:

```python
    vision_backend: Mapped[str] = mapped_column(String(32), default="stub")
```
to:
```python
    vision_backend: Mapped[str] = mapped_column(String(32), default="groq")
```

- [ ] **Step 5: Create the migration**

```python
# migrations/versions/0003_default_vision_groq.py
"""Default new tenants' vision_backend to groq (stub is now test-only).

Existing rows are left as-is; operators change per-tenant backends explicitly.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_default_vision_groq"
down_revision = "0002_review_and_absli_rename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tenants", "vision_backend",
        existing_type=sa.String(32), existing_nullable=False,
        server_default="groq",
    )


def downgrade() -> None:
    op.alter_column(
        "tenants", "vision_backend",
        existing_type=sa.String(32), existing_nullable=False,
        server_default="stub",
    )
```

- [ ] **Step 6: Run test + verify migration applies**

Run: `pytest tests/unit/test_db_models.py -k vision_backend -v`
Expected: PASS

If a local Postgres is available (`DATABASE_URL` set), also run:
Run: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: no errors (upgrade → downgrade → upgrade round-trips cleanly).

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/db/models.py migrations/versions/0003_default_vision_groq.py tests/unit/test_db_models.py
git commit -m "feat(db): default new tenants' vision_backend to groq"
```

---

### Task 6: Documentation sweep

Bring the docs in line: groq is the default; the stub is explicitly test-only, never a production judgement.

**Files:**
- Modify: `README.md`, `docs/DEPLOYMENT.md`, `docs/TENANT_ONBOARDING.md`, `docs/DESIGN_PRINCIPLES.md`, `BRAND.md/BRAND.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update each doc**

Make these substantive edits (search each file for "stub"):
- `README.md` (lines ~33, ~89, ~125): state the default vision backend is **groq**; the stub is the offline/CI backend, selectable by name, and never a production judgement.
- `docs/DEPLOYMENT.md` (line ~32): change the `VISION_BACKEND` row to say the default is `groq` and `GROQ_API_KEY` must be set, else images cap to Doubtful (review).
- `docs/TENANT_ONBOARDING.md` (lines ~25, ~81): new tenants default to `groq`; note the stub is only for offline validation, and a stub tenant can never produce a real Clear.
- `docs/DESIGN_PRINCIPLES.md` (line ~59): keep the "stub is always labelled" principle; add that the stub is never the production default and no-key scoring caps to Doubtful.
- `BRAND.md/BRAND.md` (lines ~253, ~487): keep the "Simulated — not a model judgment" label rule; clarify it now only appears in dev/CLI, not production.

- [ ] **Step 2: Verify no doc still calls the stub the default**

Run: `grep -rniE "default.*stub|stub.*default" README.md docs/ BRAND.md`
Expected: no line describes the stub as the production/default backend (matches only historical/CLI/test context).

- [ ] **Step 3: Commit**

```bash
git add README.md docs/DEPLOYMENT.md docs/TENANT_ONBOARDING.md docs/DESIGN_PRINCIPLES.md "BRAND.md/BRAND.md"
git commit -m "docs: groq is the default backend; stub is test-only"
```

---

### Task 7: Full-suite gate + verdict sanity check

- [ ] **Step 1: Run the whole suite**

Run: `pytest -q`
Expected: PASS (golden set unchanged; new tests green).

- [ ] **Step 2: Lint + types**

Run: `ruff check src tests && mypy src`
Expected: clean.

- [ ] **Step 3: Manual sanity — no-key caps to Doubtful (not Clear)**

Run:
```bash
VISION_BACKEND=groq GROQ_API_KEY= python -c "
from fastapi.testclient import TestClient
from prooflens.api.app import create_app
c = TestClient(create_app(), raise_server_exceptions=False)
import glob; img = sorted(glob.glob('tests/**/meeting.jpg', recursive=True))[0]
r = c.post('/v1/score', files={'image':('m.jpg',open(img,'rb').read(),'image/jpeg')})
print(r.status_code, r.json().get('band'))
"
```
Expected: `200 Doubtful` (status 200, band is NOT Clear).

- [ ] **Step 4: Commit any final fixups, then open the PR (operator action)**

The branch is `backend/retire-stub-default`. Confirm `GROQ_API_KEY` is set on Render (already done), then push and open a PR. No OpenAPI change → no frontend `gen:api` regen needed.

---

## Self-Review

- **Spec coverage:** default→groq (Task 2), no-key→Doubtful default path (Task 3), worker parity (Task 4), stub stays for CLI/tests (Global Constraints + Task 2 step 6), tenant DB default (Task 5), docs (Task 6), testing (each task + Task 7). All spec sections mapped.
- **Placeholder scan:** the only soft spot is Task 4's `_run_one_job` helper, which defers to "mirror the existing e2e wiring" because the exact fixture body lives in that test file — the implementer reads it there. All code steps otherwise show concrete code.
- **Type consistency:** `UnavailableVision(reason: str)` / `.name` / `.is_real` / `.assess()` used identically in Tasks 1, 3, 4. Migration `revision`/`down_revision` ids consistent with Task 5 Step 1 verification.
