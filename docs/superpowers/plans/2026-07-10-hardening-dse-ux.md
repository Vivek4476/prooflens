# Pre-go-live Hardening + DSE UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API-wide rate limiting (#22), push DSE search into SQL + signal result truncation (#20), and give the DSE scorecard a date-range control (#21) — before go-live.

**Architecture:** Three independent, additive changes. #22 is a new in-memory rate-limit middleware wired into `create_app`. #20 adds two SQL-backed repo methods (both repo impls) and reworks the DSE search endpoint + a `truncated` scorecard flag. #21 is a frontend range control reusing the analytics `FilterBar` + `useUrlState`.

**Tech Stack:** Python 3.14, FastAPI/Starlette, SQLAlchemy (backend); Next.js 15 App Router, React 18, TypeScript, axios, Vitest (frontend).

## Global Constraints

- **Additive only:** scoring engine, verdict vocabulary, webhook, `require_tenant` auth, and golden set change ZERO.
- **Honest states:** real `429`/`Retry-After`, real truncation note — never fabricated.
- **Rate limits configurable** via `Settings`, defaults **general 120/60s**, **compute 20/60s**; `0` disables a tier.
- **Rate-limit exempt paths:** `/healthz`, `/readyz`, `/metrics`, `/openapi.json`, `/docs`; only `/v1/*` is limited.
- **Compute routes** (tighter tier): `/v1/score`, `/v1/bulk-score`.
- **Scorecard truncation cap:** `_SCORECARD_LIMIT = 5000`; `truncated = total > _SCORECARD_LIMIT`.
- **LIKE safety:** in Postgres `search_hierarchy`, escape `\`, `%`, `_` in the query so they match literally (`ESCAPE '\'`).
- **Repo parity:** every new `Repo` method exists on BOTH `PostgresRepo` (`db/repo.py`) and `InMemoryRepo` (`service/repo.py`) with identical semantics.
- Backend checks (venv active: `source .venv/bin/activate`): `pytest -q -W ignore`, `ruff check src tests`, `mypy src`. Frontend (in `frontend/`): `npx tsc --noEmit`, `npx vitest run`. Note: bare `python -c` needs `PYTHONPATH=src` on this venv; pytest resolves imports fine.

---

### Task 1: #22 — API-wide rate limiting (in-memory, per-key + per-IP)

**Files:**
- Create: `src/prooflens/api/ratelimit.py`
- Modify: `src/prooflens/config.py` (2 settings), `src/prooflens/api/app.py` (wire middleware), `frontend/BACKEND_REQUIREMENTS.md` (doc)
- Test: `tests/unit/test_ratelimit.py`, `tests/integration/test_ratelimit_api.py`

**Interfaces:**
- Produces: `RateLimiter` class (pure, testable) with `check(bucket_key: str, tier: str) -> tuple[bool, int]` returning `(allowed, retry_after_seconds)`; a `rate_limit_middleware` factory used in `create_app`.

- [ ] **Step 1: Write the failing unit test.** Create `tests/unit/test_ratelimit.py`:

```python
"""Pure in-memory fixed-window rate limiter."""

from __future__ import annotations

from prooflens.api.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks_with_retry_after():
    rl = RateLimiter(limits={"general": 3}, window_seconds=60)
    t = 1000.0
    assert rl.check("k1", "general", now=t)[0] is True   # 1
    assert rl.check("k1", "general", now=t)[0] is True   # 2
    assert rl.check("k1", "general", now=t)[0] is True   # 3
    allowed, retry = rl.check("k1", "general", now=t)     # 4 -> blocked
    assert allowed is False
    assert 0 < retry <= 60


def test_window_resets():
    rl = RateLimiter(limits={"general": 1}, window_seconds=60)
    assert rl.check("k1", "general", now=1000.0)[0] is True
    assert rl.check("k1", "general", now=1000.0)[0] is False
    assert rl.check("k1", "general", now=1061.0)[0] is True  # next window


def test_separate_keys_and_tiers_are_independent():
    rl = RateLimiter(limits={"general": 1, "compute": 1}, window_seconds=60)
    assert rl.check("a", "general", now=1000.0)[0] is True
    assert rl.check("b", "general", now=1000.0)[0] is True   # different key
    assert rl.check("a", "compute", now=1000.0)[0] is True   # different tier


def test_zero_limit_disables_tier():
    rl = RateLimiter(limits={"general": 0}, window_seconds=60)
    for _ in range(100):
        assert rl.check("k", "general", now=1000.0)[0] is True  # 0 == unlimited
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `source .venv/bin/activate && pytest tests/unit/test_ratelimit.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prooflens.api.ratelimit'`.

- [ ] **Step 3: Implement the limiter + middleware.** Create `src/prooflens/api/ratelimit.py`:

```python
"""In-memory fixed-window rate limiting for the /v1/* surface.

Single-instance only: counters live in this process. A multi-instance deploy
needs a shared store (Redis) — deferred; see BACKEND_REQUIREMENTS.md. Bucketed
by the API key (hashed) when present, else client IP. Two tiers: a general cap
on all /v1/*, a tighter cap on the compute routes (/v1/score, /v1/bulk-score).
A limit of 0 means unlimited (disables the tier)."""

from __future__ import annotations

import time
from hashlib import sha256

from fastapi import Request, Response

# Paths under /v1/ that get the stricter "compute" tier.
_COMPUTE_PATHS = ("/v1/score", "/v1/bulk-score")


class RateLimiter:
    """Fixed 60s window per (bucket_key, tier). check() returns
    (allowed, retry_after_seconds). Thread-safety is not required: the ASGI
    event loop is single-threaded and check() does no awaits."""

    def __init__(self, limits: dict[str, int], window_seconds: int = 60) -> None:
        self._limits = limits
        self._window = window_seconds
        # (bucket_key, tier) -> (window_start_epoch, count)
        self._buckets: dict[tuple[str, str], tuple[float, int]] = {}

    def check(self, bucket_key: str, tier: str, now: float | None = None) -> tuple[bool, int]:
        limit = self._limits.get(tier, 0)
        if limit <= 0:
            return True, 0  # 0/absent => unlimited
        t = time.time() if now is None else now
        key = (bucket_key, tier)
        start, count = self._buckets.get(key, (t, 0))
        if t - start >= self._window:
            start, count = t, 0  # new window
        count += 1
        self._buckets[key] = (start, count)
        if count > limit:
            retry = int(self._window - (t - start)) + 1
            return False, max(retry, 1)
        return True, 0

    def prune(self, now: float | None = None) -> None:
        """Drop windows older than one full window (opportunistic GC)."""
        t = time.time() if now is None else now
        stale = [k for k, (start, _) in self._buckets.items() if t - start >= self._window]
        for k in stale:
            del self._buckets[k]


def _bucket_key(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        raw = auth[7:].strip()
        if raw:
            return "k:" + sha256(raw.encode("utf-8")).hexdigest()[:32]
    # First hop of X-Forwarded-For (Render/Vercel proxy), else the socket peer.
    xff = request.headers.get("x-forwarded-for")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    return "ip:" + ip


def make_rate_limit_middleware(limiter: RateLimiter):
    """A Starlette http middleware enforcing `limiter` on /v1/* only."""

    async def middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if not path.startswith("/v1/"):
            return await call_next(request)
        bkey = _bucket_key(request)
        # A compute request counts against BOTH tiers; the stricter one wins.
        tiers = ["general"]
        if path in _COMPUTE_PATHS:
            tiers.append("compute")
        for tier in tiers:
            allowed, retry = limiter.check(bkey, tier)
            if not allowed:
                return Response(
                    status_code=429,
                    content='{"detail":"rate limit exceeded"}',
                    media_type="application/json",
                    headers={"Retry-After": str(retry)},
                )
        return await call_next(request)

    return middleware
```

- [ ] **Step 4: Run the unit test — verify pass.**

Run: `pytest tests/unit/test_ratelimit.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Add the two settings.** In `src/prooflens/config.py`, after the `admin_token` field (~line 30) add:

```python
    # Rate limits (per 60s window) for /v1/*. 0 disables that tier. Multi-instance
    # deploys need a shared store (Redis) — single-process counters otherwise.
    ratelimit_general_per_min: int = Field(default=120, alias="RATELIMIT_GENERAL_PER_MIN")
    ratelimit_compute_per_min: int = Field(default=20, alias="RATELIMIT_COMPUTE_PER_MIN")
```

- [ ] **Step 6: Wire the middleware in `create_app`.** In `src/prooflens/api/app.py`, add the import near the others: `from .ratelimit import RateLimiter, make_rate_limit_middleware`. Then inside `create_app`, AFTER the `_limit_body_size` middleware definition and BEFORE `app.add_middleware(CORSMiddleware, ...)`, add:

```python
    _rate_limiter = RateLimiter(
        limits={
            "general": settings.ratelimit_general_per_min,
            "compute": settings.ratelimit_compute_per_min,
        },
        window_seconds=60,
    )
    app.middleware("http")(make_rate_limit_middleware(_rate_limiter))
```

(Starlette runs `@app.middleware("http")` handlers in reverse registration order; registering the limiter after body-size is fine — both run before routes/deps. Auth is a route dependency, so the limiter still runs before auth.)

- [ ] **Step 7: Write the integration test.** Create `tests/integration/test_ratelimit_api.py`:

```python
"""Rate-limit middleware behaviour over the real app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflens.api.app import create_app
from prooflens.api.deps import get_repo
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _client(general: int, compute: int) -> TestClient:
    # Patch settings so the app builds with tiny limits.
    from prooflens import config
    config.get_settings.cache_clear()
    import os
    os.environ["RATELIMIT_GENERAL_PER_MIN"] = str(general)
    os.environ["RATELIMIT_COMPUTE_PER_MIN"] = str(compute)
    repo = InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                                    scoring=ScoringConfig(), vision_backend="stub")])
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    from prooflens.api.auth import require_tenant
    app.dependency_overrides[require_tenant] = lambda: repo.get_tenant_by_slug("dev")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from prooflens import config
    yield
    import os
    os.environ.pop("RATELIMIT_GENERAL_PER_MIN", None)
    os.environ.pop("RATELIMIT_COMPUTE_PER_MIN", None)
    config.get_settings.cache_clear()


def test_over_general_limit_returns_429_with_retry_after():
    client = _client(general=2, compute=0)
    assert client.get("/v1/results").status_code == 200
    assert client.get("/v1/results").status_code == 200
    r = client.get("/v1/results")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_probes_are_never_limited():
    client = _client(general=1, compute=0)
    for _ in range(10):
        assert client.get("/healthz").status_code == 200  # exempt


def test_compute_tier_is_stricter():
    # general high, compute=1: the 2nd bulk-score call is limited by the compute tier.
    client = _client(general=1000, compute=1)
    assert client.post("/v1/bulk-score", json={"rows": [{"image_url": "https://x/p.jpg"}]}).status_code in (200, 429)
    r = client.post("/v1/bulk-score", json={"rows": [{"image_url": "https://x/p.jpg"}]})
    assert r.status_code == 429
```

- [ ] **Step 8: Run integration test + full suite + lint/type.**

Run: `pytest tests/integration/test_ratelimit_api.py -q -W ignore && pytest -q -W ignore && ruff check src tests && mypy src`
Expected: all pass. (If `get_settings` is not `lru_cache`d, drop the `cache_clear()` calls — check `config.py`; the test's `os.environ` set before `create_app` is what matters.)

- [ ] **Step 9: Document + commit.** Append to `frontend/BACKEND_REQUIREMENTS.md`:

```markdown
## Rate limiting (#22)
`/v1/*` is rate-limited per 60s window, bucketed by API key (hashed) or client IP: general
`RATELIMIT_GENERAL_PER_MIN` (default 120), compute (`/v1/score`, `/v1/bulk-score`)
`RATELIMIT_COMPUTE_PER_MIN` (default 20); `0` disables a tier. Over limit → `429` + `Retry-After`.
`/healthz`/`/readyz`/`/metrics` are exempt. **Single-instance only** — counters are per-process; a
multi-instance deploy needs a shared store (Redis).
```

```bash
git add src/prooflens/api/ratelimit.py src/prooflens/config.py src/prooflens/api/app.py tests/unit/test_ratelimit.py tests/integration/test_ratelimit_api.py frontend/BACKEND_REQUIREMENTS.md
git commit -m "feat(ratelimit): in-memory per-key/IP rate limiting on /v1/* (#22)"
```

---

### Task 2: #20 — DSE search SQL pushdown + scorecard truncation flag (backend)

**Files:**
- Modify: `src/prooflens/service/repo.py` (`Repo` protocol + `InMemoryRepo`), `src/prooflens/db/repo.py` (`PostgresRepo`), `src/prooflens/api/dse.py`
- Test: `tests/unit/test_dse_search_repo.py`, and extend `tests/integration/test_dse_api.py`

**Interfaces:**
- Produces:
  - `Repo.search_hierarchy(tenant_id: str, q: str, limit: int) -> list[dict]` — latest-row-per-agent whose `agent_id`/`agent_name` contains `q` (case-insensitive, literal `%`/`_`), capped to `limit`, sorted by `agent_id`. Row dicts have the same keys `get_hierarchy_rows` returns.
  - `Repo.result_counts_by_rep(tenant_id: str, start: datetime | None, end: datetime | None) -> dict[str, int]` — `rep_id -> count` over that tenant's results in `[start, end)` (both None = all).
  - `dse_scorecard` response gains `"truncated": bool`.

- [ ] **Step 1: Write the failing repo test.** Create `tests/unit/test_dse_search_repo.py`:

```python
"""search_hierarchy + result_counts_by_rep on InMemoryRepo."""

from __future__ import annotations

from datetime import UTC, date, datetime

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import ResultView, TenantView


def _repo() -> InMemoryRepo:
    r = InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                                 scoring=ScoringConfig(), vision_backend="stub")])
    r.replace_hierarchy("t1", [
        {"agent_id": "A1", "agent_name": "Asha Verma", "sm": "Sam", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": date(2026, 1, 1)},
        {"agent_id": "A2", "agent_name": "50%_special", "sm": "Sam", "rsm": None, "srsm": None,
         "zonal_head": None, "branch": "North", "city": None, "valid_from": date(2026, 1, 1)},
    ], "up1")
    return r


def test_search_by_name_and_id():
    r = _repo()
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "asha", 25)] == ["A1"]
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "a2", 25)] == ["A2"]


def test_like_metacharacters_match_literally():
    # "%_" must match the literal name "50%_special", not act as wildcards.
    r = _repo()
    assert [x["agent_id"] for x in r.search_hierarchy("t1", "%_special", 25)] == ["A2"]


def test_search_limit_caps():
    r = _repo()
    assert len(r.search_hierarchy("t1", "", 1)) == 1  # empty q matches all, capped


def test_result_counts_by_rep_scoped_and_counted():
    r = _repo()
    for i, rep in enumerate(["A1", "A1", "A2"]):
        r.results.append(ResultView(id=f"x{i}", created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
                                    tenant_id="t1", band="Clear", score=90.0, reason="r",
                                    reason_code="clear", rubric_version="v3", rep_id=rep))
    # a different tenant's row must not count
    r.results.append(ResultView(id="y", created_at=datetime(2026, 6, 1, 12, tzinfo=UTC).isoformat(),
                                tenant_id="t2", band="Clear", score=90.0, reason="r",
                                reason_code="clear", rubric_version="v3", rep_id="A1"))
    counts = r.result_counts_by_rep("t1", None, None)
    assert counts == {"A1": 2, "A2": 1}
```

- [ ] **Step 2: Run it — verify it fails.**

Run: `pytest tests/unit/test_dse_search_repo.py -q`
Expected: FAIL — `AttributeError: 'InMemoryRepo' object has no attribute 'search_hierarchy'`.

- [ ] **Step 3: Add the two methods to the `Repo` protocol.** In `src/prooflens/service/repo.py`, in the `Repo` protocol (near `get_hierarchy_rows`) add:

```python
    def search_hierarchy(self, tenant_id: str, q: str, limit: int) -> list[dict]:
        """Latest hierarchy row per agent whose agent_id/agent_name contains q
        (case-insensitive, % and _ literal), capped to limit, sorted by agent_id."""
        ...

    def result_counts_by_rep(
        self, tenant_id: str, start: datetime | None, end: datetime | None
    ) -> dict[str, int]:
        """rep_id -> result count for this tenant in [start, end) (None = unbounded)."""
        ...
```

- [ ] **Step 4: Implement on `InMemoryRepo`** (same file). Add:

```python
    def search_hierarchy(self, tenant_id: str, q: str, limit: int) -> list[dict]:
        rows = self._hierarchy.get(tenant_id, [])
        latest: dict[str, dict] = {}
        for r in rows:
            aid = r.get("agent_id")
            if aid is None:
                continue
            cur = latest.get(aid)
            if cur is None or r["valid_from"] > cur["valid_from"]:
                latest[aid] = r
        needle = q.strip().lower()
        matches = [
            r for r in latest.values()
            if needle in (r["agent_id"] or "").lower()
            or needle in (r.get("agent_name") or "").lower()
        ]
        matches.sort(key=lambda r: r["agent_id"])
        return [dict(r) for r in matches[:limit]]

    def result_counts_by_rep(
        self, tenant_id: str, start: datetime | None, end: datetime | None
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            if r.tenant_id != tenant_id or not r.rep_id or not r.created_at:
                continue
            ts = datetime.fromisoformat(r.created_at)
            if start is not None and ts < start:
                continue
            if end is not None and ts >= end:
                continue
            counts[r.rep_id] = counts.get(r.rep_id, 0) + 1
        return counts
```

(`datetime` is already imported in `service/repo.py`.)

- [ ] **Step 5: Run the repo test — verify pass.**

Run: `pytest tests/unit/test_dse_search_repo.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Implement on `PostgresRepo`** (`src/prooflens/db/repo.py`). Add these imports at the top if missing: `from sqlalchemy import func, or_` and `from sqlalchemy.orm import aliased`. Add the methods:

```python
    def search_hierarchy(self, tenant_id: str, q: str, limit: int) -> list[dict]:
        tid = uuid.UUID(tenant_id)
        # Latest row per agent via DISTINCT ON (Postgres), then match + cap in SQL.
        latest_sq = (
            self._session.query(Hierarchy)
            .filter(Hierarchy.tenant_id == tid)
            .distinct(Hierarchy.agent_id)
            .order_by(Hierarchy.agent_id, Hierarchy.valid_from.desc())
            .subquery()
        )
        H = aliased(Hierarchy, latest_sq)
        needle = q.strip().lower()
        # Escape LIKE metacharacters so they match literally.
        esc = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pat = f"%{esc}%"
        rows = (
            self._session.query(H)
            .filter(
                or_(
                    func.lower(H.agent_id).like(pat, escape="\\"),
                    func.lower(func.coalesce(H.agent_name, "")).like(pat, escape="\\"),
                )
            )
            .order_by(H.agent_id)
            .limit(limit)
            .all()
        )
        return [{
            "agent_id": h.agent_id, "agent_name": h.agent_name,
            "sm": h.sm, "rsm": h.rsm, "srsm": h.srsm,
            "zonal_head": h.zonal_head, "branch": h.branch, "city": h.city,
            "valid_from": h.valid_from, "upload_id": h.upload_id,
        } for h in rows]

    def result_counts_by_rep(
        self, tenant_id: str, start: datetime | None, end: datetime | None
    ) -> dict[str, int]:
        tid = uuid.UUID(tenant_id)
        query = (
            self._session.query(Result.rep_id, func.count().label("n"))
            .filter(Result.tenant_id == tid, Result.rep_id.isnot(None))
        )
        if start is not None:
            query = query.filter(Result.created_at >= start)
        if end is not None:
            query = query.filter(Result.created_at < end)
        query = query.group_by(Result.rep_id)
        return {rep_id: n for rep_id, n in query.all()}
```

- [ ] **Step 7: Rework `search_dse` to use the new methods + drop the 5000-row load.** In `src/prooflens/api/dse.py`, replace the `search_dse` body (keep the decorator + signature) with:

```python
    tenant_id = tenant.id
    needle = q.strip()
    if needle:
        matches = repo.search_hierarchy(tenant_id, needle, _SEARCH_LIMIT)
    else:
        rows = repo.get_hierarchy_rows(tenant_id) if tenant_id else []
        latest = _latest_rows_by_agent(rows)
        counts = repo.result_counts_by_rep(tenant_id, None, None)  # most-active, all time (as before)
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
```

(This removes the `agent_display_name(...)` call from the search path and the `list_results(limit=5000)` load. `agent_display_name` is still used by the scorecard — keep its import.)

- [ ] **Step 8: Add the truncation flag to the scorecard.** In `src/prooflens/api/dse.py`, near the other module constants add `_SCORECARD_LIMIT = 5000`. In `dse_scorecard`, change the main results call from `limit=5000` to `limit=_SCORECARD_LIMIT`, and add `"truncated"` to the returned dict:

```python
    items, total = repo.list_results(
        tenant_id=tenant_id, limit=_SCORECARD_LIMIT, offset=0, rep_id=agent_id, start=start, end=end
    )
    # ... existing body unchanged ...
    return {
        "agent_id": ...,   # unchanged existing keys
        # ...
        "recent": recent,
        "truncated": total > _SCORECARD_LIMIT,
    }
```

- [ ] **Step 9: Extend the DSE API tests.** In `tests/integration/test_dse_api.py` add:

```python
def test_scorecard_truncated_flag_false_for_small(client, repo):
    _seed_results(repo, "A1", [(date(2026, 6, 1), "Clear")])
    r = client.get("/v1/dse/A1", params={"from": "2026-06-01", "to": "2026-06-02"})
    assert r.json()["truncated"] is False


def test_search_uses_repo_and_still_finds_by_name(client):
    # Regression: the reworked search still returns the seeded agents by name.
    body = client.get("/v1/dse", params={"q": "asha"}).json()
    assert [x["agent_id"] for x in body["results"]] == ["A1"]
    assert body["results"][0]["name"] == "Asha Verma"
```

- [ ] **Step 10: Full suite + lint/type.**

Run: `pytest -q -W ignore && ruff check src tests && mypy src`
Expected: all pass (existing DSE tests still green — the endpoint output shape is unchanged except the added `truncated` key).

- [ ] **Step 11: Commit.**

```bash
git add src/prooflens/service/repo.py src/prooflens/db/repo.py src/prooflens/api/dse.py tests/unit/test_dse_search_repo.py tests/integration/test_dse_api.py
git commit -m "feat(dse): SQL-pushdown search + counts + scorecard truncation flag (#20)"
```

---

### Task 3: #21 — DSE date-range control + truncation note (frontend)

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (`DseScorecard.truncated`), `frontend/src/lib/api/hooks.ts` (add `useDseScorecardFilters`), `frontend/src/app/(app)/dse/page.tsx` (range control + pass params + truncation note)
- Test: `frontend/src/lib/api/hooks.test.ts` (or a new `dse-filters.test.ts`) if the pattern exists; otherwise a component test.

**Interfaces:**
- Consumes: `DseScorecard.truncated` (Task 2), the existing `FilterBar` (`components/analytics/FilterBar.tsx`), `useUrlState`, `useDseScorecard(agentId, {from,to,bucket})`, and the existing `useAnalyticsFilters` (mirror its preset→range resolution).

- [ ] **Step 1: Add `truncated` to the type.** In `frontend/src/lib/api/types.ts`, add to `DseScorecard`:

```typescript
export interface DseScorecard {
  agent_id: string;
  name: string;
  chain: DseChain;
  total: number;
  band_distribution: Record<Band, number>;
  suspect_rate: number;
  avg_score: number;
  top_reasons: DseTopReason[];
  trend: DseTrendPoint[];
  recent: ResultItem[];
  truncated: boolean; // NEW — true when total exceeded the scorecard's 5000 cap
}
```

- [ ] **Step 2: Add a DSE filters hook mirroring the analytics one.** First READ the existing `useAnalyticsFilters` (grep: `grep -rn "useAnalyticsFilters" frontend/src` — it wraps `useUrlState` and resolves a `RangePreset` + custom `from`/`to` into resolved dates, and a `Bucket`). Create `useDseScorecardFilters()` in `frontend/src/lib/api/hooks.ts` that does the SAME preset/custom/bucket resolution but returns exactly what `/dse` needs:

```typescript
// Mirrors useAnalyticsFilters (read it first). URL-backed range+bucket for the
// DSE scorecard. Default preset = "30d" (last 30 days), matching prior behavior.
export function useDseScorecardFilters() {
  // Reuse the SAME preset→{from,to} resolution + useUrlState wiring as
  // useAnalyticsFilters; only the returned `params` shape differs.
  // Returns: { preset, bucket, from, to, params, setPreset, setCustomRange, setBucket }
  // where params = { from, to, bucket } passed straight to useDseScorecard.
  // (Copy useAnalyticsFilters and drop the analytics-only `group_by`; keep range presets + bucket.)
}
```

If a shared resolver exists (e.g. `resolveRange(preset, from, to)`), reuse it — do NOT duplicate the date math. Keep the default preset = last 30 days so the scorecard is unchanged when no range is picked.

- [ ] **Step 3: Wire the control into `/dse`.** In `frontend/src/app/(app)/dse/page.tsx`, in `DsePageInner`, replace the plain `useDseScorecard(agentId)` with the filtered version and render `FilterBar` (only when an agent is selected):

```tsx
  const agentId = searchParams.get("agent") ?? undefined;
  const { preset, bucket, from, to, params, setPreset, setCustomRange, setBucket } =
    useDseScorecardFilters();
  const { data, isLoading, isError, refetch, isPlaceholderData } = useDseScorecard(agentId, params);
```

Inside the `agentId` branch (above the header `Card`), add the filter bar:

```tsx
        <FilterBar
          preset={preset}
          bucket={bucket}
          from={from}
          to={to}
          onPresetChange={setPreset}
          onCustomRangeChange={setCustomRange}
          onBucketChange={setBucket}
        />
```

(Import `FilterBar` from `@/components/analytics/FilterBar`. Omit `period`/`previousPeriod` — the DSE scorecard response has no period bounds, and those props are optional.)

- [ ] **Step 4: Add the honest truncation note.** In the success branch of `/dse`, next to the existing `isSparseDse` caveat, add:

```tsx
          {data.truncated && (
            <p className="text-caption text-text-muted">
              Showing the most recent 5,000 captures in range — totals above are capped.
            </p>
          )}
```

- [ ] **Step 5: Typecheck.**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: clean (exit 0). Fix any type mismatch in the new hook's return shape.

- [ ] **Step 6: Test the filters hook.** If `useAnalyticsFilters` has a co-located test, mirror it for `useDseScorecardFilters` in `frontend/src/lib/api/hooks.test.ts` (or a new `dse-filters.test.ts`) asserting: default `params` is a last-30-days range with `bucket: "daily"`; `setPreset("7d")` updates `params.from`/`to`. If there is NO existing hook test to mirror (these hooks need a Next router context), instead add a pure unit test for the shared range resolver you reused, OR document in the report that the hook is covered by the existing analytics filter tests (same resolver) and skip a redundant router-mocked test. Do NOT stand up a new router-mock harness just for this.

Run (in `frontend/`): `npx vitest run`
Expected: all pass (existing 182 + any added).

- [ ] **Step 7: Verify live (optional but recommended).** With the local stack running (backend authed on :8000, frontend on :3000, `.env.local` wired), open `http://localhost:3000/dse?agent=AGT0012`, confirm the range bar renders, switch presets, and confirm the scorecard refetches. Screenshot to `scratchpad/shots/dse-range.png`.

- [ ] **Step 8: Commit.**

```bash
cd .. && git add frontend/src/lib/api/types.ts frontend/src/lib/api/hooks.ts "frontend/src/app/(app)/dse/page.tsx"
git commit -m "feat(dse): date-range control + truncation note on the scorecard (#21, #20 UI)"
```

---

## Self-review notes (addressed)
- **Spec coverage:** #22 → Task 1; #20 (SQL pushdown + counts + truncation) → Task 2 (backend) + Task 3 Step 4 (UI note); #21 → Task 3. All covered.
- **Type consistency:** `search_hierarchy`/`result_counts_by_rep` signatures identical across protocol + both impls + call site; `truncated` produced in Task 2, consumed in Task 3; `useDseScorecard(agentId, params)` already exists.
- **Ambiguity resolved:** empty-`q` "most active" counts over ALL results (matches current code, which passes no date filter — the docstring's "90 days" is not enforced today; behavior preserved). The `%`/`_` literal-match requirement is tested in both repos (InMemory `in` is literal; Postgres escaped LIKE).
